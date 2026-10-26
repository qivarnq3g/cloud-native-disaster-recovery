import csv
from datetime import UTC, datetime

from scripts.kind import resources, results


def test_step_row_and_append(tmp_path):
    start = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)
    end = datetime(2026, 10, 26, 12, 0, 5, 250000, tzinfo=UTC)
    row = results.step_row("r1", "D1", 1, "detect", start, end, "ok")
    assert row["duration_s"] == "5.2" and row["started_at"] == "2026-10-26T12:00:00.000Z"
    skipped = results.step_row("r1", "D1", 1, "switch", None, None, "not_applicable")
    assert skipped["duration_s"] == "" and skipped["started_at"] == ""
    path = tmp_path / "steps.csv"
    results.append_rows(path, results.STEP_FIELDS, [row])
    results.append_rows(path, results.STEP_FIELDS, [skipped])
    with path.open() as f:
        assert [r["step"] for r in csv.DictReader(f)] == ["detect", "switch"]


def test_summary_reports_median_and_quartiles(tmp_path):
    steps = [results.step_row(f"r{i}", "D1", i, "detect",
                              datetime(2026, 10, 26, tzinfo=UTC),
                              datetime(2026, 10, 26, 0, 0, s, tzinfo=UTC), "ok")
             for i, s in enumerate([4, 5, 6, 7, 8], 1)]
    results.append_rows(tmp_path / "a" / "steps.csv", results.STEP_FIELDS, steps)
    results.append_rows(tmp_path / "a" / "runs.csv", results.RUN_FIELDS,
                        [{"run_id": f"r{i}", "scenario": "D1", "rto_s": "60", "rpo_s": "30", "result": "pass"}
                         for i in range(1, 6)])
    text = results.summary([tmp_path])
    assert "| D1 | detect | 5 | 6.0 | 5.0 - 7.0 | 4.0 | 8.0 |" in text
    assert "Số lần chạy: 5, đạt: 5." in text


def test_parse_meminfo_and_peak():
    total, used = resources.parse_meminfo("MemTotal: 16384000 kB\nMemFree: 1 kB\nMemAvailable: 8192000 kB\n")
    assert (total, used) == (16000, 8000)
    rows = [{"mem_total_mb": "16000", "mem_used_mb": "3000", "disk_total_gb": "72", "disk_used_gb": "50"},
            {"mem_total_mb": "16000", "mem_used_mb": "9000", "disk_total_gb": "72", "disk_used_gb": "55.5"},
            {"mem_total_mb": "16000", "mem_used_mb": "7000", "disk_total_gb": "72", "disk_used_gb": "54"}]
    p = resources.peak(rows)
    assert p["mem_peak_mb"] == 9000 and p["disk_peak_used_gb"] == 55.5 and p["disk_baseline_used_gb"] == 50


def test_plan_matrix_splits_iterations_into_jobs():
    m = results.plan_matrix("D1, d3", 12, 5)["include"]
    assert m == [
        {"scenario": "D1", "chunk": 1, "count": 5}, {"scenario": "D1", "chunk": 2, "count": 5},
        {"scenario": "D1", "chunk": 3, "count": 2},
        {"scenario": "D3", "chunk": 1, "count": 5}, {"scenario": "D3", "chunk": 2, "count": 5},
        {"scenario": "D3", "chunk": 3, "count": 2},
    ]


def test_plan_matrix_rejects_bad_input():
    import pytest

    for args in [("D4", 1, 1), ("", 1, 1), ("D1", 0, 1), ("D1", 1, 0), ("D1,D2,D3,D6", 300, 1)]:
        with pytest.raises(ValueError):
            results.plan_matrix(*args)


def test_wait_for_retries_through_transient_errors():
    import pytest

    from scripts.kind.scenario import wait_for

    calls = iter([RuntimeError("the database system is shutting down"), None, "f"])

    def cond():
        v = next(calls)
        if isinstance(v, Exception):
            raise v
        return v

    assert wait_for(cond, 5, "thử", interval=0) == "f"

    def always_fails():
        raise RuntimeError("boom")

    with pytest.raises(TimeoutError, match="boom"):
        wait_for(always_fails, 0.05, "thử", interval=0.01)
