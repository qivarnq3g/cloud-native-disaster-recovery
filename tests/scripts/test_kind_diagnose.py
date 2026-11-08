import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")

KUBECTL = r"""#!/usr/bin/env bash
echo "$*" >> "$STUB_LOG"
case "$*" in
  *"get pods -A --no-headers"*)
    echo "cnpg-system   barman-cloud-586ff89c44-xrzgf   0/1   ContainerCreating   0   5m35s"
    echo "cnpg-system   cnpg-cloudnative-pg-7b5f5d7b65-d8cnp   1/1   Running   0   5m46s"
    echo "velero   velero-init-abc   0/1   Completed   0   5m"
    ;;
  *"get events"*) echo "Warning FailedMount pod/barman-cloud-586ff89c44-xrzgf secret not found" ;;
  *"describe pod"*) echo "Name: $5" ;;
  *) echo "objects" ;;
esac
"""

KIND = """#!/usr/bin/env bash
echo primary
"""


@pytest.mark.skipif(BASH is None, reason="cần bash")
def test_diagnose_saves_events_and_describes_unready_pods(tmp_path):
    stub = tmp_path / "bin"
    stub.mkdir()
    for name, body in (("kubectl", KUBECTL), ("kind", KIND)):
        p = stub / name
        p.write_text(body, newline="\n")
        p.chmod(0o755)
    data = tmp_path / "data"
    env = {**os.environ, "PATH": f"{stub}{os.pathsep}{os.environ['PATH']}", "DR_KIND_DATA": str(data),
           "DR_KIND_STATE": str(tmp_path / "state"), "STUB_LOG": str(tmp_path / "calls.log")}
    lib = (ROOT / "scripts/kind/lib.sh").as_posix()
    subprocess.run([BASH, "-c", f'source "{lib}"; diagnose run-1'], env=env, check=True)
    out = data / "logs" / "run-1"
    assert "FailedMount" in (out / "primary-events.txt").read_text()
    described = sorted(p.name for p in out.glob("primary-describe-*"))
    assert described == ["primary-describe-cnpg-system-barman-cloud-586ff89c44-xrzgf.txt"]
    assert (out / "primary-objects.txt").exists()
