from datetime import UTC, datetime, timedelta

from scripts.kind.probe import FailureDetector, Prober

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


class FailingApi:
    base = "http://failing"

    def healthz(self, timeout=2):
        raise OSError("down")


def always_failing():
    return FailingApi()


def run_ticks(prober, n):
    original = prober.stop_event.wait
    count = 0

    def wait(timeout=None):
        nonlocal count
        count += 1
        if count >= n:
            prober.stop_event.set()
        return original(0)

    prober.stop_event.wait = wait
    prober.run()


def test_network_outage_is_not_detected_as_incident():
    p = Prober({"public": always_failing()}, watch="public", interval=0, control=lambda: False)
    run_ticks(p, 10)
    assert len(p.samples) == 10
    assert not p.detected.is_set() and all(not s.network_ok for s in p.samples)


def test_failures_with_network_up_are_detected():
    p = Prober({"public": always_failing()}, watch="public", interval=0, control=lambda: True)
    run_ticks(p, 5)
    assert p.detected.is_set()
    assert all(s.network_ok for s in p.samples)
