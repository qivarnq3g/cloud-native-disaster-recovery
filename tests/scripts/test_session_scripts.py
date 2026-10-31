import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts" / "azure"


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


SEED_JSON = ('{"backup_id": "20261030T010203", "server_name": "primary-202610300100", '
             '"post_count": 20, "content_digest": "0123abcd"}')


def test_seed_refuses_when_session_not_running(fake_tools):
    fake_tools.session = {"state": "stopped", "cluster": "primary"}
    assert fake_tools.run("seed.sh").returncode == 3


def test_seed_refuses_non_empty_database(fake_tools):
    fake_tools.session = {"state": "running", "cluster": "primary"}
    fake_tools.post_count = 125
    assert fake_tools.run("seed.sh").returncode == 3
    assert "kind: Backup" not in fake_tools.applied_yaml


def test_reset_uses_recorded_backup_id(fake_tools):
    fake_tools.private.joinpath("seed.json").write_text(SEED_JSON)
    fake_tools.private.joinpath("seed-ledger.csv").write_text("seq,post_id,acked_at,sha256,source\n")
    fake_tools.session = {"state": "running", "cluster": "primary", "server_name": "primary-202610310000"}
    r = fake_tools.run("reset-seed.sh", "primary")
    assert r.returncode == 0, r.stderr
    yaml = fake_tools.applied_yaml
    assert "backupID: 20261030T010203" in yaml and "serverName: primary-202610300100" in yaml
    c = fake_tools.calls
    assert c.index("nsg rule update -g rg-dr-primary") < c.index("delete clusters.postgresql.cnpg.io/db")
    assert "rollout restart deploy/api" in c
    doc = fake_tools.session_doc()
    assert doc["server_name"].startswith("primary-2") and doc["server_name"] != "primary-202610310000"
    assert str(doc["post_count"]) == "20" and doc["content_digest"] == "0123abcd"
    assert fake_tools.private.joinpath("drill-ledger.csv").read_text().startswith("seq,post_id")


def test_reset_fails_when_content_differs_from_seed(fake_tools):
    fake_tools.private.joinpath("seed.json").write_text(SEED_JSON)
    fake_tools.private.joinpath("seed-ledger.csv").write_text("seq,post_id,acked_at,sha256,source\n")
    fake_tools.session = {"state": "running", "cluster": "primary"}
    fake_tools.post_count = 19
    assert fake_tools.run("reset-seed.sh", "primary").returncode == 1
    assert not fake_tools.private.joinpath("drill-ledger.csv").exists()


def test_reset_refuses_without_seed_record(fake_tools):
    fake_tools.session = {"state": "running", "cluster": "primary"}
    assert fake_tools.run("reset-seed.sh", "primary").returncode == 5
    assert "delete" not in fake_tools.calls


def test_reset_refuses_cluster_not_serving(fake_tools):
    fake_tools.private.joinpath("seed.json").write_text(SEED_JSON)
    fake_tools.session = {"state": "running", "cluster": "standby"}
    assert fake_tools.run("reset-seed.sh", "primary").returncode == 3
