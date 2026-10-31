WARM_SESSION = {"state": "running", "cluster": "primary", "server_name": "primary-202610300100"}


def warm(fake_tools):
    fake_tools.session = WARM_SESSION
    fake_tools.vms = ["vm-dr-primary", "vm-dr-standby"]
    (fake_tools.private / "standby-server").write_text("standby-202610300110\n")
    return fake_tools


def test_warm_promotes_db_before_enabling_image_writes(fake_tools):
    r = warm(fake_tools).run("failover-warm.sh", "r1")
    assert r.returncode == 0, r.stderr
    c = fake_tools.calls
    promote = c.index('"replica":{"enabled":false}')
    assert promote < c.index("or-policy delete") < c.index('"IMAGE_STORE_READ_ONLY":"false"')
    assert c.index("nsg rule update -g rg-dr-standby") < promote


def test_warm_deletes_only_policies_on_standby_image_account(fake_tools):
    warm(fake_tools).run("failover-warm.sh", "r1")
    c = fake_tools.calls
    assert "or-policy list -g rg-dr-standby --account-name drimgstbabc123" in c
    assert "or-policy delete -g rg-dr-standby --account-name drimgstbabc123 --policy-id pol-1" in c
    assert "--policy-id pol-2" not in c
    assert c.index("--policy-id pol-1") < c.index("blob upload --account-name drimgstbabc123")
    assert c.index("blob upload --account-name drimgstbabc123") < c.index("IMAGE_STORE_READ_ONLY")


def test_warm_stops_when_standby_images_stay_read_only(fake_tools):
    warm(fake_tools).fail_on = "blob upload --account-name drimgstbabc123"
    fake_tools.extra_env["DR_ORS_TIMEOUT"] = "0"
    assert fake_tools.run("failover-warm.sh", "r1").returncode == 1
    assert "IMAGE_STORE_READ_ONLY" not in fake_tools.calls


def test_warm_switches_dns_and_session_together(fake_tools):
    r = warm(fake_tools).run("failover-warm.sh", "r1")
    assert r.returncode == 0, r.stderr
    doc = fake_tools.session_doc()
    assert doc["cluster"] == "standby" and doc["server_name"] == "standby-202610300110"
    assert "dns_switch 20.0.0.8" in fake_tools.calls


def test_warm_records_restore_and_switch_steps(fake_tools):
    warm(fake_tools).run("failover-warm.sh", "r1")
    rows = (fake_tools.root / "data" / "drills" / "r1" / "steps.csv").read_text().splitlines()
    assert [row.split(",")[0] for row in rows[1:]] == ["restore", "switch"]
    assert all(row.endswith(",ok") for row in rows[1:])


def test_warm_without_run_id_records_nothing(fake_tools):
    r = warm(fake_tools).run("failover-warm.sh", "")
    assert r.returncode == 0, r.stderr
    assert not (fake_tools.root / "data" / "drills").exists()


def test_warm_stops_if_promotion_never_finishes(fake_tools):
    warm(fake_tools).in_recovery = "t"
    r = fake_tools.run("failover-warm.sh", "r1")
    assert r.returncode == 1
    assert "dns_switch" not in fake_tools.calls and "or-policy delete" not in fake_tools.calls
    assert fake_tools.session_doc()["cluster"] == "primary"


def test_warm_refuses_when_standby_is_already_live(fake_tools):
    warm(fake_tools).session = {**WARM_SESSION, "cluster": "standby"}
    assert fake_tools.run("failover-warm.sh", "r1").returncode == 3
    assert "replica" not in fake_tools.calls


def test_restore_namespace_skips_cnpg_objects_and_targets_time(fake_tools):
    fake_tools.session = WARM_SESSION
    r = fake_tools.run("restore-namespace.sh", "r1", "2026-10-30T01:02:03Z")
    assert r.returncode == 0, r.stderr
    assert "managed-by notin (cloudnative-pg)" in fake_tools.calls
    assert "--from-backup hourly-a" in fake_tools.calls
    assert 'targetTime: "2026-10-30T01:02:03Z"' in fake_tools.applied_yaml
    assert "serverName: primary-202610300100" in fake_tools.applied_yaml
    assert fake_tools.session_doc()["server_name"].startswith("primary-2")
    assert fake_tools.session_doc()["server_name"] != "primary-202610300100"


def test_restore_namespace_uses_newest_velero_backup_of_this_session(fake_tools):
    fake_tools.session = WARM_SESSION
    fake_tools.velero_backups = ("hourly-new 2026-10-27T02:00:00Z\nhourly-old 2026-10-26T23:00:00Z\n"
                                 "start-x 2026-10-27T00:05:00Z\n")
    r = fake_tools.run("restore-namespace.sh", "r1", "2026-10-30T01:02:03Z")
    assert r.returncode == 0, r.stderr
    assert "--from-backup hourly-new" in fake_tools.calls
    assert '{"\\n"}{end}' in fake_tools.calls


