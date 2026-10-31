from __future__ import annotations

import argparse
import csv
import hashlib
import os
import platform
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.kind import results
from scripts.kind.probe import Prober, check
from scripts.kind.verify import check_images, compare, content_digest
from scripts.kind.workload import ApiClient, Ledger, Writer, parse_time, post_one, read_ledger

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = Path(os.environ.get("DR_PRIVATE_DIR", Path.home() / ".dr"))
DRILLS = Path(os.environ.get("DR_DATA_DIR", ROOT / "data" / "azure")) / "drills"
DOMAIN = "api.dr.qivarn.id.vn"
PUBLIC = f"https://{DOMAIN}"
CONTROL_URL = "https://www.gstatic.com/generate_204"
WARMUP_S = float(os.environ.get("WARMUP_S", 90))
DETECT_TIMEOUT_S = 180
STEP_SH = "scripts/azure/step.sh"
BREAK_SH = "scripts/azure/break.sh"
TARGET = "{target}"
WARM = ("D3", "D5")

COLD = "scripts/azure/failover-cold.sh"
WARM_SH = "scripts/azure/failover-warm.sh"
RUNBOOK: dict[str, list[tuple[str, list[str]]]] = {
    "D1": [("infra", []), ("restore", ["bash", "scripts/azure/restore-namespace.sh", "--restore", TARGET]),
           ("switch", [])],
    "D2": [("infra", ["bash", COLD, "--infra", "standby"]), ("restore", ["bash", COLD, "--restore", "standby"]),
           ("switch", ["bash", COLD, "--switch", "standby"])],
    "D3": [("infra", []), ("restore", ["bash", WARM_SH, "--promote"]), ("switch", ["bash", WARM_SH, "--switch"])],
    "D4": [("infra", ["bash", COLD, "--infra", "standby"]),
           ("restore", ["env", "DR_IMAGES_FROM_COPY=true", "bash", COLD, "--restore", "standby"]),
           ("switch", ["bash", COLD, "--switch", "standby"])],
}
RUNBOOK["D5"] = RUNBOOK["D3"]
SERVING = {"D1": "primary", "D2": "standby", "D3": "standby", "D4": "standby", "D5": "standby"}


def log(msg: str) -> None:
    print(f"{datetime.now(UTC):%H:%M:%S} {msg}", file=sys.stderr, flush=True)


def secret_code() -> str:
    return (PRIVATE / "secret-code").read_text().strip()


def vm_ip(cluster: str) -> str | None:
    p = subprocess.run(["az", "vm", "show", "-d", "-g", f"rg-dr-{cluster}", "-n", f"vm-dr-{cluster}",
                        "--query", "publicIps", "-o", "tsv"], capture_output=True, text=True, timeout=120)
    return p.stdout.strip() or None if p.returncode == 0 else None


def direct(cluster: str, timeout: float = 5) -> ApiClient | None:
    ip = vm_ip(cluster)
    return ApiClient(f"http://{ip}", secret_code(), timeout=timeout, host=DOMAIN) if ip else None


def control_ok() -> bool:
    try:
        with urllib.request.urlopen(CONTROL_URL, timeout=2) as r:
            return r.status == 204
    except Exception:
        return False


class Monitor:
    def __init__(self, ledger: Ledger, with_standby: bool):
        targets = {"public": ApiClient(PUBLIC, timeout=5)}
        for cluster in ("primary", "standby") if with_standby else ("primary",):
            client = direct(cluster)
            if client:
                targets[cluster] = client
        self.writer = Writer(ApiClient(PUBLIC, secret_code(), timeout=10), ledger)
        self.prober = Prober(targets, watch="public", control=control_ok)

    def start(self) -> None:
        self.writer.start()
        self.prober.start()

    def wait_detected(self, timeout: float) -> datetime | None:
        return self.prober.detector.detected_at if self.prober.detected.wait(timeout) else None

    def network_down_s(self, start: datetime, end: datetime) -> float:
        seconds = {int(s.at.timestamp()) for s in self.prober.samples
                   if s.target == "public" and not s.network_ok and start <= s.at <= end}
        return float(len(seconds))

    def stop_writer(self) -> None:
        self.writer.stop()
        log(f"đã xác nhận {self.writer.acked} bài, lỗi {self.writer.failed} lần")

    def stop(self) -> None:
        self.prober.stop()

    def save(self, path: Path) -> None:
        with path.open("w", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["at", "target", "ok", "status", "cluster", "read_only", "network_ok"])
            for s in self.prober.samples:
                w.writerow([results.iso(s.at), s.target, str(s.ok).lower(), s.status, s.cluster,
                            "" if s.read_only is None else str(s.read_only).lower(), str(s.network_ok).lower()])


