import csv


def rows(fake_tools, run_id):
    path = fake_tools.root / "data" / "drills" / run_id / "vault-d6.csv"
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def prepare(fake_tools):
    fake_tools.session = {"state": "stopped", "cluster": "primary",
                          "vault_pack": "primary-202610270000/20261027T010000Z.tar.age"}


def test_any_successful_delete_fails_the_drill(fake_tools):
    prepare(fake_tools)
    fake_tools.extra_env = {"FAKE_HTTP_DELETE": "202", "FAKE_HTTP_PUT": "409"}
    r = fake_tools.run("vault-d6.sh", "d6-1")
    assert r.returncode == 1
    assert [row["outcome"] for row in rows(fake_tools, "d6-1")][:4] == ["allowed", "refused", "allowed", "refused"]


def test_all_refused_passes(fake_tools):
    prepare(fake_tools)
    fake_tools.extra_env = {"FAKE_HTTP_DELETE": "409", "FAKE_HTTP_PUT": "403"}
    r = fake_tools.run("vault-d6.sh", "d6-1")
    assert r.returncode == 0, r.stderr
    got = rows(fake_tools, "d6-1")
    assert len(got) == 5
    assert [row["actor"] for row in got] == ["account-key", "account-key", "vault-writer", "vault-writer", "account-key"]
    assert all(row["outcome"] == "refused" for row in got[:4])
    assert got[0]["http_status"] == "409"


def test_attempts_target_the_session_pack_in_vault(fake_tools):
    prepare(fake_tools)
    fake_tools.extra_env = {"FAKE_HTTP_DELETE": "409", "FAKE_HTTP_PUT": "409"}
    fake_tools.run("vault-d6.sh", "d6-1")
    curl = [line for line in fake_tools.calls.splitlines() if line.startswith("curl")]
    assert len(curl) == 4
    assert all("https://drvaultabc123.blob.core.windows.net/vault/primary-202610270000/20261027T010000Z.tar.age?" in c
               for c in curl)
    assert "If-None-Match" not in " ".join(curl)


def test_shortened_policy_is_put_back_to_seven_days(fake_tools):
    prepare(fake_tools)
    fake_tools.extra_env = {"FAKE_HTTP_DELETE": "409", "FAKE_HTTP_PUT": "409"}
    fake_tools.run("vault-d6.sh", "d6-1")
    policy = [line for line in fake_tools.calls.splitlines() if "immutability-policy create" in line]
    assert "--period 1" in policy[0] and "--period 7" in policy[-1]
    assert rows(fake_tools, "d6-1")[4]["outcome"] == "allowed"


def test_refuses_without_vault_pack(fake_tools):
    fake_tools.session = {"state": "stopped", "cluster": "primary"}
    r = fake_tools.run("vault-d6.sh", "d6-1")
    assert r.returncode != 0 and "vault_pack" in r.stderr


def test_unreachable_vault_fails_instead_of_counting_as_refused(fake_tools):
    prepare(fake_tools)
    fake_tools.extra_env = {"FAKE_HTTP_DELETE": "000", "FAKE_HTTP_PUT": "409"}
    r = fake_tools.run("vault-d6.sh", "d6-1")
    assert r.returncode == 1
    assert [row["outcome"] for row in rows(fake_tools, "d6-1")][:4] == ["error", "refused", "error", "refused"]


def test_policy_is_restored_when_script_dies_after_shortening(fake_tools):
    prepare(fake_tools)
    fake_tools.extra_env = {"FAKE_HTTP_DELETE": "409", "FAKE_HTTP_PUT": "409",
                            "FAKE_FAIL_ON": "immutability-policy show", "FAKE_FAIL_AFTER": "--period 1"}
    r = fake_tools.run("vault-d6.sh", "d6-1")
    assert r.returncode != 0
    assert "WORM" in r.stderr and "7" in r.stderr
