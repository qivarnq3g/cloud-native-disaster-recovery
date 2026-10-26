import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts" / "azure"
BASH = shutil.which("bash")

FAKE_TOOL = r"""#!/usr/bin/env bash
tool="$(basename "$0")"
echo "$tool $*" >> "$FAKE_DIR/calls.log"
if [ -n "${FAKE_FAIL_ON:-}" ] && [[ "$tool $*" == *"$FAKE_FAIL_ON"* ]]; then exit 1; fi
case "$tool $*" in
  "az vm show"*)
    for vm in $FAKE_VMS; do [[ "$*" == *"-n $vm"* ]] && { echo "$vm"; exit 0; }; done
    exit 3 ;;
  "az vm get-instance-view"*) echo "$FAKE_POWER_STATE" ;;
  "az vm list"*) echo 0 ;;
  "terraform"*"output -raw public_ip"*) echo 20.0.0.9 ;;
  "kubectl"*"count(*)"*) echo 20 ;;
  "kubectl"*"md5("*) echo 0123abcd ;;
esac
exit 0
"""


class FakeTools:
    def __init__(self, root: Path):
        self.root = root
        self.bin = root / "bin"
        self.bin.mkdir()
        for tool in ("az", "terraform", "kubectl", "velero", "curl", "ssh-keygen"):
            p = self.bin / tool
            p.write_text(FAKE_TOOL, newline="\n")
            p.chmod(0o755)
        self.session = None
        self.vms = []
        self.power_state = "PowerState/deallocated"
        self.fail_on = ""
        private = root / "private"
        private.mkdir()
        (private / "ssh_ed25519").write_text("fake")
        (private / "ssh_ed25519.pub").write_text("ssh-ed25519 AAAA fake")
        self.private = private

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
            "DR_FAKE_SESSION": status.as_posix(),
            "DR_PYTHON": Path(sys.executable).as_posix(),
            "DR_PRIVATE_DIR": self.private.as_posix(),
            "DR_DATA_DIR": (self.root / "data").as_posix(),
            "DR_SUFFIX": "abc123",
            "ADMIN_IP": "203.0.113.7",
            "DR_POLL_SECONDS": "0",
        }
        return subprocess.run([BASH, (SCRIPTS / script).as_posix(), *args], env=env,
                              capture_output=True, text=True, timeout=60)


@pytest.fixture
def fake_tools(tmp_path):
    if BASH is None:
        pytest.skip("cần bash")
    return FakeTools(tmp_path)


def test_start_refuses_when_session_running(fake_tools):
    fake_tools.session = {"state": "running", "cluster": "primary"}
    r = fake_tools.run("session-start.sh", "primary", "abc")
    assert r.returncode == 3, r.stderr
    assert "terraform" not in fake_tools.calls


def test_start_refuses_when_vm_still_exists(fake_tools):
    fake_tools.session = {"state": "stopped", "cluster": "primary"}
    fake_tools.vms = ["vm-dr-primary"]
    r = fake_tools.run("session-start.sh", "primary", "abc")
    assert r.returncode == 3, r.stderr
    assert "terraform" not in fake_tools.calls


def test_start_refuses_third_vm(fake_tools):
    fake_tools.vms = ["vm-dr-primary", "vm-dr-standby"]
    assert fake_tools.run("session-start.sh", "primary", "abc").returncode == 4


def test_start_refuses_before_creating_anything_when_later_steps_are_missing(fake_tools, monkeypatch):
    if (SCRIPTS / "install-software.sh").exists() and (SCRIPTS / "deploy-api.sh").exists():
        pytest.skip("đã có đủ script")
    r = fake_tools.run("session-start.sh", "primary", "abc")
    assert r.returncode == 5, r.stderr
    assert "terraform" not in fake_tools.calls


def test_stop_keeps_vm_when_backup_fails(fake_tools):
    fake_tools.session = {"state": "running", "cluster": "primary"}
    fake_tools.fail_on = "backups.postgresql.cnpg.io"
    r = fake_tools.run("session-stop.sh", "primary")
    assert r.returncode == 1
    assert "destroy" not in fake_tools.calls


def test_stop_keeps_vm_when_velero_fails(fake_tools):
    fake_tools.session = {"state": "running", "cluster": "primary"}
    fake_tools.fail_on = "velero backup create"
    r = fake_tools.run("session-stop.sh", "primary")
    assert r.returncode == 1
    assert "destroy" not in fake_tools.calls


def test_stop_records_backups_then_destroys(fake_tools):
    fake_tools.session = {"state": "running", "cluster": "primary"}
    r = fake_tools.run("session-stop.sh", "primary")
    assert r.returncode == 0, r.stderr
    doc = json.loads((fake_tools.root / "status" / "session.json").read_text())
    assert doc["state"] == "stopped" and doc["post_count"] == 20 and doc["content_digest"] == "0123abcd"
    assert doc["full_backup"].startswith("stop-") and doc["full_backup"] == doc["velero_backup"]
    calls = fake_tools.calls
    assert calls.index("velero backup create") < calls.index("destroy")


def test_pause_fails_if_only_stopped(fake_tools):
    fake_tools.power_state = "PowerState/stopped"
    assert fake_tools.run("session-pause.sh", "primary").returncode == 1


def test_pause_ok_when_deallocated(fake_tools):
    r = fake_tools.run("session-pause.sh", "primary")
    assert r.returncode == 0, r.stderr
    assert "az vm deallocate -g rg-dr-primary -n vm-dr-primary" in fake_tools.calls


def test_every_az_call_names_a_group(fake_tools):
    fake_tools.session = {"state": "running", "cluster": "primary"}
    fake_tools.run("session-stop.sh", "primary")
    fake_tools.run("session-pause.sh", "primary")
    fake_tools.run("session-start.sh", "standby", "abc")
    az = [line for line in fake_tools.calls.splitlines() if line.startswith("az ")]
    assert az and all(" -g rg-dr-" in line for line in az), az


def test_start_stops_when_session_file_cannot_be_read(fake_tools, monkeypatch):
    monkeypatch.setattr(sys, "executable", str(fake_tools.bin / "az"), raising=False)
    fake_tools.fail_on = "-m scripts.dr.session_state"
    r = fake_tools.run("session-start.sh", "primary", "abc")
    assert r.returncode == 1, (r.returncode, r.stderr)
    assert "terraform" not in fake_tools.calls
