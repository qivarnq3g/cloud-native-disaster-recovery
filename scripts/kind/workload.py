"""Tải giả lập của script đo (mục 5.1 và 5.4 thiết kế): bộ dữ liệu mẫu và đăng 1 bài mỗi giây.

Bài nào API xác nhận đã nhận thì ghi vào sổ (`ledger.csv`): số thứ tự, mã bài, giờ xác nhận,
mã băm ảnh. Bước kiểm tra sau khôi phục so cơ sở dữ liệu với sổ này.

Dòng lệnh:
    python -m scripts.kind.workload seed --api URL --code-file F --ledger F --count 1000
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import struct
import threading
import time
import urllib.error
import urllib.request
import uuid
import zlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

LEDGER_FIELDS = ["seq", "post_id", "acked_at", "sha256", "source"]


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def make_png(seed: int, side: int = 256) -> bytes:
    """Ảnh PNG nhiễu ngẫu nhiên, khó nén nên cạnh 256 cho khoảng 200 KB như bộ mẫu."""
    rng = random.Random(seed)
    raw = b"".join(b"\x00" + rng.randbytes(side * 3) for _ in range(side))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", side, side, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 1)) + chunk(b"IEND", b"")


def multipart(fields: dict[str, str], file_field: str, filename: str, content: bytes,
              content_type: str) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n".encode() + content + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class ApiClient:
    def __init__(self, base: str, code: str = "", timeout: float = 5):
        self.base = base.rstrip("/")
        self.code = code
        self.timeout = timeout

    def _request(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None,
                 timeout: float | None = None) -> tuple[int, bytes]:
        req = urllib.request.Request(self.base + path, data=body, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def healthz(self, timeout: float = 2) -> tuple[int, dict]:
        status, body = self._request("GET", "/healthz", timeout=timeout)
        try:
            return status, json.loads(body)
        except ValueError:
            return status, {}

    def create_post(self, title: str, image: bytes, key: str | None = None) -> dict:
        body, ctype = multipart(
            {"idempotency_key": key or str(uuid.uuid4()), "title": title, "description": "kind"},
            "image", "image.png", image, "image/png",
        )
        status, data = self._request("POST", "/v1/posts", body,
                                     {"Content-Type": ctype, "Authorization": f"Bearer {self.code}"})
        if status not in (200, 201):
            raise RuntimeError(f"POST /v1/posts trả {status}: {data[:200]!r}")
        return json.loads(data)

    def image(self, post_id: str) -> bytes | None:
        status, data = self._request("GET", f"/v1/posts/{post_id}/image", timeout=30)
        return data if status == 200 else None


@dataclass
class LedgerEntry:
    seq: int
    post_id: str
    acked_at: str
    sha256: str
    source: str


class Ledger:
    """Sổ ghi các bài đã được xác nhận, ghi thêm từng dòng nên dừng giữa chừng vẫn còn."""

    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        if not path.exists() or path.stat().st_size == 0:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", newline="") as f:
                csv.writer(f, lineterminator="\n").writerow(LEDGER_FIELDS)

    def append(self, entry: LedgerEntry) -> None:
        with self.lock, self.path.open("a", newline="") as f:
            csv.writer(f, lineterminator="\n").writerow([entry.seq, entry.post_id, entry.acked_at, entry.sha256, entry.source])

    def next_seq(self) -> int:
        return max((e.seq for e in read_ledger(self.path)), default=0) + 1


def read_ledger(path: Path) -> list[LedgerEntry]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return [LedgerEntry(int(r["seq"]), r["post_id"], r["acked_at"], r["sha256"], r["source"])
                for r in csv.DictReader(f)]


def post_one(api: ApiClient, ledger: Ledger, seq: int, source: str) -> LedgerEntry:
    image = make_png(seq)
    post = api.create_post(f"{source} {seq}", image)
    sha = hashlib.sha256(image).hexdigest()
    if post["image_sha256"] != sha:
        raise RuntimeError(f"API trả mã băm {post['image_sha256']} khác ảnh đã gửi {sha}")
    entry = LedgerEntry(seq, post["id"], utc_now(), sha, source)
    ledger.append(entry)
    return entry


def seed(api: ApiClient, ledger: Ledger, count: int, workers: int = 8) -> None:
    start = ledger.next_seq()
    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(lambda s: post_one(api, ledger, s, "seed"), range(start, start + count)))


class Writer(threading.Thread):
    """Đăng đúng 1 bài mỗi giây (mục 5.4) tới khi được dừng; lần đăng hỏng chỉ được đếm."""

    def __init__(self, api: ApiClient, ledger: Ledger, interval: float = 1.0):
        super().__init__(daemon=True)
        self.api, self.ledger, self.interval = api, ledger, interval
        self.stop_event = threading.Event()
        self.acked = 0
        self.failed = 0
        self.seq = ledger.next_seq()

    def run(self) -> None:
        next_at = time.monotonic()
        while not self.stop_event.is_set():
            seq, self.seq = self.seq, self.seq + 1
            try:
                post_one(self.api, self.ledger, seq, "writer")
                self.acked += 1
            except Exception:
                self.failed += 1
            next_at += self.interval
            self.stop_event.wait(max(0.0, next_at - time.monotonic()))

    def stop(self) -> None:
        self.stop_event.set()
        self.join(timeout=10)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m scripts.kind.workload")
    p.add_argument("command", choices=["seed"])
    p.add_argument("--api", required=True)
    p.add_argument("--code-file", type=Path, required=True)
    p.add_argument("--ledger", type=Path, required=True)
    p.add_argument("--count", type=int, default=1000)
    a = p.parse_args(argv)
    api = ApiClient(a.api, a.code_file.read_text().strip(), timeout=30)
    seed(api, Ledger(a.ledger), a.count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
