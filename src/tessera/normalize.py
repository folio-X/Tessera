"""Unit normalization for scraped prices.

Providers publish in different units: per 1K tokens, per 1M tokens, per character.
The methodology requires USD per million tokens. This module converts.
"""

from __future__ import annotations

from typing import Literal

# Per-million is the canonical Tessera unit.
PER_MILLION = 1_000_000

# 1 token ≈ 4 characters under most tokenizers. We use this for character-priced
# providers (rare in 2026 — Google previously used per-character pricing for
# PaLM). If a provider migrates to characters, this constant goes through review.
CHARS_PER_TOKEN = 4.0

PriceUnit = Literal["per_thousand", "per_million", "per_character"]


def to_per_million(price: float, unit: PriceUnit) -> float:
    """Convert a price in the given source unit to USD per million tokens.

    Raises ValueError on negative or absurdly large prices (sanity guard —
    real LLM list prices are between $0.05 and $200 per million tokens).
    """
    if price < 0:
        raise ValueError(f"negative price: {price}")

    if unit == "per_million":
        result = price
    elif unit == "per_thousand":
        result = price * 1_000
    elif unit == "per_character":
        result = price * CHARS_PER_TOKEN * PER_MILLION
    else:  # pragma: no cover — exhaustive
        raise ValueError(f"unknown unit: {unit}")

    if result > 1_000:
        raise ValueError(
            f"normalized price {result:.2f}/M tokens exceeds sanity ceiling — "
            f"likely a parsing error, not a real LLM list price"
        )
    return result


def blended_cost(
    input_per_million: float,
    output_per_million: float,
    input_weight: float = 0.70,
    output_weight: float = 0.30,
) -> float:
    """Compute the 70/30 blended cost per million tokens for a single model."""
    if not _approx_equal(input_weight + output_weight, 1.0):
        raise ValueError(
            f"blended_cost weights must sum to 1.0, got {input_weight:.4f} + {output_weight:.4f}"
        )
    return input_weight * input_per_million + output_weight * output_per_million


def _approx_equal(a: float, b: float, eps: float = 1e-6) -> bool:
    return abs(a - b) < eps
