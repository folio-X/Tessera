"""Index computation.

Tessera publishes five values per fixing day:

  TCI  — composite, weighted average of the three sub-indexes
  TFC  — frontier closed (equal-weighted basket)
  TMC  — mid-tier closed (equal-weighted basket)
  TOI  — open (equal-weighted basket; per-model price = median across hosts)
  TCOS — frontier–open spread (absolute and percent)

All values are normalized to a base of 1000.00 on the launch date. The scale
factor for each sub-index is fixed on launch day so that the basket's mean
blended cost on that day maps to 1000.00. Subsequent days compute:

  sub_index(t) = scale_factor * mean_blended_cost(t)
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime

from .models import IndexSnapshot, Model, ModelPrice, Tier, Weights
from .normalize import blended_cost


class IndexCalculator:
    """Computes Tessera index values from a snapshot of model prices."""

    def __init__(self, models: list[Model], weights: Weights):
        self.models = models
        self.weights = weights
        self._models_by_tier: dict[Tier, list[Model]] = {
            Tier.FRONTIER_CLOSED: [],
            Tier.MID_TIER_CLOSED: [],
            Tier.OPEN: [],
        }
        for m in models:
            self._models_by_tier[m.tier].append(m)

    def compute(
        self,
        prices: list[ModelPrice],
        as_of: date,
        scale_factors: Mapping[str, float] | None = None,
    ) -> IndexSnapshot:
        """Compute the five index values for a given fixing day.

        On the launch day, pass `scale_factors=None` — this computes scale
        factors such that each sub-index equals `base_value`. On subsequent
        days, pass the launch-day scale factors so values float relative to
        base.
        """
        prices_by_model = self._group_prices(prices)

        tfc_basket = self._tier_blended_costs(Tier.FRONTIER_CLOSED, prices_by_model)
        tmc_basket = self._tier_blended_costs(Tier.MID_TIER_CLOSED, prices_by_model)
        toi_basket = self._open_basket(prices_by_model)

        tfc_mean = _mean(tfc_basket)
        tmc_mean = _mean(tmc_basket)
        toi_mean = _mean(toi_basket)

        if scale_factors is None:
            scale_factors = {
                "tfc": self.weights.base_value / tfc_mean if tfc_mean else 0.0,
                "tmc": self.weights.base_value / tmc_mean if tmc_mean else 0.0,
                "toi": self.weights.base_value / toi_mean if toi_mean else 0.0,
            }

        tfc = scale_factors["tfc"] * tfc_mean
        tmc = scale_factors["tmc"] * tmc_mean
        toi = scale_factors["toi"] * toi_mean

        tci = (
            self.weights.composite["frontier_closed"] * tfc
            + self.weights.composite["mid_tier_closed"] * tmc
            + self.weights.composite["open"] * toi
        )

        tcos_absolute = tfc - toi
        tcos_percent = (tfc - toi) / toi * 100 if toi else 0.0

        return IndexSnapshot(
            as_of=as_of,
            tci=round(tci, 2),
            tfc=round(tfc, 2),
            tmc=round(tmc, 2),
            toi=round(toi, 2),
            tcos_absolute=round(tcos_absolute, 2),
            tcos_percent=round(tcos_percent, 4),
            methodology_version=self.weights.methodology_version,
            prices=prices,
            has_stale=any(p.stale for p in prices),
        )

    def compute_launch_scale_factors(self, prices: list[ModelPrice]) -> dict[str, float]:
        """Pin the scale factors so each sub-index = base_value on launch day."""
        prices_by_model = self._group_prices(prices)
        tfc_mean = _mean(self._tier_blended_costs(Tier.FRONTIER_CLOSED, prices_by_model))
        tmc_mean = _mean(self._tier_blended_costs(Tier.MID_TIER_CLOSED, prices_by_model))
        toi_mean = _mean(self._open_basket(prices_by_model))
        return {
            "tfc": self.weights.base_value / tfc_mean if tfc_mean else 0.0,
            "tmc": self.weights.base_value / tmc_mean if tmc_mean else 0.0,
            "toi": self.weights.base_value / toi_mean if toi_mean else 0.0,
        }

    def _tier_blended_costs(
        self, tier: Tier, prices_by_model: Mapping[str, list[ModelPrice]]
    ) -> list[float]:
        """Equal-weighted blended cost per constituent in the given tier."""
        out: list[float] = []
        for m in self._models_by_tier[tier]:
            model_prices = prices_by_model.get(m.id, [])
            if not model_prices:
                continue
            # Closed-tier models have exactly one host (the provider).
            p = model_prices[0]
            out.append(
                blended_cost(
                    p.input_per_million,
                    p.output_per_million,
                    self.weights.blended_cost["input"],
                    self.weights.blended_cost["output"],
                )
            )
        return out

    def _open_basket(self, prices_by_model: Mapping[str, list[ModelPrice]]) -> list[float]:
        """For each open-tier model, use the median blended cost across hosts."""
        out: list[float] = []
        for m in self._models_by_tier[Tier.OPEN]:
            host_prices = prices_by_model.get(m.id, [])
            if not host_prices:
                continue
            blended = [
                blended_cost(
                    p.input_per_million,
                    p.output_per_million,
                    self.weights.blended_cost["input"],
                    self.weights.blended_cost["output"],
                )
                for p in host_prices
            ]
            out.append(statistics.median(blended))
        return out

    @staticmethod
    def _group_prices(prices: Iterable[ModelPrice]) -> dict[str, list[ModelPrice]]:
        grouped: dict[str, list[ModelPrice]] = {}
        for p in prices:
            grouped.setdefault(p.model_id, []).append(p)
        return grouped


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def utc_now() -> datetime:
    """UTC-aware current time. Pulled out so tests can monkeypatch."""
    return datetime.now(UTC)
