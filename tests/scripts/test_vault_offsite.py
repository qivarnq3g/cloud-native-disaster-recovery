from datetime import UTC, datetime
from pathlib import Path

from scripts.vault.blob import BlobInfo
from scripts.vault.offsite import latest_chain, local_packs, pull, to_download, to_prune

A1 = "primary-202611070800/20261107T080500Z.tar.age"
A2 = "primary-202611070800/20261107T090000Z.tar.age"
B1 = "standby-202611071335/20261107T134904Z.tar.age"


def _blob(name, size=10):
    return BlobInfo(name, datetime(2026, 11, 7, tzinfo=UTC), size)


def test_latest_chain_is_every_pack_of_the_newest_server_in_order():
    assert latest_chain([B1, A2, A1]) == [B1]
    assert latest_chain([A2, A1, "junk.txt"]) == [A1, A2]
    assert latest_chain([]) == []


def test_download_only_missing_or_size_changed_packs_of_latest_chain():
    remote = [_blob(A1), _blob(A2), _blob("primary-202611070800/notes.txt")]
    assert to_download(remote, {A1: 10}) == [A2]
    assert to_download(remote, {A1: 9, A2: 10}) == [A1]
    assert to_download([_blob(A1), _blob(B1)], {}) == [B1]


def test_prune_keeps_only_the_latest_chain():
    assert to_prune([A1, A2, B1], [B1]) == [A1, A2]
    assert to_prune([B1], [B1]) == []


def test_local_packs_lists_relative_names_with_sizes(tmp_path):
    (tmp_path / "standby-202611071335").mkdir()
    (tmp_path / B1).write_bytes(b"abc")
    (tmp_path / "standby-202611071335" / "x.part").write_bytes(b"z")
    assert local_packs(tmp_path) == {B1: 3}


def test_pull_downloads_then_prunes_and_never_leaves_partial_files(tmp_path):
    (tmp_path / "primary-202611070800").mkdir()
    (tmp_path / A1).write_bytes(b"old")
    calls = []

    def fake_download(url, sas, name, dest: Path):
        calls.append(name)
        dest.write_bytes(b"0123456789")

    report = pull("https://acc.blob.core.windows.net/vault", "sv=x",
                  tmp_path, lister=lambda url, sas: [_blob(A1, 3), _blob(B1)], downloader=fake_download)
    assert calls == [B1]
    assert report == {"chain": [B1], "downloaded": [B1], "pruned": [A1]}
    assert (tmp_path / B1).read_bytes() == b"0123456789"
    assert not (tmp_path / A1).exists()
    assert not list(tmp_path.rglob("*.part"))


def test_restore_from_dir_uses_latest_chain_without_azure(tmp_path, monkeypatch):
    from scripts.vault.restore_test import local_source

    monkeypatch.delenv("DRILL_READ_SAS_JSON", raising=False)
    for name, body in ((A1, b"a1"), (A2, b"a2"), (B1, b"b1")):
        (tmp_path / name).parent.mkdir(exist_ok=True)
        (tmp_path / name).write_bytes(body)
    names, fetch = local_source(tmp_path)
    assert names == [B1]
    dest = tmp_path / "copy.tar.age"
    fetch(B1, dest)
    assert dest.read_bytes() == b"b1"
    assert (tmp_path / B1).exists()


def test_restore_from_empty_dir_stops(tmp_path):
    import pytest

    from scripts.vault.restore_test import local_source

    with pytest.raises(SystemExit):
        local_source(tmp_path)


def test_pull_keeps_old_packs_when_download_fails(tmp_path):
    (tmp_path / "primary-202611070800").mkdir()
    (tmp_path / A1).write_bytes(b"0123456789")

    def broken(url, sas, name, dest: Path):
        dest.write_bytes(b"01")
        raise OSError("timed out")

    try:
        pull("u", "s", tmp_path, lister=lambda url, sas: [_blob(A1), _blob(B1)], downloader=broken)
    except OSError:
        pass
    assert (tmp_path / A1).exists()
    assert not (tmp_path / B1).exists()
    assert not list(tmp_path.rglob("*.part"))
