import csv
from datetime import UTC, datetime, timedelta

from scripts.dr.backup_check import CHECKS, Snapshot, append_csv, evaluate
from scripts.dr.session_state import Session

NOW = datetime(2026, 10, 27, 15, 0, tzinfo=UTC)
_DEFAULT = object()


def failed(results):
    return {r.name for r in results if not r.ok}


def _sas(sas):
    if sas is not None:
        return sas
    return {n: NOW + timedelta(days=30) for n in ("api-images-primary", "cnpg-backup", "check-read", "drill-read")}


def running(wal=_DEFAULT, velero=_DEFAULT, sas=None, primary_images=None, copied_images=None):
    return Snapshot(
        session=Session(state="running", cluster="primary", server_name="primary-202610271405",
                        started_at="2026-10-27T14:05:12Z"),
        sas_expiry=_sas(sas),
        newest_wal=NOW - timedelta(minutes=1) if wal is _DEFAULT else wal,
        newest_velero=NOW - timedelta(minutes=10) if velero is _DEFAULT else velero,
        velero_names=set(),
        full_backup_names=set(),
        primary_images={"old.jpg": NOW - timedelta(hours=1)} if primary_images is None else primary_images,
        copied_images={"old.jpg"} if copied_images is None else copied_images,
    )


def stopped(full_backup, velero_backup, full_backup_names, velero_names, sas=None):
    return Snapshot(
        session=Session(state="stopped", cluster="primary", server_name="primary-202610271405",
                        started_at="2026-10-27T14:05:12Z", stopped_at="2026-10-27T17:00:00Z",
                        full_backup=full_backup, velero_backup=velero_backup, post_count=20,
                        content_digest="0123abcd"),
        sas_expiry=_sas(sas),
        newest_wal=None,
        newest_velero=None,
        velero_names=velero_names,
        full_backup_names=full_backup_names,
        primary_images={},
        copied_images=set(),
    )


def test_running_all_fresh_is_ok():
    assert all(r.ok for r in evaluate(running(wal=NOW - timedelta(minutes=2), velero=NOW - timedelta(minutes=50)), NOW))


def test_wal_older_than_5_minutes_fails():
    assert failed(evaluate(running(wal=NOW - timedelta(minutes=5, seconds=1)), NOW)) == {"wal_age"}


def test_velero_older_than_2_hours_fails():
    assert failed(evaluate(running(velero=NOW - timedelta(hours=2, seconds=1)), NOW)) == {"velero_age"}


def test_image_not_copied_after_5_minutes_fails():
    s = running(primary_images={"a.jpg": NOW - timedelta(minutes=6)}, copied_images=set())
    assert failed(evaluate(s, NOW)) == {"image_replication"}


def test_image_not_copied_yet_but_young_is_ok():
    s = running(primary_images={"a.jpg": NOW - timedelta(minutes=4)}, copied_images=set())
    assert failed(evaluate(s, NOW)) == set()


def test_sas_expiring_within_7_days_fails():
    assert failed(evaluate(running(sas={"check-read": NOW + timedelta(days=6, hours=23)}), NOW)) == {"sas_expiry"}


def test_empty_store_fails_not_skips():
    s = Snapshot(session=None, sas_expiry={}, newest_wal=None, newest_velero=None, velero_names=set(),
                 full_backup_names=set(), primary_images={}, copied_images=set())
    assert {"session_file", "sas_expiry"} <= failed(evaluate(s, NOW))


def test_running_without_any_wal_fails():
    assert "wal_age" in failed(evaluate(running(wal=None), NOW))


def test_running_without_any_velero_backup_fails():
    assert "velero_age" in failed(evaluate(running(velero=None), NOW))


def test_stopped_checks_only_stop_backups_and_sas():
    s = stopped(full_backup="stop-202610271700", velero_backup="stop-202610271700",
                full_backup_names={"stop-202610271700"}, velero_names=set())
    results = {r.name: r for r in evaluate(s, NOW)}
    assert not results["stop_backups"].ok and results["wal_age"].detail == "skip"


