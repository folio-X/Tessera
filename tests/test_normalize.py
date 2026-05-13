"""Tests for unit normalization."""

from __future__ import annotations

import pytest

from tessera.normalize import blended_cost, to_per_million


class TestToPerMillion:
    def test_per_million_is_identity(self) -> None:
        assert to_per_million(15.0, "per_million") == 15.0

    def test_per_thousand_converts(self) -> None:
        # $0.015 per 1K tokens = $15 per 1M tokens
        assert to_per_million(0.015, "per_thousand") == pytest.approx(15.0)

    def test_per_character_converts(self) -> None:
        # $0.00001 per character * 4 chars/token * 1M = $40 per 1M tokens
        assert to_per_million(0.00001, "per_character") == pytest.approx(40.0)

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValueError, match="negative"):
            to_per_million(-1.0, "per_million")

    def test_ceiling_guard(self) -> None:
        # $50 per 1K = $50,000 per 1M — clearly a parse error
        with pytest.raises(ValueError, match="sanity ceiling"):
            to_per_million(50.0, "per_thousand")


class TestBlendedCost:
    def test_default_weights(self) -> None:
        # 0.7 * 10 + 0.3 * 30 = 7 + 9 = 16
        assert blended_cost(10.0, 30.0) == pytest.approx(16.0)

    def test_custom_weights(self) -> None:
        assert blended_cost(10.0, 30.0, 0.5, 0.5) == pytest.approx(20.0)

    def test_weights_must_sum_to_one(self) -> None:
        with pytest.raises(ValueError, match="sum to 1.0"):
            blended_cost(10.0, 30.0, 0.6, 0.6)

    def test_zero_output_only_input(self) -> None:
        assert blended_cost(10.0, 0.0) == pytest.approx(7.0)
