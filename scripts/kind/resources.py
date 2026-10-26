from __future__ import annotations

import argparse
import csv
import shutil
import signal
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

FIELDS = ["time_utc", "mem_total_mb", "mem_used_mb", "disk_total_gb", "disk_used_gb"]


def parse_meminfo(text: str) -> tuple[int, int]:
    values = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        if rest.strip():
            values[key] = int(rest.split()[0])
    total = values["MemTotal"] // 1024
    return total, total - values["MemAvailable"] // 1024


def sample(path: Path = Path("/")) -> dict:
    total, used = parse_meminfo(Path("/proc/meminfo").read_text())
    disk = shutil.disk_usage(path)
    return {
        "time_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mem_total_mb": total, "mem_used_mb": used,
        "disk_total_gb": round(disk.total / 1e9, 2), "disk_used_gb": round(disk.used / 1e9, 2),
    }


def peak(rows: list[dict]) -> dict:
    if not rows:
        return {}
    first = rows[0]
    top_mem = max(rows, key=lambda r: float(r["mem_used_mb"]))
    top_disk = max(rows, key=lambda r: float(r["disk_used_gb"]))
    return {
        "samples": len(rows),
        "mem_total_mb": int(float(first["mem_total_mb"])),
        "mem_peak_mb": int(float(top_mem["mem_used_mb"])),
        "mem_baseline_mb": int(float(first["mem_used_mb"])),
        "disk_total_gb": float(first["disk_total_gb"]),
        "disk_peak_used_gb": float(top_disk["disk_used_gb"]),
        "disk_baseline_used_gb": float(first["disk_used_gb"]),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m scripts.kind.resources")
    p.add_argument("command", choices=["sample", "peak"])
    p.add_argument("csv", nargs="+", type=Path)
    p.add_argument("--interval", type=float, default=5)
    a = p.parse_args(argv)
    if a.command == "peak":
        rows = []
        for f in a.csv:
            with f.open(newline="") as fh:
                rows.extend(csv.DictReader(fh))
        for k, v in peak(rows).items():
            print(f"{k}={v}")
        return 0
    out = a.csv[0]
    out.parent.mkdir(parents=True, exist_ok=True)
    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    new = not out.exists()
    with out.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        if new:
            w.writeheader()
        while running:
            w.writerow(sample())
            f.flush()
            time.sleep(a.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
