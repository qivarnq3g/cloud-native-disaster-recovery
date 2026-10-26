"""Đọc, ghi hai tệp trạng thái trong container `status` của kho sao lưu.

- `session.json`: phiên đang chạy hay đã tắt, và các bản sao lưu lúc tắt phiên.
- `sas-expiry.json`: ngày hết hạn của từng mã SAS (`issue-sas.sh` ghi).

Dòng lệnh (dùng trong script bash):
    python -m scripts.dr.session_state get <field>
    python -m scripts.dr.session_state set <field>=<value>...   (giá trị rỗng là null)
    python -m scripts.dr.session_state sas-expiry <name> <iso>
Xác thực bằng `BACKUP_ACCOUNT` và `BACKUP_ACCOUNT_KEY`. Khi có `DR_FAKE_SESSION` (thư mục) thì
đọc ghi tệp trong thư mục đó thay cho Azure, dùng cho kiểm thử script.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path

SESSION_BLOB = "session.json"
SAS_EXPIRY_BLOB = "sas-expiry.json"
STATES = ("running", "stopped")


@dataclass
class Session:
    state: str
    cluster: str
    server_name: str
    started_at: str
    stopped_at: str | None = None
    full_backup: str | None = None
    velero_backup: str | None = None
    post_count: int | None = None
    content_digest: str | None = None

    def __post_init__(self) -> None:
        if self.state not in STATES:
            raise ValueError(f"state phải là một trong {STATES}, không phải {self.state!r}")
        if self.post_count is not None:
            self.post_count = int(self.post_count)


def _read_json(client, name: str) -> dict | None:
    from azure.core.exceptions import ResourceNotFoundError

    try:
        return json.loads(client.get_blob_client(name).download_blob().readall())
    except ResourceNotFoundError:
        return None


def _write_json(client, name: str, doc: dict) -> None:
    client.get_blob_client(name).upload_blob(json.dumps(doc, indent=1).encode(), overwrite=True)


def read_session(client) -> Session | None:
    doc = _read_json(client, SESSION_BLOB)
    return Session(**doc) if doc is not None else None


def write_session(client, s: Session) -> None:
    _write_json(client, SESSION_BLOB, asdict(s))


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def read_sas_expiry(client) -> dict[str, datetime]:
    return {k: _parse_time(v) for k, v in (_read_json(client, SAS_EXPIRY_BLOB) or {}).items()}


def merge_sas_expiry(client, name: str, expiry: datetime) -> None:
    doc = _read_json(client, SAS_EXPIRY_BLOB) or {}
    doc[name] = expiry.strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_json(client, SAS_EXPIRY_BLOB, doc)


class _DirBlob:
    def __init__(self, path: Path):
        self.path = path

    def download_blob(self):
        from azure.core.exceptions import ResourceNotFoundError

        if not self.path.exists():
            raise ResourceNotFoundError(str(self.path))
        data = self.path.read_bytes()
        return type("Download", (), {"readall": lambda _: data})()

    def upload_blob(self, data: bytes, overwrite: bool = False) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(data)


class DirContainer:
    """Container giả trên đĩa cho kiểm thử: mỗi blob là một tệp."""

    def __init__(self, root: Path):
        self.root = root

    def get_blob_client(self, name: str) -> _DirBlob:
        return _DirBlob(self.root / name)


def status_container():
    fake = os.environ.get("DR_FAKE_SESSION")
    if fake:
        return DirContainer(Path(fake))
    from azure.storage.blob import ContainerClient

    account = os.environ["BACKUP_ACCOUNT"]
    return ContainerClient(f"https://{account}.blob.core.windows.net", "status",
                           credential={"account_name": account, "account_key": os.environ["BACKUP_ACCOUNT_KEY"]})


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print(__doc__, file=sys.stderr)
        return 64
    client = status_container()
    cmd, rest = args[0], args[1:]
    if cmd == "get" and len(rest) == 1:
        s = read_session(client)
        value = getattr(s, rest[0]) if s is not None else None
        print("" if value is None else value)
        return 0
    if cmd == "set" and rest:
        names = {f.name for f in fields(Session)}
        current = read_session(client)
        doc = asdict(current) if current is not None else {}
        for pair in rest:
            key, sep, value = pair.partition("=")
            if not sep or key not in names:
                print(f"không hiểu {pair!r}; trường hợp lệ: {sorted(names)}", file=sys.stderr)
                return 64
            doc[key] = value or None
        write_session(client, Session(**doc))
        return 0
    if cmd == "sas-expiry" and len(rest) == 2:
        merge_sas_expiry(client, rest[0], _parse_time(rest[1]))
        return 0
    print(__doc__, file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main())
