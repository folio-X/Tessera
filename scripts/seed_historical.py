"""Seed 90 days of historical Tessera index data.

This script does NOT replace real scrapers. It produces a deterministic,
plausible-looking time series for the website to render against until live
scrapers are running. Every row is clearly marked as seed data in the
snapshot's `notes` field.

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
HISTORY_DAYS = 90

# Reference prices on launch day (USD per million tokens). Manually researched
# from current public pricing pages and labelled as seed in the snapshots.
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


def prices_for_day(
    models: list[Model],
    day_offset: int,
    *,
    rng: random.Random,
) -> list[ModelPrice]:
    """Generate a plausible per-model price record for the given day offset.

    Day 0 = launch day (uses the reference prices verbatim). Earlier days drift
    upward slightly to create a downward-sloping series; jitter is small to
    keep the chart readable but visible.
    """
    # Launch day uses pristine reference prices so the index lands at 1000.00
    # exactly on day 0. Older days get drift + jitter so the chart has texture.
    is_launch = day_offset == 0
    drift = 1.0 + 0.0008 * day_offset
    observed = datetime.combine(
        LAUNCH_DATE - timedelta(days=day_offset),
        datetime.min.time(),
        tzinfo=UTC,
    ).replace(hour=16)
    prices: list[ModelPrice] = []

    for model in models:
        record = LAUNCH_PRICES[model.id]
        if model.tier == Tier.OPEN:
            hosts = record["hosts"]  # type: ignore[index]
            assert isinstance(hosts, dict)
            for host, p in hosts.items():
                jitter = 1.0 if is_launch else 1.0 + (rng.random() - 0.5) * 0.015
                prices.append(
                    ModelPrice(
                        model_id=model.id,
                        provider=model.provider,
                        host=host,
                        input_per_million=round(p["input"] * drift * jitter, 4),
                        output_per_million=round(p["output"] * drift * jitter, 4),
                        source_url=f"https://{host}.ai/pricing",
                        observed_at=observed,
                        notes="seed",
                    )
                )
        else:
            input_p = record["input"]  # type: ignore[index]
            output_p = record["output"]  # type: ignore[index]
            jitter = 1.0 if is_launch else 1.0 + (rng.random() - 0.5) * 0.01
            prices.append(
                ModelPrice(
                    model_id=model.id,
                    provider=model.provider,
                    input_per_million=round(float(input_p) * drift * jitter, 4),
                    output_per_million=round(float(output_p) * drift * jitter, 4),
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

    launch_prices = prices_for_day(models, day_offset=0, rng=rng)
    launch_factors = calculator.compute_launch_scale_factors(launch_prices)

    factors_path = default_repo_root() / "data" / "index" / "launch-scale-factors.json"
    factors_path.parent.mkdir(parents=True, exist_ok=True)
    factors_path.write_text(json.dumps(launch_factors, indent=2))

    # Walk forward from oldest to newest so the CSV ends up sorted.
    for day_offset in range(HISTORY_DAYS, -1, -1):
        prices = prices_for_day(models, day_offset, rng=rng)
        as_of = LAUNCH_DATE - timedelta(days=day_offset)
        snapshot = calculator.compute(prices, as_of, scale_factors=launch_factors)
        write_snapshot(snapshot)
        append_daily_csv(snapshot)

    csv_path = default_repo_root() / "data" / "index" / "tessera-daily.csv"
    line_count = sum(1 for _ in csv_path.open()) - 1
    print(f"seeded {line_count} fixing days; wrote {csv_path}")
    print(f"launch scale factors: {launch_factors}")


if __name__ == "__main__":
    main()
