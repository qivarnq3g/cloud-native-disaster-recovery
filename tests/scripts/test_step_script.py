import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
STEP = REPO / "scripts" / "azure" / "step.sh"
BASH = shutil.which("bash")


@pytest.fixture
def tmp_data(tmp_path):
    if BASH is None:
        pytest.skip("cần bash")
    private = tmp_path / "private"
    private.mkdir()
    (private / "ssh_ed25519").write_text("fake")
    os.environ["STEP_TEST_ROOT"] = tmp_path.as_posix()
    yield tmp_path / "data"
    os.environ.pop("STEP_TEST_ROOT")


def run_step(*args):
    root = Path(os.environ["STEP_TEST_ROOT"])
    env = {
        **os.environ,
        "DR_PYTHON": Path(sys.executable).as_posix(),
        "DR_PRIVATE_DIR": (root / "private").as_posix(),
        "DR_DATA_DIR": (root / "data").as_posix(),
        "DR_SUFFIX": "abc123",
    }
    return subprocess.run([BASH, STEP.as_posix(), *args], env=env, capture_output=True, text=True, timeout=60)


def read_steps(data, run_id):
    with open(data / "drills" / run_id / "steps.csv", newline="") as f:
        return list(csv.DictReader(f))


def test_records_ok_and_passes_exit_code(tmp_data):
    assert run_step("r1", "--new").returncode == 0
    assert run_step("r1", "restore", "--", "true").returncode == 0
    assert run_step("r1", "verify", "--", "false").returncode == 1
    rows = read_steps(tmp_data, "r1")
    assert [(r["step"], r["result"]) for r in rows] == [("restore", "ok"), ("verify", "fail")]
    assert all(r["started_at"].endswith("Z") and r["ended_at"] >= r["started_at"] for r in rows)


def test_passes_through_non_trivial_exit_code(tmp_data):
    run_step("r1", "--new")
    assert run_step("r1", "infra", "--", "bash", "-c", "exit 7").returncode == 7


def test_unknown_step_is_refused(tmp_data):
    run_step("r1", "--new")
    assert run_step("r1", "deploy", "--", "true").returncode == 64


def test_new_refuses_existing_run(tmp_data):
    run_step("r1", "--new")
    assert run_step("r1", "--new").returncode == 3


def test_step_without_new_run_is_refused(tmp_data):
    assert run_step("r2", "restore", "--", "true").returncode == 3
