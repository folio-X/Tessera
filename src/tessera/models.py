"""Model registry + core domain types.

A `Model` is a single LLM constituent of the index. A `ModelPrice` is a
scraped price record for a model at a point in time. The registry is loaded
from `data/models.yaml`.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class Tier(StrEnum):
    FRONTIER_CLOSED = "frontier_closed"
    MID_TIER_CLOSED = "mid_tier_closed"
    OPEN = "open"


class Model(BaseModel):
    """A constituent of the Tessera index."""

    id: str
    display_name: str
    provider: str
    tier: Tier
    added: date
    pricing_url: str | None = None
    api_model_id: str | None = None
    hosts: list[str] = Field(default_factory=list)


class ModelPrice(BaseModel):
    """A scraped price record for a single model at a point in time.

    All prices are USD per million tokens, standard tier, public list price.
    """

    model_id: str
    provider: str
    host: str | None = None
    input_per_million: float
    output_per_million: float
    currency: Literal["USD"] = "USD"
    source_url: str
    observed_at: datetime
    stale: bool = False
    notes: str | None = None


class IndexSnapshot(BaseModel):
    """A single fixing day's published values, with computation provenance."""

    as_of: date
    tci: float
    tfc: float
    tmc: float
    toi: float
    tcos_absolute: float
    tcos_percent: float
    methodology_version: str
    prices: list[ModelPrice]
    has_stale: bool = False


def load_models(models_path: Path | str | None = None) -> list[Model]:
    """Load the canonical model registry from data/models.yaml."""
    path = Path(models_path) if models_path else default_models_path()
    raw = yaml.safe_load(path.read_text())
    return [Model.model_validate(m) for m in raw["models"]]


def default_models_path() -> Path:
    """Resolve to the repository's data/models.yaml."""
    return Path(__file__).resolve().parents[2] / "data" / "models.yaml"


def default_weights_path() -> Path:
    """Resolve to the repository's data/weights.yaml."""
    return Path(__file__).resolve().parents[2] / "data" / "weights.yaml"


class Weights(BaseModel):
    """Sub-index weights and blended-cost weights, loaded from weights.yaml."""

    composite: dict[str, float]
    blended_cost: dict[str, float]
    base_value: float
    launch_date: date
    fixing_time_utc: str
    methodology_version: str


def load_weights(weights_path: Path | str | None = None) -> Weights:
    """Load methodology weights from data/weights.yaml."""
    path = Path(weights_path) if weights_path else default_weights_path()
    raw = yaml.safe_load(path.read_text())
    return Weights.model_validate(raw)
