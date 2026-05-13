"""Tests for the price-validation pipeline."""

from __future__ import annotations

from datetime import datetime, timezone

from tessera.models import ModelPrice
from tessera.validators import (
    DOD_REVIEW_THRESHOLD,
    MAX_PRICE_PER_MILLION,
    MIN_PRICE_PER_MILLION,
    validate_prices,
)


def price(model_id: str, input_p: float, output_p: float) -> ModelPrice:
    return ModelPrice(
        model_id=model_id,
        provider="test",
        input_per_million=input_p,
        output_per_million=output_p,
        source_url="https://example.test",
        observed_at=datetime(2026, 5, 4, 16, 0, tzinfo=timezone.utc),
    )


def test_accepts_normal_price() -> None:
    result = validate_prices([price("m1", 5.0, 15.0)])
    assert len(result.accepted) == 1
    assert not result.rejected


def test_rejects_below_floor() -> None:
    result = validate_prices([price("m1", MIN_PRICE_PER_MILLION / 2, 15.0)])
    assert len(result.accepted) == 0
    assert len(result.rejected) == 1


def test_rejects_above_ceiling() -> None:
    result = validate_prices([price("m1", MAX_PRICE_PER_MILLION * 2, 15.0)])
    assert len(result.accepted) == 0
    assert len(result.rejected) == 1


def test_flags_large_dod_move_for_review() -> None:
    prev = [price("m1", 5.0, 15.0)]
    # >50% move on input
    fresh = [price("m1", 5.0 * (1 + DOD_REVIEW_THRESHOLD + 0.1), 15.0)]
    result = validate_prices(fresh, previous=prev)
    assert len(result.accepted) == 1, "price still accepted; review is non-blocking"
    assert len(result.needs_review) == 1
    assert "input" in result.needs_review[0][1]


def test_small_dod_move_not_flagged() -> None:
    prev = [price("m1", 5.0, 15.0)]
    fresh = [price("m1", 5.05, 15.0)]
    result = validate_prices(fresh, previous=prev)
    assert not result.needs_review
