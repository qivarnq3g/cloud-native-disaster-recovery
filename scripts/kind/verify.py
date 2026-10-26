from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

from scripts.kind.workload import LedgerEntry, parse_time

POSTS_RPO_S = 300


def content_digest(rows: dict[str, str]) -> str:
    joined = ",".join(f"{pid}:{sha}" for pid, sha in sorted(rows.items()))
    return hashlib.md5(joined.encode()).hexdigest()


@dataclass
class VerifyReport:
    posts_acked: int
    posts_restored: int
    posts_missing: int
    posts_missing_beyond_rpo: int
    posts_holes: int
    posts_extra: int
    sha_mismatch: list[str]
    rpo_s: float
    digest_expected: str
    digest_actual: str
    rpo_target_s: float = POSTS_RPO_S
    images_checked: int = 0
    images_bad: list[str] = field(default_factory=list)

    @property
    def digest_match(self) -> bool:
        return self.digest_expected == self.digest_actual

    @property
    def ok(self) -> bool:
        return (self.posts_holes == 0 and not self.sha_mismatch and self.digest_match
                and self.posts_missing_beyond_rpo == 0 and self.rpo_s <= self.rpo_target_s
                and not self.images_bad)


def compare(ledger: list[LedgerEntry], db_rows: dict[str, str], incident_at: datetime,
            rpo_target_s: float = POSTS_RPO_S) -> VerifyReport:
    by_id = {e.post_id: e for e in ledger}
    survived = [e for e in ledger if e.post_id in db_rows]
    missing = [e for e in ledger if e.post_id not in db_rows]
    last = max((parse_time(e.acked_at) for e in survived), default=None)
    holes = [e for e in missing if last is not None and parse_time(e.acked_at) < last]
    beyond = [e for e in missing if (incident_at - parse_time(e.acked_at)).total_seconds() > rpo_target_s]
    rpo = 0.0
    if missing:
        rpo = max(0.0, (incident_at - last).total_seconds()) if last else float("inf")
    prefix = {e.post_id: e.sha256 for e in ledger if last is not None and parse_time(e.acked_at) <= last}
    restored_known = {pid: sha for pid, sha in db_rows.items() if pid in by_id}
    return VerifyReport(
        posts_acked=len(ledger),
        posts_restored=len(survived),
        posts_missing=len(missing),
        posts_missing_beyond_rpo=len(beyond),
        posts_holes=len(holes),
        posts_extra=len(db_rows) - len(restored_known),
        sha_mismatch=sorted(pid for pid, sha in restored_known.items() if by_id[pid].sha256 != sha),
        rpo_s=round(rpo, 3),
        digest_expected=content_digest(prefix),
        digest_actual=content_digest(restored_known),
        rpo_target_s=rpo_target_s,
    )


def check_images(rows: dict[str, str], fetch) -> list[str]:
    from concurrent.futures import ThreadPoolExecutor

    def bad(item: tuple[str, str]) -> str | None:
        pid, sha = item
        data = fetch(pid)
        return pid if data is None or hashlib.sha256(data).hexdigest() != sha else None

    with ThreadPoolExecutor(16) as pool:
        return sorted(p for p in pool.map(bad, rows.items()) if p)
