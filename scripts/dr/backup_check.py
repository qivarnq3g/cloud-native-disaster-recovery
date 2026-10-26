"""Kiểm tra sao lưu mỗi giờ (mục 4.5 thiết kế), lõi của workflow `backup-check`.

Ngưỡng: WAL mới nhất không cũ hơn 5 phút; bản Velero không cũ hơn 2 giờ; ảnh trong kho chính
cũ hơn 5 phút phải đã có ở bản chép; mã SAS còn ít nhất 7 ngày. Phiên đã tắt thì chỉ kiểm
tệp phiên, hạn SAS và hai bản sao lưu lúc tắt phiên. Kho rỗng hay thiếu tệp là lỗi, không phải
"không có gì để kiểm".

Dòng lệnh: python -m scripts.dr.backup_check --csv <file>
Mã truy cập lấy từ biến BACKUP_CHECK_SAS_JSON, một JSON {container_url: sas}.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.dr.session_state import Session, read_sas_expiry, read_session

CHECKS = ("session_file", "wal_age", "velero_age", "image_replication", "sas_expiry", "stop_backups")
WAL_MAX_AGE = timedelta(minutes=5)
VELERO_MAX_AGE = timedelta(hours=2)
IMAGE_RPO = timedelta(minutes=5)
SAS_MIN_LEFT = timedelta(days=7)


@dataclass
class Snapshot:
    session: Session | None
    sas_expiry: dict[str, datetime]
    newest_wal: datetime | None
    newest_velero: datetime | None
    velero_names: set[str]
    full_backup_names: set[str]
    primary_images: dict[str, datetime]
    copied_images: set[str]


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def _skip(name: str) -> CheckResult:
    return CheckResult(name, True, "skip")


def _age(name: str, newest: datetime | None, limit: timedelta, now: datetime, what: str) -> CheckResult:
    if newest is None:
        return CheckResult(name, False, f"chưa có {what} nào")
    age = now - newest
    return CheckResult(name, age <= limit, f"{what} mới nhất cũ {int(age.total_seconds())} s (ngưỡng {int(limit.total_seconds())} s)")


def evaluate(s: Snapshot, now: datetime) -> list[CheckResult]:
    results: dict[str, CheckResult] = {}
    state = s.session.state if s.session else None
    results["session_file"] = (CheckResult("session_file", True, f"state={state}") if s.session
                               else CheckResult("session_file", False, "thiếu status/session.json"))

    if state == "running":
        results["wal_age"] = _age("wal_age", s.newest_wal, WAL_MAX_AGE, now, "WAL")
        results["velero_age"] = _age("velero_age", s.newest_velero, VELERO_MAX_AGE, now, "bản Velero")
        late = sorted(n for n, t in s.primary_images.items() if now - t > IMAGE_RPO and n not in s.copied_images)
        results["image_replication"] = CheckResult(
            "image_replication", not late,
            f"{len(late)} ảnh quá 5 phút chưa chép: {', '.join(late[:5])}" if late
            else f"{len(s.primary_images)} ảnh, đủ ở bản chép")
        results["stop_backups"] = _skip("stop_backups")
    else:
        for name in ("wal_age", "velero_age", "image_replication"):
            results[name] = _skip(name)
        if state == "stopped":
            missing = []
            if not s.session.full_backup or s.session.full_backup not in s.full_backup_names:
                missing.append(f"bản đầy đủ {s.session.full_backup}")
            if not s.session.velero_backup or s.session.velero_backup not in s.velero_names:
                missing.append(f"bản Velero {s.session.velero_backup}")
            results["stop_backups"] = CheckResult("stop_backups", not missing,
                                                  "thiếu " + ", ".join(missing) if missing else "đủ hai bản lúc tắt phiên")
        else:
            results["stop_backups"] = _skip("stop_backups")

    if not s.sas_expiry:
        results["sas_expiry"] = CheckResult("sas_expiry", False, "thiếu status/sas-expiry.json")
    else:
        soon = sorted(n for n, t in s.sas_expiry.items() if t - now < SAS_MIN_LEFT)
        results["sas_expiry"] = CheckResult("sas_expiry", not soon,
                                            f"còn dưới 7 ngày: {', '.join(soon)}" if soon else "mọi mã còn từ 7 ngày")
    return [results[n] for n in CHECKS]


def _container(url: str, sas: str):
    from azure.storage.blob import ContainerClient

    return ContainerClient.from_container_url(f"{url.rstrip('/')}?{sas.lstrip('?')}")


def _pick(sas: dict[str, str], account_prefix: str, container: str) -> tuple[str, str]:
    for url, token in sas.items():
        parts = url.rstrip("/").split("/")
        if parts[-1] == container and parts[2].startswith(account_prefix):
            return url, token
    raise KeyError(f"BACKUP_CHECK_SAS_JSON thiếu container {container} của tài khoản {account_prefix}*")


def collect(sas: dict[str, str]) -> Snapshot:
    """Đọc kho bằng các mã chỉ đọc. Tên tài khoản theo bảng tên của kế hoạch hạ tầng."""
    status = _container(*_pick(sas, "drbackup", "status"))
    session = read_session(status)
    sas_expiry = read_sas_expiry(status)

    newest_wal = None
    full_backup_names: set[str] = set()
    if session is not None:
        cnpg = _container(*_pick(sas, "drbackup", "cnpg"))
        wals = [b.last_modified for b in cnpg.list_blobs(name_starts_with=f"{session.server_name}/wals/")]
        newest_wal = max(wals, default=None)
        for b in cnpg.list_blobs(name_starts_with=f"{session.server_name}/base/"):
            parts = b.name.split("/")
            if len(parts) >= 4:
                full_backup_names.add(parts[2])
            if parts[-1] == "backup.info":
                # Barman ghi tên bản sao lưu (tên đối tượng Backup của CNPG) vào backup.info.
                info = cnpg.get_blob_client(b.name).download_blob().readall().decode(errors="replace")
                for line in info.splitlines():
                    if line.startswith("backup_name="):
                        full_backup_names.add(line.split("=", 1)[1].strip())

    velero = _container(*_pick(sas, "drbackup", "velero"))
    velero_times: dict[str, datetime] = {}
    for b in velero.list_blobs(name_starts_with="backups/"):
        parts = b.name.split("/")
        if len(parts) == 3 and parts[2] == "velero-backup.json":
            velero_times[parts[1]] = b.last_modified

    primary = _container(*_pick(sas, "drimgpri", "images"))
    copy = _container(*_pick(sas, "drimgcopy", "images"))
    return Snapshot(
        session=session,
        sas_expiry=sas_expiry,
        newest_wal=newest_wal,
        newest_velero=max(velero_times.values(), default=None),
        velero_names=set(velero_times),
        full_backup_names=full_backup_names,
        primary_images={b.name: b.last_modified for b in primary.list_blobs()},
        copied_images={b.name for b in copy.list_blobs()},
    )


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_csv(path: Path, s: Snapshot, results: list[CheckResult], now: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["checked_at", "state", *CHECKS])
        by_name = {r.name: r for r in results}
        w.writerow([_iso(now), s.session.state if s.session else "",
                    *("skip" if by_name[n].detail == "skip" else ("ok" if by_name[n].ok else "fail") for n in CHECKS)])


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Kiểm tra sao lưu mỗi giờ")
    p.add_argument("--csv", type=Path)
    a = p.parse_args(argv)
    now = datetime.now(UTC)
    raw = os.environ.get("BACKUP_CHECK_SAS_JSON")
    if not raw:
        print("thiếu biến BACKUP_CHECK_SAS_JSON", file=sys.stderr)
        return 1
    snapshot = collect(json.loads(raw))
    results = evaluate(snapshot, now)
    for r in results:
        print(f"{'skip' if r.detail == 'skip' else ('ok' if r.ok else 'FAIL'):5} {r.name:18} {r.detail}")
    if a.csv:
        append_csv(a.csv, snapshot, results, now)
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
