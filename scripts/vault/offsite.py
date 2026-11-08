from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from scripts.vault.blob import BlobInfo, download, list_blobs
from scripts.vault.pack import SUFFIX, newest_pack_time

PART = ".part"


def latest_chain(names: list[str]) -> list[str]:
    servers = {n.partition("/")[0] for n in names if "/" in n}
    newest = {s: t for s in servers if (t := newest_pack_time(names, s)) is not None}
    if not newest:
        return []
    server = max(newest, key=newest.__getitem__)
    timed = [(newest_pack_time([n], server), n) for n in names]
    return [n for t, n in sorted((t, n) for t, n in timed if t is not None)]


def to_download(remote: list[BlobInfo], local: dict[str, int]) -> list[str]:
    sizes = {b.name: b.size for b in remote}
    return [n for n in latest_chain(list(sizes)) if local.get(n) != sizes[n]]


def to_prune(local_names: list[str], chain: list[str]) -> list[str]:
    keep = set(chain)
    return sorted(n for n in local_names if n not in keep)


def local_packs(mirror: Path) -> dict[str, int]:
    return {p.relative_to(mirror).as_posix(): p.stat().st_size
            for p in mirror.rglob(f"*{SUFFIX}") if p.is_file()}


def pull(url: str, sas: str, mirror: Path,
         lister: Callable[[str, str], list[BlobInfo]] = list_blobs,
         downloader: Callable[[str, str, str, Path], None] = download) -> dict:
    mirror.mkdir(parents=True, exist_ok=True)
    for stale in mirror.rglob(f"*{PART}"):
        stale.unlink()
    remote = lister(url, sas)
    chain = latest_chain([b.name for b in remote])
    fetched = []
    for name in to_download(remote, local_packs(mirror)):
        dest = mirror / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + PART)
        try:
            downloader(url, sas, name, part)
        except BaseException:
            part.unlink(missing_ok=True)
            raise
        part.replace(dest)
        fetched.append(name)
    pruned = to_prune(list(local_packs(mirror)), chain)
    for name in pruned:
        (mirror / name).unlink()
    for folder in sorted((p for p in mirror.iterdir() if p.is_dir()), reverse=True):
        if not any(folder.iterdir()):
            folder.rmdir()
    return {"chain": chain, "downloaded": fetched, "pruned": pruned}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Kéo các gói mới nhất trong két về một thư mục ngoài Azure bằng SAS chỉ đọc")
    p.add_argument("--url", required=True)
    p.add_argument("--sas-file", type=Path, required=True)
    p.add_argument("--mirror", type=Path, required=True)
    a = p.parse_args(argv)
    report = pull(a.url, a.sas_file.read_text().strip(), a.mirror)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["chain"] else 1


if __name__ == "__main__":
    sys.exit(main())
