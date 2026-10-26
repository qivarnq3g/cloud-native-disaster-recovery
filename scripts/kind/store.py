from __future__ import annotations

import json
import secrets
import sys
import time
from pathlib import Path

IDENTITIES: dict[str, list[str]] = {
    "admin": ["Admin", "Read", "Write", "List", "Tagging"],
    "cnpg": ["Read:cnpg", "Write:cnpg", "List:cnpg"],
    "velero": ["Read:velero", "Write:velero", "List:velero"],
    "api-primary": ["Read:images", "Write:images"],
    "api-standby": ["Read:images-copy", "Write:images-copy", "Read:images-standby", "Write:images-standby"],
    "image-copy": ["Read:images", "List:images", "Read:images-copy", "Write:images-copy", "List:images-copy",
                   "Read:images-standby", "Write:images-standby", "List:images-standby"],
    "vault-writer": ["Write:vault"],
}

BUCKETS = ("cnpg", "velero", "images", "images-copy", "images-standby")
VAULT_BUCKET = "vault"
VAULT_RETENTION_DAYS = 7
ENDPOINT = "http://127.0.0.1:18333"


def new_credentials() -> dict:
    return {
        "identities": {name: {"access": f"{name}-{secrets.token_hex(4)}", "secret": secrets.token_hex(20)}
                       for name in IDENTITIES},
        "secret_code": secrets.token_urlsafe(24),
        "db_password": secrets.token_hex(16),
    }


def seaweed_config(creds: dict) -> dict:
    return {
        "identities": [
            {
                "name": name,
                "credentials": [{"accessKey": creds["identities"][name]["access"],
                                 "secretKey": creds["identities"][name]["secret"]}],
                "actions": actions,
            }
            for name, actions in IDENTITIES.items()
        ]
    }


def load(state_dir: Path) -> dict:
    return json.loads((state_dir / "credentials.json").read_text())


def init(state_dir: Path) -> dict:
    state_dir.mkdir(parents=True, exist_ok=True)
    state_dir.chmod(0o700)
    path = state_dir / "credentials.json"
    if path.exists():
        creds = load(state_dir)
    else:
        creds = new_credentials()
        path.write_text(json.dumps(creds, indent=1))
        path.chmod(0o600)
    code = state_dir / "secret-code"
    code.write_text(creds["secret_code"])
    code.chmod(0o600)
    s3 = state_dir / "s3.json"
    s3.write_text(json.dumps(seaweed_config(creds), indent=1))
    s3.chmod(0o644)
    return creds


def client(creds: dict, identity: str = "admin", endpoint: str = ENDPOINT):
    import boto3
    from botocore.config import Config

    ident = creds["identities"][identity]
    return boto3.client(
        "s3", endpoint_url=endpoint, region_name="us-east-1",
        aws_access_key_id=ident["access"], aws_secret_access_key=ident["secret"],
        config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 2},
                      request_checksum_calculation="when_required",
                      response_checksum_validation="when_required"),
    )


def wait_ready(s3, timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            s3.list_buckets()
            return
        except Exception:
            if time.monotonic() > deadline:
                raise
            time.sleep(1)


def create_buckets(s3) -> None:
    existing = {b["Name"] for b in s3.list_buckets().get("Buckets", [])}
    for name in BUCKETS:
        if name not in existing:
            s3.create_bucket(Bucket=name)
    if VAULT_BUCKET not in existing:
        s3.create_bucket(Bucket=VAULT_BUCKET, ObjectLockEnabledForBucket=True)
    s3.put_object_lock_configuration(
        Bucket=VAULT_BUCKET,
        ObjectLockConfiguration={
            "ObjectLockEnabled": "Enabled",
            "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Days": VAULT_RETENTION_DAYS}},
        },
    )


USAGE = 'Dòng lệnh:\n    python -m scripts.kind.store init <state_dir>      sinh khóa, credentials.json và s3.json\n    python -m scripts.kind.store buckets <state_dir>   tạo bucket (két có khóa chống xóa)\n    python -m scripts.kind.store get <state_dir> <identity> <access|secret>'


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) >= 2 and args[0] == "init":
        init(Path(args[1]))
        return 0
    if len(args) >= 2 and args[0] == "buckets":
        s3 = client(load(Path(args[1])))
        wait_ready(s3)
        create_buckets(s3)
        return 0
    if len(args) == 4 and args[0] == "get" and args[3] in ("access", "secret"):
        print(load(Path(args[1]))["identities"][args[2]][args[3]])
        return 0
    print(USAGE, file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main())
