#!/usr/bin/env python3
"""Deprecated dashboard-generator compatibility entry point.

The former implementation authored road corridors, settlement populations,
exposure totals, geological explanations, and emergency priorities by hand.
Those values are not valid GIS exposure and must never overwrite the live
dashboard. This wrapper delegates to the provenance-safe operational updater,
which uses the canonical grid, real OSM geometries, and current risk layer.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compatibility wrapper for the provenance-safe dashboard updater"
    )
    parser.add_argument(
        "--mode",
        default="live",
        choices=["live", "storm", "dry"],
        help="Live Open-Meteo update or explicitly labelled simulation mode",
    )
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()
    updater = Path(__file__).with_name("12_hourly_cloud_updater.py")
    print(
        "Legacy synthetic dashboard generation is retired; delegating to "
        "the provenance-safe operational risk and GIS exposure pipeline."
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(updater),
            "--mode",
            args.mode,
            "--timeout-seconds",
            str(args.timeout_seconds),
        ],
        check=False,
    )
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