def test_stopped_with_both_backups_is_ok():
    s = stopped(full_backup="stop-202610271700", velero_backup="stop-202610271700",
                full_backup_names={"stop-202610271700"}, velero_names={"stop-202610271700"})
    assert failed(evaluate(s, NOW)) == set()


def test_every_check_reported_once():
    assert [r.name for r in evaluate(running(), NOW)] == list(CHECKS)


def test_csv_row_uses_ok_fail_skip(tmp_path):
    s = stopped(full_backup="stop-1", velero_backup="stop-1", full_backup_names=set(), velero_names={"stop-1"})
    path = tmp_path / "2026-10.csv"
    append_csv(path, s, evaluate(s, NOW), NOW)
    append_csv(path, s, evaluate(s, NOW), NOW)
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert len(rows) == 2
    assert rows[0]["checked_at"] == "2026-10-27T15:00:00Z" and rows[0]["state"] == "stopped"
    assert rows[0]["wal_age"] == "skip" and rows[0]["stop_backups"] == "fail" and rows[0]["sas_expiry"] == "ok"


class _Blob:
    def __init__(self, name, last_modified, data=b""):
        self.name, self.last_modified, self.data = name, last_modified, data


class _Container:
    def __init__(self, blobs):
        self.blobs = {b.name: b for b in blobs}

    def list_blobs(self, name_starts_with=""):
        return [b for n, b in self.blobs.items() if n.startswith(name_starts_with)]

    def get_blob_client(self, name):
        data = self.blobs[name].data if name in self.blobs else None
        from azure.core.exceptions import ResourceNotFoundError

        class Client:
            def download_blob(self):
                if data is None:
                    raise ResourceNotFoundError(name)
                return type("D", (), {"readall": lambda _: data})()

        return Client()


def test_collect_reads_store_layout(monkeypatch):
    import json as _json

    from scripts.dr import backup_check

    t = NOW - timedelta(minutes=1)
    session = {"state": "stopped", "cluster": "primary", "server_name": "primary-1", "started_at": "x",
               "stopped_at": "y", "full_backup": "stop-1", "velero_backup": "stop-1", "post_count": 3,
               "content_digest": "d"}
    stores = {
        "https://drbackupabc.blob.core.windows.net/status": _Container([
            _Blob("session.json", t, _json.dumps(session).encode()),
            _Blob("sas-expiry.json", t, b'{"check-read": "2026-11-26T00:00:00Z"}')]),
        "https://drbackupabc.blob.core.windows.net/cnpg": _Container([
            _Blob("primary-1/wals/0000000100000000/000000010000000000000001.gz", NOW - timedelta(minutes=3)),
            _Blob("primary-1/wals/0000000100000000/000000010000000000000002.gz", t),
            _Blob("primary-1/base/20261027T170000/backup.info", t, b"backup_id=20261027T170000\nbackup_name=stop-1\n"),
            _Blob("primary-1/base/20261027T170000/data.tar.gz", t),
            _Blob("old-server/wals/x.gz", NOW)]),
        "https://drbackupabc.blob.core.windows.net/velero": _Container([
            _Blob("backups/stop-1/velero-backup.json", t),
            _Blob("backups/stop-1/stop-1.tar.gz", t)]),
        "https://drimgpriabc.blob.core.windows.net/images": _Container([_Blob("original/a.jpg", t)]),
        "https://drimgcopyabc.blob.core.windows.net/images": _Container([_Blob("original/a.jpg", t)]),
    }
    monkeypatch.setattr(backup_check, "_container", lambda url, sas: stores[url])
    s = backup_check.collect({url: "sv=x" for url in stores})
    assert s.session.full_backup == "stop-1" and set(s.sas_expiry) == {"check-read"}
    assert s.newest_wal == t
    assert s.full_backup_names == {"20261027T170000", "stop-1"}
    assert s.velero_names == {"stop-1"} and s.newest_velero == t
    assert s.copied_images == {"original/a.jpg"}
    assert failed(evaluate(s, NOW)) == set()