class AzureEnv:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def health(self, target: str) -> dict | None:
        client = ApiClient(PUBLIC) if target == "public" else direct(target)
        if client is None:
            return None
        ok, _, body = check(client)
        return body if ok else None

    def monitor(self, ledger: Ledger, with_standby: bool) -> Monitor:
        return Monitor(ledger, with_standby)

    def sh(self, cmd: list[str], extra_env: dict | None = None) -> int:
        env = {**os.environ, "DR_DATA_DIR": DRILLS.parent.as_posix(), **(extra_env or {})}
        return subprocess.run(["bash", *cmd], cwd=ROOT, env=env).returncode

    def psql(self, cluster: str, sql: str) -> str:
        env = {**os.environ, "KUBECONFIG": str(PRIVATE / f"kubeconfig-{cluster}")}
        p = subprocess.run(["kubectl", "-n", "dr-api", "exec", "db-1", "-c", "postgres", "--", "psql", "-d", "dr",
                            "-tA", "-F", ",", "-c", sql], env=env, capture_output=True, text=True, timeout=300)
        if p.returncode != 0:
            raise RuntimeError(f"psql trên {cluster} lỗi: {p.stderr.strip()[-400:]}")
        return p.stdout

    def verify(self, cluster: str, ledger: Ledger, incident: datetime) -> dict:
        refresh = subprocess.run(["bash", "-c", 'source scripts/azure/lib.sh; refresh_admin_ip "$1"', "lib", cluster],
                                 cwd=ROOT, timeout=120)
        if refresh.returncode != 0:
            raise RuntimeError(f"không cập nhật được quy tắc admin của {cluster}")
        out = self.psql(cluster, "SELECT id, encode(image_sha256, 'hex') FROM posts")
        rows = dict(line.split(",", 1) for line in out.splitlines() if line)
        entries = read_ledger(ledger.path)
        report = compare(entries, rows, incident)
        digest = self.psql(cluster, "SELECT md5(coalesce(string_agg(id::text || ':' || encode(image_sha256, 'hex'), "
                                    "',' ORDER BY id), '')) FROM posts").strip()
        if digest != content_digest(rows):
            raise RuntimeError("mã nội dung tính trong Postgres khác mã tính trong Python")
        client = direct(cluster, timeout=30)
        if client is None:
            raise RuntimeError(f"không lấy được IP của vm-dr-{cluster}")
        report.images_checked = len(rows)
        report.images_bad = check_images(rows, client.image)
        try:
            entry = post_one(client, ledger, max((e.seq for e in entries), default=0) + 1, "check")
            data = client.image(entry.post_id)
            functional = data is not None and hashlib.sha256(data).hexdigest() == entry.sha256
        except Exception as e:
            log(f"kiểm tra chức năng lỗi: {e}")
            functional = False
        log(f"kiểm tra {cluster}: {report.posts_restored}/{report.posts_acked} bài còn, thiếu {report.posts_missing} "
            f"(RPO {report.rpo_s} s), lỗ hổng {report.posts_holes}, ngoài sổ {report.posts_extra}, "
            f"mã nội dung {'khớp' if report.digest_match else 'KHÁC'}, ảnh hỏng {len(report.images_bad)}, "
            f"chức năng {'đạt' if functional else 'LỖI'}")
        return {"report": report, "digest": digest, "functional": functional}


ENV = AzureEnv()


def preflight(scenario: str) -> bool:
    public = ENV.health("public")
    if not public or public.get("status") != "ok" or public.get("read_only") is not False:
        log("cụm chính chưa phục vụ ghi qua tên miền chung")
        return False
    if scenario in WARM:
        standby = ENV.health("standby")
        if not standby or standby.get("status") != "ok" or standby.get("read_only") is not True:
            log("cụm dự phòng ấm chưa chạy ở chế độ chỉ đọc: dựng bằng standby-up.sh")
            return False
    return True


def read_steps(path: Path) -> dict[str, dict]:
    with path.open(newline="") as f:
        return {r["step"]: r for r in csv.DictReader(f)}


