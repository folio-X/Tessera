"""Persistence for daily snapshots and the rolling tessera-daily.csv.

A daily snapshot is written to `data/snapshots/YYYY-MM-DD.json` with full
provenance (every price, every source URL). The compact roll-up file at
`data/index/tessera-daily.csv` is appended one row per fixing day.

The CSV is the canonical data feed read by the public website and by
downstream consumers.
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from .models import IndexSnapshot, ModelPrice

CSV_HEADER = [
    "date",
    "tci",
    "tfc",
    "tmc",
    "toi",
    "tcos_absolute",
    "tcos_percent",
    "methodology_version",
    "has_stale",
]


def default_repo_root() -> Path:
    """Repo root, resolved from this module's location."""
    return Path(__file__).resolve().parents[2]


def snapshot_path(as_of: date, root: Path | None = None) -> Path:
    root = root or default_repo_root()
    return root / "data" / "snapshots" / f"{as_of.isoformat()}.json"


def daily_csv_path(root: Path | None = None) -> Path:
    root = root or default_repo_root()
    return root / "data" / "index" / "tessera-daily.csv"


def write_snapshot(snapshot: IndexSnapshot, root: Path | None = None) -> Path:
    """Write the per-day snapshot JSON. Overwrites if exists (corrections policy
    requires explicit CHANGELOG entries, not silent file rewrites — callers
    should check before overwriting in production)."""
    path = snapshot_path(snapshot.as_of, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(snapshot.model_dump_json(indent=2))
    return path


def append_daily_csv(snapshot: IndexSnapshot, root: Path | None = None) -> Path:
    """Append a row to data/index/tessera-daily.csv. Creates the file with
    header if missing. If a row already exists for this date, replaces it."""
    path = daily_csv_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    if path.exists():
        with path.open() as f:
            rows = [r for r in csv.DictReader(f) if r["date"] != snapshot.as_of.isoformat()]

    rows.append(
        {
            "date": snapshot.as_of.isoformat(),
            "tci": f"{snapshot.tci:.2f}",
            "tfc": f"{snapshot.tfc:.2f}",
            "tmc": f"{snapshot.tmc:.2f}",
            "toi": f"{snapshot.toi:.2f}",
            "tcos_absolute": f"{snapshot.tcos_absolute:.2f}",
            "tcos_percent": f"{snapshot.tcos_percent:.4f}",
            "methodology_version": snapshot.methodology_version,
            "has_stale": "true" if snapshot.has_stale else "false",
        }
    )

    rows.sort(key=lambda r: r["date"])

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(rows)

    return path


def load_yesterday_prices(as_of: date, root: Path | None = None) -> list[ModelPrice]:
    """Load the previous fixing day's prices, used to carry forward STALE values.

    Returns [] if there is no prior snapshot.
    """
    root = root or default_repo_root()
    snaps = sorted((root / "data" / "snapshots").glob("*.json"))
    snaps = [p for p in snaps if p.stem < as_of.isoformat()]
    if not snaps:
        return []
    data = json.loads(snaps[-1].read_text())
    return [ModelPrice.model_validate(p) for p in data["prices"]]
