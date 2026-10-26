from datetime import UTC, datetime, timedelta

from scripts.kind.probe import FailureDetector

T = datetime(2026, 10, 26, tzinfo=UTC)


def at(s):
    return T + timedelta(seconds=s)


def test_detects_on_fifth_consecutive_failure_once():
    d = FailureDetector()
    fired = [d.feed(False, at(i)) for i in range(7)]
    assert fired == [False, False, False, False, True, False, False]
    assert d.detected_at == at(4)


def test_success_resets_streak():
    d = FailureDetector()
    for i, ok in enumerate([False] * 4 + [True] + [False] * 4):
        assert not d.feed(ok, at(i))
    assert d.detected_at is None
    assert d.feed(False, at(9))
