"""Sanity validators applied to scraped prices before they enter the index.

The methodology explicitly forbids invention or interpolation of prices.
Validators may *reject* a scraped value (forcing a STALE fallback to the
previous day), but they may never *change* it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .models import ModelPrice

logger = logging.getLogger(__name__)

# Hard floor — no LLM has list-priced below $0.01/M tokens. A scraped value
# below this is almost certainly a parsing error (missing a digit, decimal
# point misread).
MIN_PRICE_PER_MILLION = 0.01

# Hard ceiling — current frontier output prices peak around $75/M tokens. If
# we ever see >$1000/M, it's almost certainly a parse error.
MAX_PRICE_PER_MILLION = 1_000.00

# Day-over-day price changes >50% trigger a manual review. Real list-price
# moves of this magnitude are rare and worth a human looking at.
DOD_REVIEW_THRESHOLD = 0.50


@dataclass
class ValidationResult:
    accepted: list[ModelPrice]
    rejected: list[tuple[ModelPrice, str]]
    needs_review: list[tuple[ModelPrice, str]]


def validate_prices(
    fresh: list[ModelPrice], previous: list[ModelPrice] | None = None
) -> ValidationResult:
    """Apply sanity validators. Does not mutate inputs."""
    accepted: list[ModelPrice] = []
    rejected: list[tuple[ModelPrice, str]] = []
    needs_review: list[tuple[ModelPrice, str]] = []

    previous_by_key: dict[tuple[str, str | None], ModelPrice] = {}
    if previous:
        for p in previous:
            previous_by_key[(p.model_id, p.host)] = p

    for price in fresh:
        if not _in_range(price.input_per_million):
            rejected.append((price, f"input price out of range: {price.input_per_million}"))
            continue
        if not _in_range(price.output_per_million):
            rejected.append((price, f"output price out of range: {price.output_per_million}"))
            continue

        prev = previous_by_key.get((price.model_id, price.host))
        if prev:
            review_reason = _dod_review_reason(price, prev)
            if review_reason:
                needs_review.append((price, review_reason))

        accepted.append(price)

    return ValidationResult(accepted=accepted, rejected=rejected, needs_review=needs_review)


def _in_range(price: float) -> bool:
    return MIN_PRICE_PER_MILLION <= price <= MAX_PRICE_PER_MILLION


def _dod_review_reason(fresh: ModelPrice, previous: ModelPrice) -> str | None:
    """Return a human-readable reason if the day-over-day change is >50%, else None."""
    for label, fresh_val, prev_val in (
        ("input", fresh.input_per_million, previous.input_per_million),
        ("output", fresh.output_per_million, previous.output_per_million),
    ):
        if prev_val <= 0:
            continue
        change = abs(fresh_val - prev_val) / prev_val
        if change > DOD_REVIEW_THRESHOLD:
            return (
                f"{label} price moved {change:.0%} day-over-day ({prev_val:.2f} → {fresh_val:.2f})"
            )
    return None
