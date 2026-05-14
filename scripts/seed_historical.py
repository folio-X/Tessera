"""Seed 90 days of historical Tessera index data.

This script does NOT replace real scrapers. It produces a deterministic,
plausible-looking time series for the website to render against until live
scrapers are running. Every row is clearly marked as seed data in the
snapshot's `notes` field.

Methodology of the seed:
  - Launch day (offset 0) uses the pristine reference prices below, so each
    sub-index lands at exactly 1000.00 on the fixing day.
  - For days BEFORE launch we generate a random walk *anchored* to those
    reference prices. There is no built-in drift — the series wanders up and
    down around the reference but doesn't trend, because at index launch we
    have no real history to claim a direction for.
  - The walk uses a fixed seed so the seed file is reproducible.

Run:
    python scripts/seed_historical.py
"""

from __future__ import annotations

import json
import random
from datetime import UTC, date, datetime, timedelta

from tessera.index import IndexCalculator
from tessera.models import Model, ModelPrice, Tier, load_models, load_weights
from tessera.storage import append_daily_csv, default_repo_root, write_snapshot

LAUNCH_DATE = date(2026, 5, 4)
# Days of pre-launch synthetic backfill (so the website has a 90-day chart
# from day one). These are labeled `notes: "seed"` in every record.
PRE_LAUNCH_DAYS = 90
# Days of post-launch random walk to extend through today. Real scrapers
# will replace these once the daily-update workflow runs.
TODAY = date(2026, 5, 14)
POST_LAUNCH_DAYS = (TODAY - LAUNCH_DATE).days

# Daily volatility (standard deviation of log-return) applied to each model
# price in the random walk. ~0.4% is realistic for list-price movement —
# providers don't reprice every day, but the cross-section of constituents
# combined gives the index this much daily flicker.
DAILY_SIGMA = 0.004

# Mean-reversion strength toward the launch-day reference. 0.0 = pure random
# walk (can drift arbitrarily far), 1.0 = always at reference. A small value
# keeps the walk realistic but prevents the 90-day endpoint from being
# unrealistically far from launch.
MEAN_REVERSION = 0.04

# Reference prices on launch day (USD per million tokens). Manually researched
# from current public pricing pages.
LAUNCH_PRICES: dict[str, dict[str, float | dict[str, dict[str, float]]]] = {
    # Frontier Closed
    "openai-gpt-5": {"input": 1.25, "output": 10.00},
    "anthropic-claude-opus-4-7": {"input": 15.00, "output": 75.00},
    "google-gemini-2-5-pro": {"input": 1.25, "output": 10.00},
    # Mid-Tier Closed
    "openai-gpt-5-mini": {"input": 0.25, "output": 2.00},
    "anthropic-claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    "google-gemini-2-5-flash": {"input": 0.30, "output": 2.50},
    # Open — per-host prices
    "meta-llama-3-1-70b-instruct": {
        "hosts": {
            "together": {"input": 0.88, "output": 0.88},
            "fireworks": {"input": 0.90, "output": 0.90},
            "groq": {"input": 0.59, "output": 0.79},
            "deepinfra": {"input": 0.35, "output": 0.40},
            "replicate": {"input": 0.65, "output": 2.75},
        }
    },
    "alibaba-qwen-2-5-72b-instruct": {
        "hosts": {
            "together": {"input": 1.20, "output": 1.20},
            "fireworks": {"input": 0.90, "output": 0.90},
            "deepinfra": {"input": 0.35, "output": 0.40},
        }
    },
    "deepseek-v3": {
        "hosts": {
            "together": {"input": 1.25, "output": 1.25},
            "fireworks": {"input": 0.90, "output": 0.90},
            "deepinfra": {"input": 0.49, "output": 0.89},
        }
    },
}


def reference_per_host_prices() -> dict[tuple[str, str | None], tuple[float, float]]:
    """Flatten LAUNCH_PRICES into a (model_id, host) → (input, output) dict."""
    out: dict[tuple[str, str | None], tuple[float, float]] = {}
    for model_id, record in LAUNCH_PRICES.items():
        if "hosts" in record:
            hosts = record["hosts"]
            assert isinstance(hosts, dict)
            for host, p in hosts.items():
                out[(model_id, host)] = (p["input"], p["output"])
        else:
            input_p = float(record["input"])  # type: ignore[arg-type]
            output_p = float(record["output"])  # type: ignore[arg-type]
            out[(model_id, None)] = (input_p, output_p)
    return out


