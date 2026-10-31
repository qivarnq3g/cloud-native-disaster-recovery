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
        for tool in ("az", "terraform", "kubectl", "velero", "curl", "ssh-keygen"):
            p = self.bin / tool
            p.write_text(FAKE_TOOL, newline="\n")
            p.chmod(0o755)
        self.session = None
        self.vms = []
        self.power_state = "PowerState/deallocated"
        self.fail_on = ""
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
    assert doc["full_backup"] == "20261027T000000" and doc["velero_backup"].startswith("stop-")
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


@pytest.mark.parametrize("script", ["session-resume.sh", "session-stop.sh"])
def test_admin_rule_follows_current_ip_before_cluster_access(fake_tools, script):
    fake_tools.vms = ["vm-dr-primary"]
    fake_tools.session = {"state": "running", "cluster": "primary"}
    r = fake_tools.run(script, "primary")
    assert r.returncode == 0, r.stderr
    calls = fake_tools.calls
    rule = "az network nsg rule update -g rg-dr-primary --nsg-name vm-dr-primary-nsg -n admin --source-address-prefixes 203.0.113.7/32"
    assert rule in calls
    later = "kubectl" if script == "session-stop.sh" else "curl"
    assert calls.index(rule) < calls.index(later)


def test_stop_keeps_vm_when_backup_id_is_missing(fake_tools):
    fake_tools.session = {"state": "running", "cluster": "primary"}
    fake_tools.fail_on = "{.status.backupId}"
    r = fake_tools.run("session-stop.sh", "primary")
    assert r.returncode == 1 and "destroy" not in fake_tools.calls


STANDBY_STUBS = ["cluster-up.sh", "install-software.sh", "deploy-api.sh"]


def test_standby_up_refuses_when_primary_not_running(fake_tools):
    fake_tools.stubs = STANDBY_STUBS
    fake_tools.session = {"state": "stopped", "cluster": "primary"}
    assert fake_tools.run("standby-up.sh", "abc").returncode == 5
    assert "cluster-up.sh" not in fake_tools.calls


def test_standby_up_refuses_when_standby_exists(fake_tools):
    fake_tools.stubs = STANDBY_STUBS
    fake_tools.session = {"state": "running", "cluster": "primary"}
    fake_tools.vms = ["vm-dr-standby"]
    assert fake_tools.run("standby-up.sh", "abc").returncode == 3


def test_standby_up_installs_replica_from_primary_server(fake_tools):
    fake_tools.stubs = STANDBY_STUBS
    fake_tools.session = {"state": "running", "cluster": "primary", "server_name": "primary-202610300100"}
    r = fake_tools.run("standby-up.sh", "abc")
    assert r.returncode == 0, r.stderr
    calls = fake_tools.calls
    assert "install-software.sh standby standby-" in calls and "primary-202610300100" in calls
    assert "install-software.sh DR_DB_MODE=replica" in fake_tools.env_log
    assert "deploy-api.sh DR_DB_MODE= DR_READ_ONLY=true" in fake_tools.env_log
    assert (fake_tools.private / "standby-server").read_text().strip().startswith("standby-")
    assert fake_tools.session_doc()["cluster"] == "primary"


def test_standby_up_takes_full_backup_on_primary_before_building(fake_tools):
    fake_tools.stubs = STANDBY_STUBS
    fake_tools.session = {"state": "running", "cluster": "primary", "server_name": "primary-202610300100"}
    r = fake_tools.run("standby-up.sh", "abc")
    assert r.returncode == 0, r.stderr
    calls = fake_tools.calls
    refresh = calls.index("nsg rule update -g rg-dr-primary")
    backup = calls.index("kubectl -n dr-api wait --for=jsonpath={.status.phase}=completed backups.postgresql.cnpg.io/seed-")
    assert refresh < backup < calls.index("cluster-up.sh standby")


def test_standby_up_stops_before_building_when_full_backup_fails(fake_tools):
    fake_tools.stubs = STANDBY_STUBS
    fake_tools.session = {"state": "running", "cluster": "primary", "server_name": "primary-202610300100"}
    fake_tools.fail_on = "backups.postgresql.cnpg.io/seed-"
    assert fake_tools.run("standby-up.sh", "abc").returncode == 1
    assert "cluster-up.sh" not in fake_tools.calls


def test_standby_down_refreshes_admin_ip_first(fake_tools):
    fake_tools.vms = ["vm-dr-standby"]
    (fake_tools.private / "standby-server").write_text("standby-202610300100")
    r = fake_tools.run("standby-down.sh")
    assert r.returncode == 0, r.stderr
    calls = fake_tools.calls
    assert calls.index("nsg rule update -g rg-dr-standby") < calls.index("destroy")
    assert "cluster-standby.tfstate" in calls
    assert not (fake_tools.private / "standby-server").exists()


def test_standby_down_refuses_while_standby_is_the_live_cluster(fake_tools):
    fake_tools.session = {"state": "running", "cluster": "standby"}
    fake_tools.vms = ["vm-dr-standby"]
    assert fake_tools.run("standby-down.sh").returncode == 3
    assert "destroy" not in fake_tools.calls
