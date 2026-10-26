from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from scripts.kind.workload import ApiClient

DETECT_THRESHOLD = 5


@dataclass
class FailureDetector:
    threshold: int = DETECT_THRESHOLD
    streak: int = 0
    detected_at: datetime | None = None

    def feed(self, ok: bool, at: datetime) -> bool:
        if ok:
            self.streak = 0
            return False
        self.streak += 1
        if self.streak == self.threshold and self.detected_at is None:
            self.detected_at = at
            return True
        return False


@dataclass
class Sample:
    at: datetime
    target: str
    ok: bool
    status: int
    cluster: str = ""
    read_only: bool | None = None


def check(api: ApiClient) -> tuple[bool, int, dict]:
    try:
        status, body = api.healthz(timeout=2)
    except Exception:
        return False, 0, {}
    return status == 200 and body.get("status") == "ok", status, body


class Prober(threading.Thread):

    def __init__(self, targets: dict[str, ApiClient], watch: str, interval: float = 1.0):
        super().__init__(daemon=True)
        self.targets, self.watch, self.interval = targets, watch, interval
        self.samples: list[Sample] = []
        self.detector = FailureDetector()
        self.stop_event = threading.Event()
        self.detected = threading.Event()

    def run(self) -> None:
        next_at = time.monotonic()
        while not self.stop_event.is_set():
            for name, api in self.targets.items():
                ok, status, body = check(api)
                at = datetime.now(UTC)
                self.samples.append(Sample(at, name, ok, status, body.get("cluster", ""), body.get("read_only")))
                if name == self.watch and self.detector.feed(ok, at):
                    self.detected.set()
            next_at += self.interval
            self.stop_event.wait(max(0.0, next_at - time.monotonic()))

    def stop(self) -> None:
        self.stop_event.set()
        self.join(timeout=10)


def wait_healthy(api: ApiClient, timeout: float, writable: bool = True, interval: float = 1.0) -> datetime:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ok, _, body = check(api)
        if ok and (not writable or body.get("read_only") is False):
            return datetime.now(UTC)
        time.sleep(interval)
    raise TimeoutError(f"{api.base}/healthz không lên trong {timeout:.0f} s")
