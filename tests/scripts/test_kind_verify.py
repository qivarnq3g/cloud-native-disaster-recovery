import hashlib
from datetime import UTC, datetime, timedelta

from scripts.kind.verify import check_images, compare, content_digest
from scripts.kind.workload import LedgerEntry

T0 = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)


def entry(seq, seconds_before_incident, sha=None):
    acked = (T0 - timedelta(seconds=seconds_before_incident)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return LedgerEntry(seq, f"0000{seq:04d}-0000-7000-8000-000000000000", acked, sha or f"{seq:064x}", "writer")


def rows(entries):
    return {e.post_id: e.sha256 for e in entries}


def test_digest_matches_postgres_formula():
    # md5('a:01,b:02'), cùng thứ tự với ORDER BY id trong Postgres
    assert content_digest({"b": "02", "a": "01"}) == hashlib.md5(b"a:01,b:02").hexdigest()


def test_everything_restored_is_ok():
    ledger = [entry(i, 100 - i) for i in range(1, 11)]
    r = compare(ledger, rows(ledger), T0)
    assert r.ok and r.posts_missing == 0 and r.rpo_s == 0 and r.digest_match


def test_tail_loss_within_rpo_is_ok_and_measures_rpo():
    ledger = [entry(i, 100 - i) for i in range(1, 11)]  # bài 10 xác nhận 90 s trước sự cố
    r = compare(ledger, rows(ledger[:7]), T0)  # còn tới bài 7, xác nhận 93 s trước sự cố
    assert r.ok
    assert r.posts_missing == 3 and r.posts_holes == 0
    assert r.rpo_s == 93
    assert r.digest_match


def test_hole_in_the_middle_fails():
    ledger = [entry(i, 100 - i) for i in range(1, 11)]
    restored = rows(ledger[:4] + ledger[5:])
    r = compare(ledger, restored, T0)
    assert not r.ok and r.posts_holes == 1 and not r.digest_match


def test_loss_older_than_rpo_target_fails():
    ledger = [entry(1, 600), entry(2, 400), entry(3, 10)]
    r = compare(ledger, rows(ledger[:1]), T0)
    assert r.posts_missing_beyond_rpo == 1  # bài 2: 400 s > 300 s
    assert not r.ok


def test_wrong_sha_fails():
    ledger = [entry(1, 10), entry(2, 5)]
    restored = rows(ledger) | {ledger[1].post_id: "ff" * 32}
    r = compare(ledger, restored, T0)
    assert r.sha_mismatch == [ledger[1].post_id] and not r.ok


def test_in_flight_post_is_extra_not_loss():
    ledger = [entry(1, 10)]
    restored = rows(ledger) | {"ffffffff-0000-7000-8000-000000000000": "aa" * 32}
    r = compare(ledger, restored, T0)
    assert r.posts_extra == 1 and r.posts_missing == 0 and r.ok


def test_nothing_restored_reports_infinite_rpo():
    ledger = [entry(1, 10)]
    r = compare(ledger, {}, T0)
    assert r.rpo_s == float("inf") and not r.ok


def test_check_images_reports_missing_and_corrupt():
    good = b"good"
    data = {"a": good, "b": b"corrupt", "c": None}
    expected = {k: hashlib.sha256(good).hexdigest() for k in data}
    assert check_images(expected, data.get) == ["b", "c"]
