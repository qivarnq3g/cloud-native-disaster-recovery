import json

from scripts.kind import store


def test_credentials_are_random_and_scoped(tmp_path):
    a = store.init(tmp_path / "a")
    b = store.init(tmp_path / "b")
    assert a["identities"]["admin"]["secret"] != b["identities"]["admin"]["secret"]
    assert len(a["secret_code"]) >= 16
    cfg = json.loads((tmp_path / "a" / "s3.json").read_text())
    by_name = {i["name"]: i for i in cfg["identities"]}
    assert set(by_name) == set(store.IDENTITIES)
    assert all(":" in act for name, i in by_name.items() if name != "admin" for act in i["actions"])
    assert by_name["vault-writer"]["actions"] == ["Write:vault"]
    assert by_name["api-primary"]["credentials"][0]["accessKey"] == a["identities"]["api-primary"]["access"]


def test_init_keeps_existing_credentials_and_hides_them(tmp_path):
    first = store.init(tmp_path)
    assert store.init(tmp_path) == first
    assert (tmp_path / "credentials.json").stat().st_mode & 0o077 == 0
    assert (tmp_path / "secret-code").read_text() == first["secret_code"]
    assert (tmp_path / "secret-code").stat().st_mode & 0o077 == 0