def run(scenario: str, run_id: str, iteration: int, decide: Callable[[], None]) -> bool:
    if not preflight(scenario):
        return False
    if ENV.sh([STEP_SH, run_id, "--new"]) != 0:
        return False
    run_dir = DRILLS / run_id
    ledger = Ledger(PRIVATE / "drill-ledger.csv")
    monitor = ENV.monitor(ledger, scenario in WARM)
    monitor.start()
    log(f"đăng 1 bài/giây trong {WARMUP_S:.0f} s trước sự cố")
    ENV.sleep(WARMUP_S)

    times: dict[str, datetime | None] = {"detected": None, "decided": None, "restored": None,
                                         "verify_start": None, "verified": None}
    status: dict[str, str] = {}
    outcome = None
    try:
        if ENV.sh([BREAK_SH, scenario]) != 0:
            log("lệnh phá lỗi")
            return False
        incident = ENV.now()
        times["detected"] = monitor.wait_detected(DETECT_TIMEOUT_S)
        monitor.stop_writer()
        if times["detected"] is None:
            log(f"không phát hiện được sự cố trong {DETECT_TIMEOUT_S} s")
            status["detect"] = "fail"
        else:
            status["detect"] = "ok"
            log(f"phát hiện sau {(times['detected'] - incident).total_seconds():.1f} s, chờ người trực quyết định")
            decide()
            times["decided"] = ENV.now()
            status["decide"] = "ok"
            target = (incident - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            for step, cmd in RUNBOOK[scenario]:
                if not cmd:
                    status[step] = "not_needed"
                    continue
                log(f"bước {step}: {' '.join(cmd)}")
                code = ENV.sh([STEP_SH, run_id, step, "--", *[target if c == TARGET else c for c in cmd]])
                status[step] = "ok" if code == 0 else "fail"
                if code != 0:
                    log(f"bước {step} lỗi {code}, dừng runbook")
                    break
            if all(status.get(step) in ("ok", "not_needed") for step, _ in RUNBOOK[scenario]):
                recorded = read_steps(run_dir / "steps.csv")
                times["restored"] = max(parse_time(recorded[s]["ended_at"]) for s, c in RUNBOOK[scenario] if c)
                times["verify_start"] = ENV.now()
                outcome = ENV.verify(SERVING[scenario], ledger, incident)
                times["verified"] = ENV.now()
    finally:
        monitor.stop()
        if hasattr(monitor, "save") and run_dir.exists():
            monitor.save(run_dir / "probes.csv")

    passed = outcome is not None and outcome["report"].ok and outcome["functional"]
    status["verify"] = "skipped" if outcome is None else ("ok" if passed else "fail")
    write(scenario, run_id, iteration, run_dir, incident, times, status, outcome, monitor, ledger, passed)
    log(f"{scenario} {'ĐẠT' if passed else 'KHÔNG ĐẠT'}")
    return passed


def write(scenario: str, run_id: str, iteration: int, run_dir: Path, incident: datetime,
          times: dict, status: dict, outcome: dict | None, monitor, ledger: Ledger, passed: bool) -> None:
    recorded = read_steps(run_dir / "steps.csv")

    def row(step: str, start, end) -> dict:
        return results.step_row(run_id, scenario, iteration, step, start, end, status.get(step, "skipped"))

    detect = row("detect", incident, times["detected"])
    if times["detected"] is not None:
        down = monitor.network_down_s(incident, times["detected"])
        detect["duration_s"] = f"{max(0.0, (times['detected'] - incident).total_seconds() - down):.1f}"
    rows = [detect, row("decide", times["detected"], times["decided"])]
    for step in ("infra", "restore", "switch"):
        r = recorded.get(step)
        if r:
            rows.append(row(step, parse_time(r["started_at"]), parse_time(r["ended_at"])))
        else:
            rows.append(row(step, None, None))
    rows.append(row("verify", times["verify_start"], times["verified"]))
    (run_dir / "steps.csv").unlink()
    results.append_rows(run_dir / "steps.csv", results.STEP_FIELDS, rows)

    report = outcome["report"] if outcome else None
    restored = times["restored"]
    run_row = {
        "run_id": run_id, "scenario": scenario, "iteration": iteration, "runner": platform.node(),
        "cpus": os.cpu_count(), "seed_posts": sum(e.source == "seed" for e in read_ledger(ledger.path)),
        "incident_at": results.iso(incident), "detected_at": results.iso(times["detected"]),
        "service_restored_at": results.iso(restored), "verified_at": results.iso(times["verified"]),
        "rto_s": "" if restored is None else f"{(restored - incident).total_seconds():.1f}",
        "result": "pass" if passed else "fail",
    }
    if report is not None:
        run_row.update({
            "posts_acked": report.posts_acked, "posts_restored": report.posts_restored,
            "posts_missing": report.posts_missing, "posts_missing_beyond_rpo": report.posts_missing_beyond_rpo,
            "posts_holes": report.posts_holes, "posts_extra": report.posts_extra, "rpo_s": report.rpo_s,
            "digest_match": str(report.digest_match).lower(), "content_digest": outcome["digest"],
            "images_checked": report.images_checked, "images_bad": len(report.images_bad),
            "functional_ok": str(outcome["functional"]).lower(),
        })
    results.append_rows(run_dir / "runs.csv", results.RUN_FIELDS, [run_row])


def wait_for_operator() -> None:
    input("Nhấn Enter khi đã quyết định khôi phục: ")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m scripts.dr.azure_drill",
                                description="Chạy một lần diễn tập D1 tới D5 trên Azure")
    p.add_argument("scenario", choices=sorted(RUNBOOK))
    p.add_argument("--run-id", required=True)
    p.add_argument("--iteration", type=int, default=1)
    p.add_argument("--auto-decide", action="store_true")
    a = p.parse_args(argv)
    decide = (lambda: None) if a.auto_decide else wait_for_operator
    return 0 if run(a.scenario, a.run_id, a.iteration, decide) else 1


if __name__ == "__main__":
    sys.exit(main())
