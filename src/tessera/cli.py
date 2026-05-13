"""Tessera CLI.

Three commands:

  tessera scrape [--provider X]   run scrapers, print prices (no commit)
  tessera compute --date YYYY-MM-DD   recompute the index from existing snapshot
  tessera daily-run               full pipeline: scrape → validate → compute → write
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime

import click

from .index import IndexCalculator
from .models import ModelPrice, load_models, load_weights
from .scrapers import ALL_SCRAPERS
from .storage import (
    append_daily_csv,
    daily_csv_path,
    default_repo_root,
    load_yesterday_prices,
    snapshot_path,
    write_snapshot,
)
from .validators import validate_prices


@click.group()
def main() -> None:
    """Tessera index pipeline CLI."""


@main.command()
@click.option("--provider", help="Run only one provider (default: all)")
def scrape(provider: str | None) -> None:
    """Run scrapers and print results without committing."""
    providers = [provider] if provider else list(ALL_SCRAPERS.keys())
    cache_root = default_repo_root() / "data" / "snapshots" / "raw"
    today = datetime.now(UTC).date()

    for name in providers:
        cls = ALL_SCRAPERS.get(name)
        if cls is None:
            click.echo(f"unknown provider: {name}", err=True)
            sys.exit(2)
        with cls(cache_root=cache_root) as scraper:
            try:
                prices = scraper.run(today=today)
            except Exception as exc:  # noqa: BLE001 - report and continue
                click.echo(f"[{name}] FAILED: {exc}", err=True)
                continue
            for p in prices:
                click.echo(
                    f"[{name}] {p.model_id}  in=${p.input_per_million}  out=${p.output_per_million}"
                )


@main.command()
@click.option("--date", "as_of", required=True, type=click.DateTime(formats=["%Y-%m-%d"]))
def compute(as_of: datetime) -> None:
    """Recompute the index from an existing daily snapshot."""
    target = as_of.date()
    path = snapshot_path(target)
    if not path.exists():
        click.echo(f"no snapshot at {path}", err=True)
        sys.exit(1)

    data = json.loads(path.read_text())
    prices = [ModelPrice.model_validate(p) for p in data["prices"]]
    models = load_models()
    weights = load_weights()
    calc = IndexCalculator(models, weights)

    launch_factors = _load_launch_factors(weights.launch_date)
    snapshot = calc.compute(prices, target, scale_factors=launch_factors)
    click.echo(snapshot.model_dump_json(indent=2))


@main.command(name="daily-run")
@click.option(
    "--date",
    "as_of",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Fixing date, defaults to today (UTC)",
)
@click.option("--dry-run", is_flag=True, help="Compute but do not write files")
def daily_run(as_of: datetime | None, dry_run: bool) -> None:
    """Full daily pipeline: scrape, validate, compute, persist."""
    target = as_of.date() if as_of else datetime.now(UTC).date()
    cache_root = default_repo_root() / "data" / "snapshots" / "raw"

    fresh: list[ModelPrice] = []
    failures: list[str] = []
    for name, cls in ALL_SCRAPERS.items():
        with cls(cache_root=cache_root) as scraper:
            try:
                fresh.extend(scraper.run(today=target))
            except Exception as exc:  # noqa: BLE001 - tolerate, fall back to stale
                failures.append(f"{name}: {exc}")

    yesterday_prices = load_yesterday_prices(target)
    fresh = _fill_stale_from_yesterday(fresh, yesterday_prices)

    result = validate_prices(fresh, previous=yesterday_prices)
    for rejected, reason in result.rejected:
        click.echo(f"REJECTED {rejected.model_id}@{rejected.host}: {reason}", err=True)
    for review, reason in result.needs_review:
        click.echo(f"REVIEW   {review.model_id}@{review.host}: {reason}", err=True)

    models = load_models()
    weights = load_weights()
    calc = IndexCalculator(models, weights)

    launch_factors = _load_launch_factors(weights.launch_date)
    snapshot = calc.compute(result.accepted, target, scale_factors=launch_factors)

    if dry_run:
        click.echo(snapshot.model_dump_json(indent=2))
        return

    write_snapshot(snapshot)
    append_daily_csv(snapshot)
    click.echo(f"wrote {snapshot_path(target)} and updated {daily_csv_path()}")
    if failures:
        click.echo(f"WARNING: {len(failures)} scrapers failed", err=True)


def _fill_stale_from_yesterday(
    fresh: list[ModelPrice], yesterday: list[ModelPrice]
) -> list[ModelPrice]:
    """For any (model, host) present yesterday but missing today, carry forward
    yesterday's value with stale=True."""
    fresh_keys = {(p.model_id, p.host) for p in fresh}
    out = list(fresh)
    for prev in yesterday:
        if (prev.model_id, prev.host) not in fresh_keys:
            out.append(prev.model_copy(update={"stale": True}))
    return out


def _load_launch_factors(launch_date: date) -> dict[str, float] | None:
    """Load pinned launch-day scale factors. Returns None if no launch snapshot
    exists yet (first run = launch day)."""
    path = snapshot_path(launch_date)
    if not path.exists():
        return None
    factors_path = default_repo_root() / "data" / "index" / "launch-scale-factors.json"
    if factors_path.exists():
        raw: dict[str, float] = json.loads(factors_path.read_text())
        return raw
    return None


if __name__ == "__main__":
    main()
