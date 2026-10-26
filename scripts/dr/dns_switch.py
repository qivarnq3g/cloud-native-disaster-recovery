"""Đổi bản ghi A của API qua API Cloudflare (bước 6 "chuyển lưu lượng" của mục 5.2 thiết kế).

Chỉ dùng thư viện chuẩn. Mã Cloudflare không bao giờ được in ra.
"""

from __future__ import annotations

import argparse
import csv
import http.client
import ipaddress
import json
import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

API = "https://api.cloudflare.com/client/v4"
DEFAULT_NAME = "api.dr.qivarn.id.vn"
TTL = 60
DOH_RESOLVERS = ("https://cloudflare-dns.com/dns-query", "https://dns.google/resolve")


class HealthCheckFailed(RuntimeError):
    pass


def urlopen_json(req: urllib.request.Request) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body or b"{}")
        except ValueError:
            return e.code, {"success": False, "errors": [{"message": body[:200].decode(errors="replace")}]}


class CloudflareDns:
    def __init__(self, token: str, zone_id: str, http: Callable[[urllib.request.Request], tuple[int, dict]] = urlopen_json):
        self.token = token
        self.zone_id = zone_id
        self._http = http

    def __repr__(self) -> str:
        return f"CloudflareDns(zone_id={self.zone_id!r})"

    def _call(self, method: str, url: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Content-Type", "application/json")
        status, payload = self._http(req)
        if status >= 300 or not payload.get("success", False):
            messages = "; ".join(e.get("message", "") for e in payload.get("errors", []))
            raise RuntimeError(f"Cloudflare {method} trả {status}: {messages}")
        return payload

    def _records_url(self) -> str:
        return f"{API}/zones/{self.zone_id}/dns_records"

    def get_a_record(self, name: str) -> dict:
        query = urllib.parse.urlencode({"type": "A", "name": name})
        records = [r for r in self._call("GET", f"{self._records_url()}?{query}")["result"]
                   if r.get("type") == "A" and r.get("name") == name]
        if len(records) != 1:
            raise LookupError(f"cần đúng một bản ghi A cho {name}, thấy {len(records)}")
        r = records[0]
        return {"id": r["id"], "content": r["content"], "ttl": r["ttl"], "proxied": r["proxied"]}

    def set_a_record(self, record_id: str, ip: str) -> None:
        self._call("PATCH", f"{self._records_url()}/{record_id}",
                   {"content": ip, "ttl": TTL, "proxied": False})


@dataclass
class SwitchResult:
    changed: bool
    started_at: datetime
    record_updated_at: datetime
    resolved_at: datetime | None
    old_ip: str = ""
    new_ip: str = ""


def _now() -> datetime:
    return datetime.now(UTC)


def switch(dns: CloudflareDns, name: str, ip: str, health: Callable[[str, str], bool],
           resolve: Callable[[str], set[str]], timeout_s: int = 300,
           sleep: Callable[[float], None] = time.sleep, poll_s: float = 5.0) -> SwitchResult:
    ipaddress.IPv4Address(ip)  # ValueError nếu không phải IPv4
    started_at = _now()
    if not health(name, ip):
        raise HealthCheckFailed(f"https://{ip}/healthz (SNI {name}) chưa trả 200, không đổi DNS")
    record = dns.get_a_record(name)
    if record["content"] == ip:
        now = _now()
        return SwitchResult(False, started_at, now, now, record["content"], ip)
    dns.set_a_record(record["id"], ip)
    updated_at = _now()
    deadline = time.monotonic() + timeout_s
    while True:
        if resolve(name) == {ip}:
            return SwitchResult(True, started_at, updated_at, _now(), record["content"], ip)
        if time.monotonic() >= deadline:
            return SwitchResult(True, started_at, updated_at, None, record["content"], ip)
        sleep(poll_s)


class _SniHTTPSConnection(http.client.HTTPSConnection):
    """Kết nối tới một IP nhưng bắt tay TLS với tên miền (SNI) và gửi Host là tên miền."""

    def __init__(self, ip: str, server_name: str, context: ssl.SSLContext, timeout: float):
        super().__init__(ip, 443, timeout=timeout, context=context)
        self._server_name = server_name
        self._ctx = context

    def connect(self) -> None:
        sock = socket.create_connection((self.host, self.port), self.timeout)
        self.sock = self._ctx.wrap_socket(sock, server_hostname=self._server_name)


def https_health(name: str, ip: str, insecure: bool = False, timeout: float = 10) -> bool:
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    conn = _SniHTTPSConnection(ip, name, ctx, timeout)
    try:
        conn.request("GET", "/healthz", headers={"Host": name})
        return conn.getresponse().status == 200
    except OSError:
        return False
    finally:
        conn.close()


def doh_resolve(name: str) -> set[str]:
    """Hỏi cả hai máy chủ DoH; trả hợp các IP. Chỉ khi cả hai cùng thấy một IP thì tập có một phần tử."""
    answers: set[str] = set()
    for base in DOH_RESOLVERS:
        req = urllib.request.Request(f"{base}?{urllib.parse.urlencode({'name': name, 'type': 'A'})}",
                                     headers={"Accept": "application/dns-json"})
        try:
            status, payload = urlopen_json(req)
        except OSError:
            return set()
        if status != 200:
            return set()
        found = {a["data"] for a in payload.get("Answer", []) if a.get("type") == 1}
        if not found:
            return set()
        answers |= found
    return answers


def _read_secret(env: str, file_name: str) -> str:
    value = os.environ.get(env)
    if value:
        return value.strip()
    path = Path.home() / ".dr" / file_name
    if not path.exists():
        sys.exit(f"thiếu {env} và {path}")
    return path.read_text(encoding="utf-8").strip()


def _iso(t: datetime | None) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ") if t else ""


def append_csv(path: Path, r: SwitchResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["started_at", "record_updated_at", "resolved_at", "old_ip", "new_ip"])
        w.writerow([_iso(r.started_at), _iso(r.record_updated_at), _iso(r.resolved_at), r.old_ip, r.new_ip])


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Đổi bản ghi A của API qua Cloudflare")
    p.add_argument("ip")
    p.add_argument("--name", default=DEFAULT_NAME)
    p.add_argument("--insecure", action="store_true", help="chấp nhận chứng chỉ chưa tin cậy khi kiểm tra /healthz")
    p.add_argument("--csv", type=Path)
    p.add_argument("--timeout", type=int, default=300)
    a = p.parse_args(argv)
    dns = CloudflareDns(_read_secret("CLOUDFLARE_API_TOKEN", "cloudflare-token"),
                        _read_secret("CLOUDFLARE_ZONE_ID", "cloudflare-zone-id"))
    try:
        r = switch(dns, a.name, a.ip, health=lambda n, ip: https_health(n, ip, a.insecure),
                   resolve=doh_resolve, timeout_s=a.timeout)
    except HealthCheckFailed as e:
        print(e, file=sys.stderr)
        return 1
    if a.csv:
        append_csv(a.csv, r)
    if not r.changed:
        print(f"{a.name} đã trỏ {a.ip}, không đổi")
        return 0
    if r.resolved_at is None:
        print(f"đã đổi {a.name}: {r.old_ip} -> {a.ip}, nhưng sau {a.timeout} s DoH chưa thấy IP mới", file=sys.stderr)
        return 2
    print(f"đã đổi {a.name}: {r.old_ip} -> {a.ip}, DoH thấy IP mới sau "
          f"{(r.resolved_at - r.record_updated_at).total_seconds():.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
