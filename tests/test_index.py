"""Tests for index calculation.

The launch-day invariant is: each sub-index equals base_value (1000.00).
On subsequent days, sub-indexes scale linearly with the basket's mean
blended cost.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from tessera.index import IndexCalculator
from tessera.models import Model, ModelPrice, Tier, Weights


def make_weights() -> Weights:
    return Weights(
        composite={"frontier_closed": 0.40, "mid_tier_closed": 0.30, "open": 0.30},
        blended_cost={"input": 0.70, "output": 0.30},
        base_value=1000.0,
        launch_date=date(2026, 5, 4),
        fixing_time_utc="16:00",
        methodology_version="1.0.0",
    )


def make_models() -> list[Model]:
    return [
        Model(
            id="frontier-a",
            display_name="Frontier A",
            provider="lab1",
            tier=Tier.FRONTIER_CLOSED,
            added=date(2026, 5, 4),
        ),
        Model(
            id="frontier-b",
            display_name="Frontier B",
            provider="lab2",
            tier=Tier.FRONTIER_CLOSED,
            added=date(2026, 5, 4),
        ),
        Model(
            id="mid-a",
            display_name="Mid A",
            provider="lab1",
            tier=Tier.MID_TIER_CLOSED,
            added=date(2026, 5, 4),
        ),
        Model(
            id="mid-b",
            display_name="Mid B",
            provider="lab2",
            tier=Tier.MID_TIER_CLOSED,
            added=date(2026, 5, 4),
        ),
        Model(
            id="open-a",
            display_name="Open A",
            provider="meta",
            tier=Tier.OPEN,
            added=date(2026, 5, 4),
            hosts=["together", "fireworks"],
        ),
        Model(
            id="open-b",
            display_name="Open B",
            provider="alibaba",
            tier=Tier.OPEN,
            added=date(2026, 5, 4),
            hosts=["together", "fireworks"],
        ),
    ]


def price(model_id: str, host: str | None, input_p: float, output_p: float) -> ModelPrice:
    return ModelPrice(
        model_id=model_id,
        provider="test",
        host=host,
        input_per_million=input_p,
        output_per_million=output_p,
        source_url="https://example.test",
        observed_at=datetime(2026, 5, 4, 16, 0, tzinfo=timezone.utc),
    )


def make_launch_prices() -> list[ModelPrice]:
    return [
        # Frontier blended: (0.7*5 + 0.3*25) = 11.0 each; mean = 11.0
        price("frontier-a", None, 5.0, 25.0),
        price("frontier-b", None, 5.0, 25.0),
        # Mid blended: (0.7*1 + 0.3*4) = 1.9 each; mean = 1.9
        price("mid-a", None, 1.0, 4.0),
        price("mid-b", None, 1.0, 4.0),
        # Open A across hosts: blended both = 1.0, median = 1.0
        price("open-a", "together", 1.0, 1.0),
        price("open-a", "fireworks", 1.0, 1.0),
        # Open B across hosts: blended both = 0.5, median = 0.5
        price("open-b", "together", 0.5, 0.5),
        price("open-b", "fireworks", 0.5, 0.5),
        # TOI mean = 0.75
    ]


class TestLaunchDay:
    def test_all_subindexes_equal_base_value(self) -> None:
        calc = IndexCalculator(make_models(), make_weights())
        snapshot = calc.compute(make_launch_prices(), date(2026, 5, 4))
        assert snapshot.tfc == 1000.00
        assert snapshot.tmc == 1000.00
        assert snapshot.toi == 1000.00
        assert snapshot.tci == 1000.00

    def test_tcos_zero_on_launch(self) -> None:
        calc = IndexCalculator(make_models(), make_weights())
        snapshot = calc.compute(make_launch_prices(), date(2026, 5, 4))
        assert snapshot.tcos_absolute == 0.0
        assert snapshot.tcos_percent == 0.0

    def test_methodology_version_in_snapshot(self) -> None:
        calc = IndexCalculator(make_models(), make_weights())
        snapshot = calc.compute(make_launch_prices(), date(2026, 5, 4))
        assert snapshot.methodology_version == "1.0.0"


class TestSubsequentDay:
    def test_frontier_doubles_when_blended_cost_doubles(self) -> None:
        calc = IndexCalculator(make_models(), make_weights())
        scale_factors = calc.compute_launch_scale_factors(make_launch_prices())

        doubled = make_launch_prices()
        # Double frontier blended cost on day +1.
        doubled[0] = price("frontier-a", None, 10.0, 50.0)
        doubled[1] = price("frontier-b", None, 10.0, 50.0)

        snap = calc.compute(doubled, date(2026, 5, 5), scale_factors=scale_factors)
        assert snap.tfc == pytest.approx(2000.00)
        assert snap.tmc == pytest.approx(1000.00)
        assert snap.toi == pytest.approx(1000.00)
        # TCI = 0.4*2000 + 0.3*1000 + 0.3*1000 = 800 + 300 + 300 = 1400
        assert snap.tci == pytest.approx(1400.00)

    def test_tcos_widens_when_frontier_rises(self) -> None:
        calc = IndexCalculator(make_models(), make_weights())
        scale_factors = calc.compute_launch_scale_factors(make_launch_prices())

        doubled = make_launch_prices()
        doubled[0] = price("frontier-a", None, 10.0, 50.0)
        doubled[1] = price("frontier-b", None, 10.0, 50.0)

        snap = calc.compute(doubled, date(2026, 5, 5), scale_factors=scale_factors)
        # TFC=2000, TOI=1000 → spread = 1000 abs, 100% relative
        assert snap.tcos_absolute == pytest.approx(1000.00)
        assert snap.tcos_percent == pytest.approx(100.0)


class TestOpenIndexMedian:
    def test_uses_median_not_mean_across_hosts(self) -> None:
        """A single host with anomalous pricing should not move the open index."""
        calc = IndexCalculator(make_models(), make_weights())
        prices = make_launch_prices()

        # Insert a third, very cheap host for open-a. Median of (1.0, 1.0, 0.1) = 1.0
        prices.append(price("open-a", "groq", 0.1, 0.1))
        snap = calc.compute(prices, date(2026, 5, 4))
        assert snap.toi == 1000.00


class TestStaleFlag:
    def test_has_stale_when_any_price_marked_stale(self) -> None:
        calc = IndexCalculator(make_models(), make_weights())
        prices = make_launch_prices()
        prices[0] = prices[0].model_copy(update={"stale": True})
        snap = calc.compute(prices, date(2026, 5, 5))
        assert snap.has_stale is True

    def test_no_stale_when_all_fresh(self) -> None:
        calc = IndexCalculator(make_models(), make_weights())
        snap = calc.compute(make_launch_prices(), date(2026, 5, 4))
        assert snap.has_stale is False


class TestRealRegistry:
    """Smoke test against the real data/models.yaml + weights.yaml."""

    def test_real_registry_loads_and_computes(self) -> None:
        from tessera.models import load_models, load_weights

        models = load_models()
        weights = load_weights()
        assert weights.base_value == 1000.0
        assert weights.composite["frontier_closed"] == 0.40
        # Three tiers must each contain models.
        from collections import Counter

        counts = Counter(m.tier for m in models)
        assert counts[Tier.FRONTIER_CLOSED] >= 3
        assert counts[Tier.MID_TIER_CLOSED] >= 3
        assert counts[Tier.OPEN] >= 3
