from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from scripts.kind.verify import IMAGES_RPO_S
from scripts.vault.blob import download, list_blobs
from scripts.vault.pack import fetch_age, newest_pack_time

DIGEST_SQL = ("SELECT md5(coalesce(string_agg(id::text || ':' || encode(image_sha256, 'hex'), ',' ORDER BY id), '')) "
              "FROM posts")
IMAGES_SQL = "SELECT id::text || ':' || encode(image_sha256, 'hex') FROM posts ORDER BY id"


class DecryptError(Exception):
    pass


@dataclass
class VaultReport:
    ok: bool
    count_match: bool
    digest_match: bool
    missing_images: list[str]
    images_lost_within_rpo: list[str] = field(default_factory=list)


def created_at(image_name: str) -> datetime | None:
    try:
        u = uuid.UUID(image_name.rpartition("/")[2])
    except ValueError:
        return None
    if u.version != 7:
        return None
    return datetime.fromtimestamp((u.int >> 80) / 1000, UTC)


@dataclass
class Pack:
    manifest: dict
    image_hashes: dict[str, str] = field(default_factory=dict)


def plan_packs(names: list[str], server_name: str) -> list[str]:
    timed = []
    for name in names:
        when = newest_pack_time([name], server_name)
        if when is not None:
            timed.append((when, name))
    return [name for _, name in sorted(timed)]


def decrypt(age_bin: Path, key_file: Path, src: Path) -> Path:
    out = src.with_name(src.name.removesuffix(".age"))
    r = subprocess.run([str(age_bin), "-d", "-i", str(key_file), "-o", str(out), str(src)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        out.unlink(missing_ok=True)
        raise DecryptError(r.stderr.strip() or f"age thoát mã {r.returncode}")
    return out


def read_pack(tar: Path, dump_dest: Path | None) -> Pack:
    manifest: dict = {}
    hashes: dict[str, str] = {}
    with tarfile.open(tar) as t:
        for member in t:
            if not member.isfile():
                continue
            name = member.name
            if name == "manifest.json":
                manifest = json.loads(t.extractfile(member).read())
            elif name == "db.dump" and dump_dest is not None:
                with t.extractfile(member) as src, open(dump_dest, "wb") as out:
                    shutil.copyfileobj(src, out, 1 << 20)
            elif name.startswith("images/") and ".." not in name.split("/"):
                digest = hashlib.sha256()
                with t.extractfile(member) as src:
                    for chunk in iter(lambda: src.read(1 << 20), b""):
                        digest.update(chunk)
                hashes[name.removeprefix("images/")] = digest.hexdigest()
    return Pack(manifest, hashes)


def check(manifest: dict, restored_count: int, restored_digest: str, present_images: set[str],
          incident_at: datetime | None = None, images_rpo_s: float = IMAGES_RPO_S) -> VaultReport:
    count_match = int(manifest["post_count"]) == restored_count
    digest_match = manifest["content_digest"] == restored_digest
    missing = sorted(set(manifest["images"]) - present_images)
    recent = []
    if incident_at is not None:
        for name in missing:
            at = created_at(name)
            if at is not None and 0 <= (incident_at - at).total_seconds() <= images_rpo_s:
                recent.append(name)
    missing = [n for n in missing if n not in recent]
    return VaultReport(count_match and digest_match and not missing, count_match, digest_match, missing, recent)


def _vault(sas: dict[str, str]) -> tuple[str, str]:
    for url, token in sas.items():
        host = url.split("/")[2]
        if host.startswith("drvault") and url.rstrip("/").endswith("/vault"):
            return url.rstrip("/"), token.lstrip("?")
    raise SystemExit("DRILL_READ_SAS_JSON thiếu drvault*/vault")


def local_source(mirror: Path) -> tuple[list[str], Callable[[str, Path], None]]:
    from scripts.vault.offsite import latest_chain, local_packs

    names = latest_chain(list(local_packs(mirror)))
    if not names:
        raise SystemExit(f"{mirror} không có gói nào")
    return names, lambda name, dest: shutil.copyfile(mirror / name, dest)


def azure_source() -> tuple[list[str], Callable[[str, Path], None]]:
    from scripts.dr.backup_check import _container, _pick
    from scripts.dr.session_state import read_session

    sas = json.loads(os.environ["DRILL_READ_SAS_JSON"])
    session = read_session(_container(*_pick(sas, "drbackup", "status")))
    if session is None or not session.vault_pack:
        raise SystemExit("session.json chưa có vault_pack")
    server = session.vault_pack.split("/", 1)[0]
    vault_url, vault_sas = _vault(sas)
    names = plan_packs([b.name for b in list_blobs(vault_url, vault_sas, prefix=f"{server}/")], server)
    if session.vault_pack not in names:
        raise SystemExit(f"két không có gói {session.vault_pack}")
    return names[:names.index(session.vault_pack) + 1], lambda name, dest: download(vault_url, vault_sas, name, dest)


def _run(cmd: str, *args: str, stdin=None) -> str:
    return subprocess.run([*shlex.split(cmd), *args], check=True, capture_output=True, text=stdin is None,
                          stdin=stdin).stdout


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="D7: giải mã các gói trong két, khôi phục gói mới nhất, so với manifest")
    p.add_argument("--key", type=Path, required=True)
    p.add_argument("--psql", required=True)
    p.add_argument("--pg-restore", required=True)
    p.add_argument("--age", type=Path)
    p.add_argument("--work", type=Path)
    p.add_argument("--from-dir", type=Path)
    p.add_argument("--incident-at", type=datetime.fromisoformat,
                   help="giờ sự cố của lần chuyển gần nhất (ISO 8601); ảnh mất của bài tạo trong RPO ảnh trước đó không tính lỗi")
    a = p.parse_args(argv)
    if not a.age and not os.environ.get("AGE_SHA256"):
        p.error("cần --age hoặc biến môi trường AGE_SHA256 để tải và kiểm tra age")

    names, fetch = local_source(a.from_dir) if a.from_dir else azure_source()
    work = a.work or Path(tempfile.mkdtemp(prefix="vault-"))
    work.mkdir(parents=True, exist_ok=True)
    age_bin = a.age or fetch_age(work / "age", os.environ["AGE_SHA256"])
    started = time.monotonic()
    images: dict[str, str] = {}
    dump = work / "db.dump"
    newest: Pack | None = None
    for name in names:
        sealed = work / "pack.tar.age"
        fetch(name, sealed)
        tar = decrypt(age_bin, a.key, sealed)
        sealed.unlink()
        newest = read_pack(tar, dump if name == names[-1] else None)
        tar.unlink()
        images.update(newest.image_hashes)
    decrypted_s = time.monotonic() - started

    with open(dump, "rb") as f:
        _run(a.pg_restore, stdin=f)
    restored_s = time.monotonic() - started
    count = int(_run(a.psql, "SELECT count(*) FROM posts").strip())
    digest = _run(a.psql, DIGEST_SQL).strip()
    expected = {}
    for line in _run(a.psql, IMAGES_SQL).split():
        post_id, _, sha = line.partition(":")
        expected[f"original/{post_id}"] = sha
    present = {name for name, sha in expected.items() if images.get(name) == sha}
    report = check({**newest.manifest, "images": sorted(expected)}, count, digest, present,
                   incident_at=a.incident_at)
    print(json.dumps({**asdict(report), "packs": names, "posts": count, "images_in_packs": len(images),
                      "decrypt_s": round(decrypted_s, 1), "restore_s": round(restored_s, 1),
                      "manifest_created_at": newest.manifest.get("created_at")}, ensure_ascii=False))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
