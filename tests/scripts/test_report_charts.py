from scripts.report.charts import attempts, median_run, official_runs, official_steps, passing, run_steps


def test_official_round_has_three_passes_per_scenario_and_two_d4_failures():
    ok = passing(official_runs())
    assert {sc: len(v) for sc, v in ok.items()} == {"D1": 3, "D2": 3, "D3": 3, "D4": 3, "D5": 3}
    assert attempts()["D4"] == 5 and attempts()["D1"] == 3


def test_steps_of_the_median_run_add_up_to_its_rto():
    steps = official_steps()
    for sc, runs in passing(official_runs()).items():
        chosen = median_run(runs)
        assert float(chosen["rto_s"]) == sorted(float(r["rto_s"]) for r in runs)[1]
        assert abs(sum(run_steps(steps, chosen["run_id"]).values()) - float(chosen["rto_s"])) < 2.0, sc


def test_unknown_run_has_no_steps():
    assert run_steps(official_steps(), "official-D9-9") == {}
