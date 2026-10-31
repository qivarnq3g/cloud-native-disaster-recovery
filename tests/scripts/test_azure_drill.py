import csv
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts.dr import azure_drill
from scripts.dr.azure_drill import RUNBOOK, run
from scripts.kind.verify import compare


@dataclass
class StepView:
    started_at: str
    ended_at: str
    duration_s: float
    result: str


class FakeMonitor:
    def __init__(self, env):
        self.env = env
        self.writer_stopped = False

    def start(self):
        pass

    def wait_detected(self, timeout):
        if self.env.never_detect:
            return None
        self.env.clock += timedelta(seconds=5 + self.env.control_down_for)
        return self.env.clock

    def network_down_s(self, start, end):
        return float(self.env.control_down_for)

    def stop_writer(self):
        self.writer_stopped = True

    def stop(self):
        pass


class FakeEnv:
    def __init__(self, drills: Path):
        self.drills = drills
        self.clock = datetime(2026, 10, 31, 8, 0, tzinfo=UTC)
        self.public_health = {"status": "ok", "read_only": False}
        self.standby_health = {"status": "ok", "read_only": True}
        self.broke = False
        self.never_detect = False
        self.control_down_for = 0
        self.fail_step = None
        self.commands: list[list[str]] = []
        self.verified_on = None
        self.verify_ok = True

    def now(self):
        return self.clock

    def sleep(self, seconds):
        self.clock += timedelta(seconds=seconds)

    def advance(self, seconds):
        return lambda: self.sleep(seconds)

    def health(self, target):
        return self.public_health if target == "public" else self.standby_health

    def monitor(self, ledger, with_standby):
        self.with_standby = with_standby
        return FakeMonitor(self)

    def sh(self, cmd, extra_env=None):
        self.commands.append(list(cmd))
        name = Path(cmd[0]).name
        if name == "break.sh":
            self.broke = True
            return 0
        run_dir = self.drills / cmd[1]
        if cmd[2] == "--new":
            run_dir.mkdir(parents=True)
            (run_dir / "steps.csv").write_text("step,started_at,ended_at,result\n")
            return 0
        step, start = cmd[2], self.clock
        self.clock += timedelta(seconds=30)
        code = 1 if step == self.fail_step else 0
        with (run_dir / "steps.csv").open("a") as f:
            f.write(f"{step},{azure_drill.results.iso(start)},{azure_drill.results.iso(self.clock)},"
                    f"{'fail' if code else 'ok'}\n")
        return code

    def verify(self, cluster, ledger, incident):
        self.verified_on = cluster
        return {"report": compare([], {}, incident), "digest": "d41d8cd98f00b204e9800998ecf8427e",
                "functional": self.verify_ok}

    def steps(self, run_id):
        with (self.drills / run_id / "steps.csv").open(newline="") as f:
            return {r["step"]: StepView(r["started_at"], r["ended_at"], float(r["duration_s"] or 0), r["result"])
                    for r in csv.DictReader(f)}

    def run_row(self, run_id):
        with (self.drills / run_id / "runs.csv").open(newline="") as f:
            return next(csv.DictReader(f))


@pytest.fixture
def fake_env(tmp_path, monkeypatch):
    env = FakeEnv(tmp_path / "drills")
    monkeypatch.setattr(azure_drill, "ENV", env)
    monkeypatch.setattr(azure_drill, "DRILLS", env.drills)
    monkeypatch.setattr(azure_drill, "PRIVATE", tmp_path / "private")
    return env


def test_runbook_covers_three_steps_for_each_scenario():
    for s in ("D1", "D2", "D3", "D4", "D5"):
        assert [step for step, _ in RUNBOOK[s]] == ["infra", "restore", "switch"]


def test_d4_cold_copies_images():
    assert any("DR_IMAGES_FROM_COPY=true" in " ".join(cmd) for _, cmd in RUNBOOK["D4"])
    assert not any("DR_IMAGES_FROM_COPY=true" in " ".join(cmd) for _, cmd in RUNBOOK["D2"])


