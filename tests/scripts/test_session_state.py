import json
from datetime import UTC, datetime

import pytest
from azure.core.exceptions import ResourceNotFoundError

from scripts.dr import session_state
from scripts.dr.session_state import Session, merge_sas_expiry, read_sas_expiry, read_session, write_session


class FakeBlob:
    def __init__(self, store, name):
        self.store, self.name = store, name

    def download_blob(self):
        if self.name not in self.store:
            raise ResourceNotFoundError("missing")
        data = self.store[self.name]
        return type("D", (), {"readall": lambda _: data})()

    def upload_blob(self, data, overwrite=False):
        assert overwrite
        self.store[self.name] = data if isinstance(data, bytes) else data.encode()


class FakeContainer:
    def __init__(self):
        self.blobs = {}

    def get_blob_client(self, name):
        return FakeBlob(self.blobs, name)


@pytest.fixture
def fake_container():
    return FakeContainer()


def test_session_round_trip(fake_container):
    s = Session(state="running", cluster="primary", server_name="primary-202610271405",
                started_at="2026-10-27T14:05:12Z")
    write_session(fake_container, s)
    assert read_session(fake_container) == s


def test_missing_session_is_none(fake_container):
    assert read_session(fake_container) is None


def test_sas_expiry_merge_keeps_other_names(fake_container):
    merge_sas_expiry(fake_container, "cnpg-backup", datetime(2026, 11, 26, tzinfo=UTC))
    merge_sas_expiry(fake_container, "check-read", datetime(2026, 11, 27, tzinfo=UTC))
    assert set(read_sas_expiry(fake_container)) == {"cnpg-backup", "check-read"}


def test_rejects_unknown_state(fake_container):
    with pytest.raises(ValueError):
        Session(state="paused", cluster="primary", server_name="x", started_at="x")


def test_session_json_has_every_field(fake_container):
    write_session(fake_container, Session(state="running", cluster="primary", server_name="p", started_at="t"))
    doc = json.loads(fake_container.blobs["session.json"])
    assert set(doc) == {"state", "cluster", "server_name", "started_at", "stopped_at", "full_backup",
                        "velero_backup", "post_count", "content_digest"}


def test_cli_set_then_get_with_fake_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DR_FAKE_SESSION", str(tmp_path / "status"))
    assert session_state.main(["get", "state"]) == 0
    assert capsys.readouterr().out.strip() == ""
    assert session_state.main(["set", "state=running", "cluster=primary", "server_name=primary-1",
                               "started_at=2026-10-27T14:05:12Z"]) == 0
    assert session_state.main(["set", "state=stopped", "post_count=20", "full_backup="]) == 0
    capsys.readouterr()
    session_state.main(["get", "state"])
    session_state.main(["get", "post_count"])
    session_state.main(["get", "server_name"])
    assert capsys.readouterr().out.split() == ["stopped", "20", "primary-1"]
