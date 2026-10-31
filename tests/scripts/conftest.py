import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts" / "azure"
BASH = shutil.which("bash")

FAKE_TOOL = r"""#!/usr/bin/env bash
tool="$(basename "$0")"
echo "$tool $*" >> "$FAKE_DIR/calls.log"
[[ "$tool $*" == "kubectl"*" apply -f -"* ]] && cat >> "$FAKE_DIR/applied.yaml"
if [ -n "${FAKE_FAIL_ON:-}" ] && [[ "$tool $*" == *"$FAKE_FAIL_ON"* ]]; then exit 1; fi
case "$tool $*" in
  "az vm show -d"*) echo 20.0.0.8 ;;
  "az vm show"*)
    for vm in $FAKE_VMS; do [[ "$*" == *"-n $vm"* ]] && { echo "$vm"; exit 0; }; done
    exit 3 ;;
  "az vm get-instance-view"*) echo "$FAKE_POWER_STATE" ;;
  "az vm list"*) echo 0 ;;
  "az storage account or-policy list"*) echo pol-1 ;;
  "az storage blob list"*) echo 0 ;;
  "kubectl"*"pg_is_in_recovery()"*) echo "${FAKE_IN_RECOVERY:-f}" ;;
  "terraform"*"output -raw public_ip"*) echo 20.0.0.9 ;;
  "kubectl"*"count(*)"*) echo "${FAKE_POST_COUNT:-20}" ;;
  "kubectl"*"md5("*) echo 0123abcd ;;
  "kubectl"*"{.status.backupId}"*) echo 20261027T000000 ;;
esac
exit 0
"""


STUB_SCRIPT = r"""#!/usr/bin/env bash
echo "$(basename "$0") $*" >> "$FAKE_DIR/calls.log"
echo "$(basename "$0") DR_DB_MODE=${DR_DB_MODE:-} DR_READ_ONLY=${DR_READ_ONLY:-}" >> "$FAKE_DIR/env.log"
exit 0
"""


class FakeTools:
    def __init__(self, root: Path):
        self.root = root
        self.bin = root / "bin"
        self.bin.mkdir()
        for tool in ("az", "terraform", "kubectl", "velero", "curl", "ssh-keygen", "dns_switch"):
            p = self.bin / tool
            p.write_text(FAKE_TOOL, newline="\n")
            p.chmod(0o755)
        self.session = None
        self.vms = []
        self.power_state = "PowerState/deallocated"
        self.fail_on = ""
        self.in_recovery = "f"
        self.post_count = 20
        self.stubs: list[str] = []
        self.extra_env: dict[str, str] = {}
        private = root / "private"
        private.mkdir()
        (private / "ssh_ed25519").write_text("fake")
        (private / "ssh_ed25519.pub").write_text("ssh-ed25519 AAAA fake")
        self.private = private

    @property
    def env_log(self) -> str:
        log = self.root / "env.log"
        return log.read_text() if log.exists() else ""

    def session_doc(self) -> dict:
        return json.loads((self.root / "status" / "session.json").read_text())

    @property
    def applied_yaml(self) -> str:
        log = self.root / "applied.yaml"
        return log.read_text(encoding="utf-8") if log.exists() else ""

    @property
    def calls(self) -> str:
        log = self.root / "calls.log"
        return log.read_text() if log.exists() else ""

    def run(self, script: str, *args: str) -> subprocess.CompletedProcess:
        status = self.root / "status"
        status.mkdir(exist_ok=True)
        if self.session is not None:
            doc = {"state": None, "cluster": None, "server_name": "primary-202610270000",
                   "started_at": "2026-10-27T00:00:00Z", "stopped_at": None, "full_backup": None,
                   "velero_backup": None, "post_count": None, "content_digest": None}
            doc.update(self.session)
            (status / "session.json").write_text(json.dumps(doc))
        env = {
            **os.environ,
            "PATH": f"{self.bin.as_posix()}{os.pathsep}{os.environ['PATH']}",
            "FAKE_DIR": self.root.as_posix(),
            "FAKE_VMS": " ".join(self.vms),
            "FAKE_POWER_STATE": self.power_state,
            "FAKE_FAIL_ON": self.fail_on,
            "FAKE_IN_RECOVERY": self.in_recovery,
            "FAKE_POST_COUNT": str(self.post_count),
            "DR_DNS_SWITCH": (self.bin / "dns_switch").as_posix(),
            "DR_PROMOTE_TIMEOUT": "0",
            "DR_FAKE_SESSION": status.as_posix(),
            "DR_PYTHON": Path(sys.executable).as_posix(),
            "DR_PRIVATE_DIR": self.private.as_posix(),
            "DR_DATA_DIR": (self.root / "data").as_posix(),
            "DR_SUFFIX": "abc123",
            "ADMIN_IP": "203.0.113.7",
            "DR_POLL_SECONDS": "0",
        }
        if self.stubs:
            stub_dir = self.root / "stubs"
            stub_dir.mkdir(exist_ok=True)
            for name in self.stubs:
                (stub_dir / name).write_text(STUB_SCRIPT, newline="\n")
            env["DR_SCRIPT_DIR"] = stub_dir.as_posix()
        env.update(self.extra_env)
        return subprocess.run([BASH, (SCRIPTS / script).as_posix(), *args], env=env,
                              capture_output=True, text=True, timeout=60)


@pytest.fixture
def fake_tools(tmp_path):
    if BASH is None:
        pytest.skip("cần bash")
    return FakeTools(tmp_path)