def test_restore_namespace_refuses_backups_older_than_session(fake_tools):
    fake_tools.session = WARM_SESSION
    fake_tools.velero_backups = "hourly-old 2026-10-26T23:00:00Z\n"
    r = fake_tools.run("restore-namespace.sh", "r1", "2026-10-30T01:02:03Z")
    assert r.returncode == 5, r.stderr
    assert "velero restore" not in fake_tools.calls


def test_restore_namespace_restores_schedule_and_takes_base_backup(fake_tools):
    fake_tools.session = WARM_SESSION
    assert fake_tools.run("restore-namespace.sh", "r1", "2026-10-30T01:02:03Z").returncode == 0
    c = fake_tools.calls
    assert c.index("condition=Ready clusters.postgresql.cnpg.io/db") < c.index("scheduled-backup.yaml")
    assert c.index("condition=Ready clusters.postgresql.cnpg.io/db") < c.index("backups.postgresql.cnpg.io/restore-")


def test_warm_takes_base_backup_after_promotion(fake_tools):
    r = warm(fake_tools).run("failover-warm.sh", "r1")
    assert r.returncode == 0, r.stderr
    c = fake_tools.calls
    assert c.index("pg_is_in_recovery()") < c.index("backups.postgresql.cnpg.io/promote-")


def test_restore_namespace_rejects_bad_target_time(fake_tools):
    fake_tools.session = WARM_SESSION
    assert fake_tools.run("restore-namespace.sh", "r1", "yesterday").returncode == 64
    assert "velero" not in fake_tools.calls


COLD_STUBS = ["cluster-up.sh", "install-software.sh", "deploy-api.sh"]


def cold(fake_tools):
    fake_tools.stubs = COLD_STUBS
    fake_tools.session = {"state": "stopped", "cluster": "primary", "server_name": "primary-202610300100"}
    return fake_tools


def test_cold_copies_images_only_when_asked(fake_tools):
    r = cold(fake_tools).run("failover-cold.sh", "r1", "standby")
    assert r.returncode == 0, r.stderr
    assert "copy start-batch" not in fake_tools.calls
    fake_tools.extra_env["DR_IMAGES_FROM_COPY"] = "true"
    r = fake_tools.run("failover-cold.sh", "r2", "standby")
    assert r.returncode == 0, r.stderr
    assert "copy start-batch" in fake_tools.calls


def test_cold_recovers_from_last_server_and_switches(fake_tools):
    r = cold(fake_tools).run("failover-cold.sh", "r1", "standby")
    assert r.returncode == 0, r.stderr
    c = fake_tools.calls
    assert "cluster-up.sh standby" in c
    assert "install-software.sh standby standby-" in c and "primary-202610300100" in c
    doc = fake_tools.session_doc()
    assert doc["cluster"] == "standby" and doc["state"] == "running"
    assert doc["server_name"].startswith("standby-")
    rows = (fake_tools.root / "data" / "drills" / "r1" / "steps.csv").read_text().splitlines()
    assert [row.split(",")[0] for row in rows[1:]] == ["infra", "restore", "switch"]


def test_cold_takes_base_backup_on_new_server(fake_tools):
    assert cold(fake_tools).run("failover-cold.sh", "r1", "standby").returncode == 0
    c = fake_tools.calls
    assert c.index("deploy-api.sh standby") < c.index("backups.postgresql.cnpg.io/cold-") < c.index("dns_switch")


def test_cold_skips_cluster_up_when_vm_exists(fake_tools):
    cold(fake_tools).vms = ["vm-dr-standby"]
    r = fake_tools.run("failover-cold.sh", "r1", "standby")
    assert r.returncode == 0, r.stderr
    c = fake_tools.calls
    assert "cluster-up.sh" not in c
    assert c.index("nsg rule update -g rg-dr-standby") < c.index("install-software.sh")


def test_cold_stops_before_switch_when_image_copy_fails(fake_tools):
    cold(fake_tools).extra_env["DR_IMAGES_FROM_COPY"] = "true"
    fake_tools.fail_on = "copy start-batch"
    assert fake_tools.run("failover-cold.sh", "r1", "standby").returncode == 1
    assert "dns_switch" not in fake_tools.calls


def test_copy_images_waits_for_every_blob(fake_tools):
    r = fake_tools.run("copy-images.sh")
    assert r.returncode == 0, r.stderr
    c = fake_tools.calls
    assert "--source-account-name drimgcopyabc123" in c and "--account-name drimgstbabc123" in c
    assert "properties.copy.status!='success'" in c