def _step(
    current: dict[tuple[str, str | None], tuple[float, float]],
    reference: dict[tuple[str, str | None], tuple[float, float]],
    rng: random.Random,
) -> dict[tuple[str, str | None], tuple[float, float]]:
    """One day of mean-reverting random-walk steps for every (model, host)."""
    nxt: dict[tuple[str, str | None], tuple[float, float]] = {}
    for key, (ref_in, ref_out) in reference.items():
        cur_in, cur_out = current[key]
        shock_in = rng.gauss(0.0, DAILY_SIGMA)
        shock_out = rng.gauss(0.0, DAILY_SIGMA)
        pulled_in = cur_in + MEAN_REVERSION * (ref_in - cur_in)
        pulled_out = cur_out + MEAN_REVERSION * (ref_out - cur_out)
        new_in = round(max(0.05, pulled_in * (1.0 + shock_in)), 4)
        new_out = round(max(0.05, pulled_out * (1.0 + shock_out)), 4)
        nxt[key] = (new_in, new_out)
    return nxt


def build_walk(
    reference: dict[tuple[str, str | None], tuple[float, float]],
    rng: random.Random,
) -> dict[date, dict[tuple[str, str | None], tuple[float, float]]]:
    """Build the full per-(model, host) price walk.

    The walk is anchored on launch day at the exact reference values, walks
    backward in time for PRE_LAUNCH_DAYS days (synthetic backfill), and
    forward in time for POST_LAUNCH_DAYS days (real-launched series wandering
    away from 1000). Both halves use the same mean-reverting random walk so
    the series has consistent texture.
    """
    series: dict[date, dict[tuple[str, str | None], tuple[float, float]]] = {}
    series[LAUNCH_DATE] = dict(reference)

    # Walk BACKWARD from launch day to fill the pre-launch chart.
    current = dict(reference)
    for offset in range(1, PRE_LAUNCH_DAYS + 1):
        current = _step(current, reference, rng)
        series[LAUNCH_DATE - timedelta(days=offset)] = current

    # Walk FORWARD from launch day to today.
    current = dict(reference)
    for offset in range(1, POST_LAUNCH_DAYS + 1):
        current = _step(current, reference, rng)
        series[LAUNCH_DATE + timedelta(days=offset)] = current

    return series


def prices_for_day(
    models: list[Model],
    as_of: date,
    walk: dict[date, dict[tuple[str, str | None], tuple[float, float]]],
) -> list[ModelPrice]:
    """Build ModelPrice records for a given fixing date from the prebuilt walk."""
    observed = datetime.combine(as_of, datetime.min.time(), tzinfo=UTC).replace(hour=16)
    day_prices = walk[as_of]
    prices: list[ModelPrice] = []

    for model in models:
        if model.tier == Tier.OPEN:
            for host in model.hosts:
                in_p, out_p = day_prices[(model.id, host)]
                prices.append(
                    ModelPrice(
                        model_id=model.id,
                        provider=model.provider,
                        host=host,
                        input_per_million=in_p,
                        output_per_million=out_p,
                        source_url=f"https://{host}.ai/pricing",
                        observed_at=observed,
                        notes="seed",
                    )
                )
        else:
            in_p, out_p = day_prices[(model.id, None)]
            prices.append(
                ModelPrice(
                    model_id=model.id,
                    provider=model.provider,
                    input_per_million=in_p,
                    output_per_million=out_p,
                    source_url=f"https://{model.provider}.com/api/pricing",
                    observed_at=observed,
                    notes="seed",
                )
            )
    return prices


def main() -> None:
    models = load_models()
    weights = load_weights()
    calculator = IndexCalculator(models, weights)
    rng = random.Random(42)

    reference = reference_per_host_prices()
    walk = build_walk(reference, rng)

    launch_prices = prices_for_day(models, LAUNCH_DATE, walk)
    launch_factors = calculator.compute_launch_scale_factors(launch_prices)

    factors_path = default_repo_root() / "data" / "index" / "launch-scale-factors.json"
    factors_path.parent.mkdir(parents=True, exist_ok=True)
    factors_path.write_text(json.dumps(launch_factors, indent=2))

    # Emit oldest → newest so the CSV ends up sorted.
    for as_of in sorted(walk.keys()):
        prices = prices_for_day(models, as_of, walk)
        snapshot = calculator.compute(prices, as_of, scale_factors=launch_factors)
        write_snapshot(snapshot)
        append_daily_csv(snapshot)

    csv_path = default_repo_root() / "data" / "index" / "tessera-daily.csv"
    line_count = sum(1 for _ in csv_path.open()) - 1
    print(f"seeded {line_count} fixing days; wrote {csv_path}")
    print(f"launch scale factors: {launch_factors}")


if __name__ == "__main__":
    main()
