"""Ghi và tóm tắt số đo của bản thu nhỏ trong `data/kind/`.

- `steps.csv`: sáu bước của mục 5.2 thiết kế cho mỗi lần chạy.
- `runs.csv`: một dòng mỗi lần chạy: RTO, RPO, số bài, mã nội dung, ảnh.
- `d6.csv`: từng lần thử xóa hay ghi đè két ở D6.

Dòng lệnh:
    python -m scripts.kind.results summary <thư mục có các CSV> [...]   in bảng Markdown
    python -m scripts.kind.results matrix <D1,D2,...> <số lần> <số lần mỗi job>
        in ma trận job cho workflow kind-mini (mỗi job chạy một phần số lần của một tình huống)
"""

from __future__ import annotations

import csv
import statistics
import sys
from datetime import datetime
from pathlib import Path

STEPS = ("detect", "decide", "infra", "restore", "verify", "switch")
STEP_FIELDS = ["run_id", "scenario", "iteration", "step", "started_at", "ended_at", "duration_s", "result"]
RUN_FIELDS = [
    "run_id", "scenario", "iteration", "runner", "cpus", "mem_total_mb", "seed_posts", "incident_at",
    "detected_at", "service_restored_at", "verified_at", "rto_s", "posts_acked", "posts_restored",
    "posts_missing", "posts_missing_beyond_rpo", "posts_holes", "posts_extra", "rpo_s", "digest_match",
    "content_digest", "images_checked", "images_bad", "functional_ok", "result",
]
D6_FIELDS = ["run_id", "iteration", "attempt", "identity", "refused", "error_code", "original_intact", "result"]


def iso(t: datetime | None) -> str:
    return "" if t is None else t.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def append_rows(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def step_row(run_id: str, scenario: str, iteration: int, step: str, start: datetime | None,
             end: datetime | None, result: str) -> dict:
    duration = "" if start is None or end is None else f"{(end - start).total_seconds():.1f}"
    return {"run_id": run_id, "scenario": scenario, "iteration": iteration, "step": step,
            "started_at": iso(start), "ended_at": iso(end), "duration_s": duration, "result": result}


def read_csvs(dirs: list[Path], name: str) -> list[dict]:
    rows: list[dict] = []
    for d in dirs:
        for p in sorted(d.rglob(name)):
            with p.open(newline="") as f:
                rows.extend(csv.DictReader(f))
    return rows


def describe(values: list[float]) -> str:
    """Trung vị và khoảng tứ phân vị (mục 5.4), kèm nhỏ nhất và lớn nhất."""
    if not values:
        return "| 0 | | | | |"
    v = sorted(values)
    if len(v) >= 2:
        q1, _, q3 = statistics.quantiles(v, n=4, method="inclusive")
    else:
        q1 = q3 = v[0]
    return f"| {len(v)} | {statistics.median(v):.1f} | {q1:.1f} - {q3:.1f} | {v[0]:.1f} | {v[-1]:.1f} |"


def summary(dirs: list[Path]) -> str:
    steps = read_csvs(dirs, "steps.csv")
    runs = read_csvs(dirs, "runs.csv")
    out = ["| Tình huống | Bước | Số lần | Trung vị (s) | Tứ phân vị (s) | Nhỏ nhất | Lớn nhất |",
           "|---|---|---|---|---|---|---|"]
    for scenario in sorted({r["scenario"] for r in runs}):
        for step in STEPS:
            vals = [float(r["duration_s"]) for r in steps
                    if r["scenario"] == scenario and r["step"] == step and r["duration_s"]]
            if vals:
                out.append(f"| {scenario} | {step} {describe(vals)}")
        rto = [float(r["rto_s"]) for r in runs if r["scenario"] == scenario and r["rto_s"]]
        if rto:
            out.append(f"| {scenario} | RTO (không gồm switch) {describe(rto)}")
        rpo = [float(r["rpo_s"]) for r in runs if r["scenario"] == scenario and r["rpo_s"]]
        if rpo:
            out.append(f"| {scenario} | RPO bài viết {describe(rpo)}")
    passed = sum(r["result"] == "pass" for r in runs)
    out.append("")
    out.append(f"Số lần chạy: {len(runs)}, đạt: {passed}.")
    d6 = read_csvs(dirs, "d6.csv")
    if d6:
        refused = sum(r["refused"] == "true" for r in d6 if r["result"] == "pass")
        out.append(f"D6: {len(d6)} lần thử xóa hay ghi đè két, {refused} lần bị từ chối đúng như mong đợi, "
                   f"{sum(r['result'] == 'pass' for r in d6)} lần đạt.")
    return "\n".join(out)


SCENARIOS = ("D1", "D2", "D3", "D6")
MAX_JOBS = 256  # giới hạn số job của một ma trận GitHub Actions


def plan_matrix(scenarios: str, iterations: int, per_job: int) -> dict:
    names = [s.strip().upper() for s in scenarios.split(",") if s.strip()]
    unknown = [s for s in names if s not in SCENARIOS]
    if not names or unknown:
        raise ValueError(f"tình huống phải thuộc {SCENARIOS}, nhận {scenarios!r}")
    if iterations < 1 or per_job < 1:
        raise ValueError("số lần và số lần mỗi job phải từ 1")
    include = []
    for name in dict.fromkeys(names):
        done, chunk = 0, 1
        while done < iterations:
            count = min(per_job, iterations - done)
            include.append({"scenario": name, "chunk": chunk, "count": count})
            done, chunk = done + count, chunk + 1
    if len(include) > MAX_JOBS:
        raise ValueError(f"{len(include)} job vượt giới hạn {MAX_JOBS}; tăng số lần mỗi job")
    return {"include": include}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) >= 2 and args[0] == "summary":
        print(summary([Path(a) for a in args[1:]]))
        return 0
    if len(args) == 4 and args[0] == "matrix":
        import json

        print(json.dumps(plan_matrix(args[1], int(args[2]), int(args[3]))))
        return 0
    print(__doc__, file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main())
