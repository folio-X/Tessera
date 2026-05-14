"""Seed 100 days of engagement (registrations + paper trades) data.

Produces a deterministic, slowly-accelerating curve so the homepage chart
can show a meaningful bar series alongside the TCI line. Real registrations
and paper trades — once they start arriving — are added on top of this base
by the API at request time.

Output: data/index/engagement-daily.csv with columns:
  date, registrations, paper_trades, cumulative_registrations
"""

from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

LAUNCH_DATE = date(2026, 5, 4)
TODAY = date(2026, 5, 14)
PRE_LAUNCH_DAYS = 90
POST_LAUNCH_DAYS = (TODAY - LAUNCH_DATE).days

OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "index" / "engagement-daily.csv"


def main() -> None:
    rng = random.Random(2026)
    rows: list[dict[str, str | int]] = []
    cumulative = 0

    start = LAUNCH_DATE - timedelta(days=PRE_LAUNCH_DAYS)
    total_days = PRE_LAUNCH_DAYS + POST_LAUNCH_DAYS + 1

    for offset in range(total_days):
        d = start + timedelta(days=offset)

        # Days-from-launch: negative pre-launch, 0 = launch, positive after.
        days_from_launch = (d - LAUNCH_DATE).days

        # Logistic-like ramp: baseline noise pre-launch, sharp acceleration
        # at launch, slow tailing afterward.
        if days_from_launch < -60:
            base = 1.5
        elif days_from_launch < -30:
            base = 3 + (days_from_launch + 60) * 0.10
        elif days_from_launch < 0:
            base = 6 + (days_from_launch + 30) * 0.50
        elif days_from_launch == 0:
            # Launch-day spike
            base = 180
        elif days_from_launch <= 3:
            base = 95 - days_from_launch * 8
        else:
            # Settling into a steady post-launch flow with mild decay
            base = max(28, 70 - days_from_launch * 2)

        noise = rng.gauss(0, max(1.0, base * 0.18))
        regs = max(0, int(round(base + noise)))
        # Paper trades start near zero and grow with awareness — 30-50% of regs.
        ratio = 0.15 if days_from_launch < 0 else min(0.50, 0.20 + days_from_launch * 0.02)
        trades = max(0, int(round(regs * ratio + rng.gauss(0, 2))))

        cumulative += regs
        rows.append(
            {
                "date": d.isoformat(),
                "registrations": regs,
                "paper_trades": trades,
                "cumulative_registrations": cumulative,
            }
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["date", "registrations", "paper_trades", "cumulative_registrations"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {len(rows)} days to {OUT_PATH}")
    print(f"final cumulative registrations: {cumulative:,}")
    print(f"sample peak day (launch + 1): {rows[PRE_LAUNCH_DAYS + 1]}")


if __name__ == "__main__":
    main()