def test_d1_needs_no_infra_or_switch():
    steps = dict(RUNBOOK["D1"])
    assert steps["infra"] == [] and steps["switch"] == []


def test_run_refuses_warm_scenario_without_standby(fake_env):
    fake_env.standby_health = None
    assert run("D3", "r1", 1, decide=lambda: None) is False and fake_env.broke is False


def test_run_refuses_warm_scenario_when_standby_writable(fake_env):
    fake_env.standby_health = {"status": "ok", "read_only": False}
    assert run("D5", "r1", 1, decide=lambda: None) is False and fake_env.broke is False


def test_run_refuses_when_primary_down(fake_env):
    fake_env.public_health = None
    assert run("D2", "r1", 1, decide=lambda: None) is False and fake_env.broke is False


def test_decide_time_is_recorded_between_detect_and_infra(fake_env):
    assert run("D2", "r1", 1, decide=fake_env.advance(seconds=42)) is True
    steps = fake_env.steps("r1")
    assert steps["decide"].duration_s == 42 and steps["decide"].ended_at <= steps["infra"].started_at


def test_network_outage_seconds_excluded_from_detect(fake_env):
    fake_env.control_down_for = 10
    run("D2", "r1", 1, decide=lambda: None)
    assert fake_env.steps("r1")["detect"].duration_s < 15


def test_steps_csv_has_kind_columns_and_all_six_steps(fake_env):
    run("D2", "r1", 1, decide=lambda: None)
    with (fake_env.drills / "r1" / "steps.csv").open(newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == azure_drill.results.STEP_FIELDS
        assert [r["step"] for r in reader] == ["detect", "decide", "infra", "restore", "switch", "verify"]


def test_d3_marks_infra_not_needed_and_verifies_standby(fake_env):
    assert run("D3", "r1", 1, decide=lambda: None) is True
    steps = fake_env.steps("r1")
    assert steps["infra"].result == "not_needed" and steps["restore"].result == "ok"
    assert fake_env.verified_on == "standby" and fake_env.with_standby is True


def test_d1_restores_to_one_second_before_incident(fake_env):
    run("D1", "r1", 1, decide=lambda: None)
    incident = datetime(2026, 10, 31, 8, 1, 30, tzinfo=UTC)
    restore = next(c for c in fake_env.commands if len(c) > 2 and c[2] == "restore")
    assert restore[-1] == (incident - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert fake_env.verified_on == "primary"


def test_failed_step_stops_runbook_and_fails_run(fake_env):
    fake_env.fail_step = "restore"
    assert run("D2", "r1", 1, decide=lambda: None) is False
    assert not any(len(c) > 2 and c[2] == "switch" for c in fake_env.commands)
    assert fake_env.verified_on is None
    assert fake_env.run_row("r1")["result"] == "fail"


def test_undetected_incident_fails_run(fake_env):
    fake_env.never_detect = True
    assert run("D2", "r1", 1, decide=lambda: None) is False
    assert not any(len(c) > 2 and c[2] == "infra" for c in fake_env.commands)


def test_runs_csv_records_rto_from_incident_to_service_restored(fake_env):
    run("D2", "r1", 1, decide=fake_env.advance(seconds=42))
    row = fake_env.run_row("r1")
    assert row["result"] == "pass" and row["scenario"] == "D2"
    assert float(row["rto_s"]) == 5 + 42 + 3 * 30


def test_break_script_actions(fake_tools):
    fake_tools.run("break.sh", "D1")
    assert "kubectl delete namespace dr-api --wait=false" in fake_tools.calls
    fake_tools.run("break.sh", "D2")
    assert "az vm delete -g rg-dr-primary -n vm-dr-primary --yes --force-deletion true --no-wait" in fake_tools.calls
    fake_tools.run("break.sh", "D4")
    assert "az group delete -n rg-dr-primary --yes --no-wait" in fake_tools.calls
    assert "splitbind" not in fake_tools.calls


def test_break_script_rejects_unknown_scenario(fake_tools):
    assert fake_tools.run("break.sh", "D9").returncode == 64
    assert "delete" not in fake_tools.calls
