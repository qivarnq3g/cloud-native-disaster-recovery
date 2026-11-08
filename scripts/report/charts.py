from __future__ import annotations

import argparse
import csv
import random
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ["D1", "D2", "D3", "D4", "D5"]
LABELS = {
    "D1": "D1 xóa namespace",
    "D2": "D2 mất cụm, lạnh",
    "D3": "D3 mất cụm, ấm",
    "D4": "D4 mất nhóm, lạnh",
    "D5": "D5 mất nhóm, ấm",
}
STEPS = ["detect", "decide", "infra", "restore", "switch"]
STEP_LABELS = {"detect": "phát hiện", "decide": "quyết định", "infra": "dựng hạ tầng",
               "restore": "khôi phục dữ liệu", "switch": "đổi DNS"}
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#ffffff"


def _rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def attempts(root: Path = ROOT) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for d in (root / "data/azure/drills").glob("official-D*"):
        sc = d.name.split("-")[1]
        if sc in SCENARIOS:
            out[sc] += 1
    return out


def official_runs(root: Path = ROOT) -> list[dict]:
    rows = []
    for f in sorted((root / "data/azure/drills").glob("official-D*/runs.csv")):
        rows += [r for r in _rows(f) if r.get("scenario") in SCENARIOS]
    return rows


def official_steps(root: Path = ROOT) -> list[dict]:
    rows = []
    for f in sorted((root / "data/azure/drills").glob("official-D*/steps.csv")):
        rows += [r for r in _rows(f) if r.get("scenario") in SCENARIOS]
    return rows


def passing(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["result"] == "pass":
            out[r["scenario"]].append(r)
    return out


def median_run(runs: list[dict]) -> dict:
    ordered = sorted(runs, key=lambda r: float(r["rto_s"]))
    return ordered[(len(ordered) - 1) // 2]


def run_steps(steps: list[dict], run_id: str) -> dict[str, float]:
    return {s["step"]: float(s["duration_s"]) for s in steps
            if s["run_id"] == run_id and s["step"] in STEPS and s["duration_s"]}


def kind_runs(folder: Path) -> dict[str, list[float]]:
    out: dict[str, list[float]] = defaultdict(list)
    for r in _rows(folder / "runs.csv"):
        if r["result"] == "pass" and r["rto_s"]:
            out[r["scenario"]].append(float(r["rto_s"]))
    return out


def _style(plt):
    plt.rcParams.update({
        "font.family": "Times New Roman", "font.size": 11, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
        "xtick.color": INK2, "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False,
        "axes.spines.left": False, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.dpi": 200,
    })


def _strip(ax, groups: list[tuple[str, list[float]]], xlabel: str, target: tuple[float, str] | None, jitter=0.0):
    rnd = random.Random(7)
    for i, (_, vals) in enumerate(groups):
        ys = [i + (rnd.uniform(-jitter, jitter) if jitter else 0) for _ in vals]
        ax.scatter(vals, ys, s=46, color=SERIES[0], alpha=0.75 if jitter else 1, edgecolors=SURFACE,
                   linewidths=1.2, zorder=3)
        m = statistics.median(vals)
        ax.plot([m, m], [i - 0.28, i + 0.28], color=INK, linewidth=2, zorder=4)
    ax.set_yticks(range(len(groups)), [g for g, _ in groups])
    ax.set_ylim(len(groups) - 0.5, -0.9 if target else -0.5)
    ax.set_xlabel(xlabel)
    ax.set_xlim(left=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    if target:
        ax.axvline(target[0], color=INK2, linestyle=(0, (4, 3)), linewidth=1.2, zorder=2)
        ax.text(target[0] - 4, -0.62, target[1], color=INK2, fontsize=11, ha="right", va="center")


def render(out: Path, kind_folder: Path) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _style(plt)
    out.mkdir(parents=True, exist_ok=True)
    runs = official_runs()
    ok = passing(runs)
    made = []

    tries = attempts()

    def label(sc):
        total = tries[sc]
        return f"{LABELS[sc]} ({len(ok[sc])}/{total})"

    fig, (a, b) = plt.subplots(1, 2, figsize=(7.4, 3.6), sharey=True, gridspec_kw={"wspace": 0.08})
    _strip(a, [(label(sc), [float(r["rto_s"]) for r in ok[sc]]) for sc in SCENARIOS], "RTO (giây)",
           (600, "mục tiêu cách ấm 600 s"))
    a.set_xlim(0, 700)
    _strip(b, [(label(sc), [float(r["rpo_s"]) for r in ok[sc]]) for sc in SCENARIOS], "RPO (giây)",
           (300, "mục tiêu RPO 300 s"))
    b.set_xlim(0, 320)
    b.tick_params(axis="y", length=0, labelleft=False)
    fig.savefig(out / "official-rto-rpo.png", bbox_inches="tight")
    plt.close(fig)
    made.append(out / "official-rto-rpo.png")

    steps = official_steps()
    fig, ax = plt.subplots(figsize=(7.4, 3.4))
    for i, sc in enumerate(SCENARIOS):
        chosen = median_run(ok[sc])
        parts = run_steps(steps, chosen["run_id"])
        left = 0.0
        for j, st in enumerate(STEPS):
            w = parts.get(st, 0.0)
            ax.barh(i, w, left=left, height=0.56, color=SERIES[j], edgecolor=SURFACE, linewidth=2,
                    label=STEP_LABELS[st] if i == 0 else None)
            left += w
        ax.text(left + 6, i, f"RTO {float(chosen['rto_s']):.0f} s", va="center", color=INK, fontsize=11)
    ax.set_yticks(range(len(SCENARIOS)), [f"{LABELS[sc]} ({median_run(ok[sc])['run_id'].removeprefix('official-')})"
                                          for sc in SCENARIOS])
    ax.invert_yaxis()
    ax.set_xlabel("Thời gian (giây), lần đạt có RTO trung vị của mỗi tình huống")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.legend(ncol=3, loc="lower left", bbox_to_anchor=(0, 1.02), frameon=False, fontsize=11, handlelength=1.2)
    fig.savefig(out / "official-steps.png", bbox_inches="tight")
    plt.close(fig)
    made.append(out / "official-steps.png")

    k = kind_runs(kind_folder)
    groups = [(f"{LABELS[sc]} ({len(k[sc])} lần)", k[sc]) for sc in ["D1", "D2", "D3"] if k.get(sc)]
    fig, ax = plt.subplots(figsize=(7.4, 2.4))
    _strip(ax, groups, "RTO (giây)", None, jitter=0.18)
    fig.savefig(out / "kind-rto.png", bbox_inches="tight")
    plt.close(fig)
    made.append(out / "kind-rto.png")
    return made


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Vẽ biểu đồ RTO, RPO và thời gian từng bước cho báo cáo")
    p.add_argument("--out", type=Path, default=ROOT / "docs/bao-cao/hinh")
    p.add_argument("--kind", type=Path, default=ROOT / "data/kind/2026-11-08-gh42434189591")
    a = p.parse_args(argv)
    for f in render(a.out, a.kind):
        print(f.relative_to(ROOT) if f.is_relative_to(ROOT) else f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
