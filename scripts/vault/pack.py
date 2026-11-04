from __future__ import annotations

import argparse
import errno
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from scripts.vault.blob import BlobInfo, download, list_blobs, upload_new

AGE_VERSION = "v1.2.1"
AGE_URL = f"https://github.com/FiloSottile/age/releases/download/{AGE_VERSION}/age-{AGE_VERSION}-linux-amd64.tar.gz"
STAMP = "%Y%m%dT%H%M%SZ"
SUFFIX = ".tar.age"


def pack_name(server_name: str, at: datetime) -> str:
    return f"{server_name}/{at.strftime(STAMP)}{SUFFIX}"


def newest_pack_time(names: list[str], server_name: str) -> datetime | None:
    times = []
    for name in names:
        folder, _, leaf = name.partition("/")
        if folder != server_name or not leaf.endswith(SUFFIX):
            continue
        try:
            times.append(datetime.strptime(leaf[:-len(SUFFIX)], STAMP).replace(tzinfo=UTC))
        except ValueError:
            continue
    return max(times, default=None)


def select_images(images: list[BlobInfo], since: datetime | None) -> list[str]:
    return sorted(b.name for b in images if since is None or b.last_modified > since)


def seal_pack(age_bin: Path, recipients_file: Path, out: Path, dump: Path, image_names: list[str],
              fetch: Callable[[str, Path], None], velero: Path, manifest: dict, scratch: Path) -> None:
    cmd = [str(age_bin), "-R", str(recipients_file), "-o", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    failure: OSError | None = None
    try:
        with tarfile.open(fileobj=proc.stdin, mode="w|") as t:
            t.add(dump, arcname="db.dump")
            for name in image_names:
                held = scratch / "image"
                fetch(name, held)
                t.add(held, arcname=f"images/{name}")
                held.unlink()
            t.add(velero, arcname=f"velero/{velero.name}")
            body = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
            info = tarfile.TarInfo("manifest.json")
            info.size = len(body)
            info.mtime = int(datetime.now(UTC).timestamp())
            t.addfile(info, io.BytesIO(body))
    except OSError as e:
        failure = e
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass
    pipe_closed = isinstance(failure, BrokenPipeError) or getattr(failure, "errno", None) == errno.EINVAL
    if failure is not None and not pipe_closed:
        proc.kill()
        proc.wait()
        out.unlink(missing_ok=True)
        raise failure
    if proc.wait() != 0:
        out.unlink(missing_ok=True)
        raise subprocess.CalledProcessError(proc.returncode, cmd) from failure
    if failure is not None:
        raise failure


def fetch_age(dest: Path, sha256: str, http=urllib.request.urlopen) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / "age.tar.gz"
    with http(AGE_URL, timeout=120) as r, open(archive, "wb") as out:
        shutil.copyfileobj(r, out, 1 << 20)
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual != sha256.lower():
        archive.unlink()
        raise ValueError(f"mã băm age sai: {actual}, cần {sha256}")
    binary = dest / "age-bin"
    with tarfile.open(archive) as t:
        member = t.getmember("age/age")
        with t.extractfile(member) as src, open(binary, "wb") as out:
            shutil.copyfileobj(src, out)
    binary.chmod(0o755)
    archive.unlink()
    return binary


def _env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"thiếu biến môi trường {name}")
    return value


def run(work: Path, now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> str:
    created = now().replace(microsecond=0)
    server = _env("SERVER_NAME")
    vault_url, vault_sas = _env("VAULT_CONTAINER_URL"), _env("VAULT_SAS")
    image_url, image_sas = _env("IMAGE_CONTAINER_URL"), _env("IMAGE_SAS")
    velero_url, velero_sas = _env("VELERO_CONTAINER_URL"), _env("VELERO_SAS")
    velero_backup = _env("VELERO_BACKUP")
    dump = work / "db.dump"
    if not dump.is_file():
        raise SystemExit(f"không thấy {dump}")

    since = newest_pack_time([b.name for b in list_blobs(vault_url, vault_sas, prefix=f"{server}/")], server)
    names = select_images(list_blobs(image_url, image_sas), since)
    velero = work / f"{velero_backup}.tar.gz"
    download(velero_url, velero_sas, f"backups/{velero_backup}/{velero_backup}.tar.gz", velero)

    manifest = {
        "created_at": created.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "server_name": server,
        "post_count": int(_env("POST_COUNT")),
        "content_digest": _env("CONTENT_DIGEST"),
        "images": names,
        "images_since": since.strftime("%Y-%m-%dT%H:%M:%SZ") if since else None,
        "velero_backup": velero_backup,
    }
    age_bin = fetch_age(work / "age", _env("AGE_SHA256"))
    scratch = work / "scratch"
    scratch.mkdir(exist_ok=True)
    sealed = work / "pack.tar.age"
    seal_pack(age_bin, Path(_env("RECIPIENTS_FILE")), sealed, dump, names,
              lambda name, dest: download(image_url, image_sas, name, dest), velero, manifest, scratch)
    scratch.rmdir()
    velero.unlink()
    name = pack_name(server, created)
    upload_new(vault_url, vault_sas, name, sealed)
    sealed.unlink()
    return name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gói bản xuất, ảnh mới và bản Velero, mã hóa age, tải lên két")
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args(argv)
    print(run(args.work))
    return 0


if __name__ == "__main__":
    sys.exit(main())
