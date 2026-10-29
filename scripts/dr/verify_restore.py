from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shlex
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from scripts.dr.backup_check import _container, _pick
from scripts.dr.session_state import Session, read_session

DIGEST_SQL = ("SELECT md5(coalesce(string_agg(id::text || ':' || encode(image_sha256, 'hex'), ',' ORDER BY id), '')) "
              "FROM posts")
PAGE = 60


@dataclass
class ImageCheck:
    post_id: str
    expected_sha256: str
    actual_sha256: str | None


@dataclass
class VerifyReport:
    ok: bool
    missing_posts: int
    extra_posts: int
    digest_match: bool
    bad_images: list[str]


def compare(expected: Session, actual_count: int, actual_digest: str, image_checks: list[ImageCheck]) -> VerifyReport:
    bad = [c.post_id for c in image_checks if c.actual_sha256 != c.expected_sha256]
    if expected.post_count is None:
        return VerifyReport(ok=actual_count > 0 and not bad, missing_posts=0, extra_posts=0,
                            digest_match=True, bad_images=bad)
    missing = max(expected.post_count - actual_count, 0)
    extra = max(actual_count - expected.post_count, 0)
    digest_match = actual_digest == expected.content_digest
    return VerifyReport(ok=not missing and not extra and digest_match and not bad, missing_posts=missing,
                        extra_posts=extra, digest_match=digest_match, bad_images=bad)


def http_get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read()


def fetch_posts(api: str, get: Callable[[str], bytes] = http_get) -> list[dict]:
    posts: list[dict] = []
    before = None
    while True:
        url = f"{api}/v1/posts?limit={PAGE}" + (f"&before={before}" if before else "")
        page = json.loads(get(url))
        posts.extend(page["posts"])
        before = page.get("next")
        if not before:
            return posts


def check_images(api: str, posts: list[dict], sample: int, get: Callable[[str], bytes] = http_get) -> list[ImageCheck]:
    checks = []
    for p in random.sample(posts, min(sample, len(posts))):
        try:
            actual = hashlib.sha256(get(f"{api}/v1/posts/{p['id']}/image")).hexdigest()
        except OSError:
            actual = None
        checks.append(ImageCheck(p["id"], p["image_sha256"], actual))
    return checks


def store_unchanged(before: set[str], after: set[str]) -> bool:
    return after <= before


def _sas() -> dict[str, str]:
    return json.loads(os.environ["DRILL_READ_SAS_JSON"])


def list_store(sas: dict[str, str]) -> set[str]:
    return {b.name for b in _container(*_pick(sas, "drbackup", "cnpg")).list_blobs()}


def _psql(cmd: str, sql: str) -> str:
    return subprocess.run([*shlex.split(cmd), sql], check=True, capture_output=True, text=True).stdout.strip()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="So bản khôi phục của diễn tập với session.json trong kho sao lưu")
    p.add_argument("--list-store", type=Path, help="chỉ ghi danh sách tệp trong container cnpg rồi thoát")
    p.add_argument("--api", default="http://127.0.0.1:8080")
    p.add_argument("--psql", help="lệnh psql, câu SQL được thêm vào cuối")
    p.add_argument("--sample", type=int, default=50)
    p.add_argument("--store-before", type=Path)
    a = p.parse_args(argv)
    sas = _sas()
    if a.list_store:
        a.list_store.write_text("\n".join(sorted(list_store(sas))) + "\n", encoding="utf-8")
        return 0
    if not a.psql:
        p.error("cần --psql")

    expected = read_session(_container(*_pick(sas, "drbackup", "status")))
    if expected is None:
        print("không đọc được status/session.json", file=sys.stderr)
        return 1
    count = int(_psql(a.psql, "SELECT count(*) FROM posts"))
    digest = _psql(a.psql, DIGEST_SQL)
    report = compare(expected, count, digest, check_images(a.api, fetch_posts(a.api), a.sample))
    store_ok = True
    if a.store_before:
        before = set(a.store_before.read_text(encoding="utf-8").split())
        store_ok = store_unchanged(before, list_store(sas))
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps({"state": expected.state, "server_name": expected.server_name, "expected_posts": expected.post_count,
                      "actual_posts": count, "store_unchanged": store_ok, **asdict(report)}, ensure_ascii=False))
    return 0 if report.ok and store_ok else 1


if __name__ == "__main__":
    sys.exit(main())
