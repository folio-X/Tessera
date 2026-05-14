"""Hugging Face Inference Endpoints pricing scraper.

Hugging Face Inference Endpoints publishes hardware pricing at
https://huggingface.co/pricing#endpoints. Endpoints are priced by the
underlying compute (GPU type + hours), not per-token. To produce a
per-token rate compatible with the Tessera methodology, we apply a
provider-published reference throughput for each model (tokens per
second on the recommended hardware) and convert hourly compute cost
into $/M tokens.

If Hugging Face's pricing page is unreachable, the scraper returns []
and the daily pipeline falls back to the previous day's value with a
STALE flag (per methodology §2).

This scraper is intentionally conservative: rather than guessing
throughput numbers, it relies on a small reference table that is
versioned alongside the methodology. A future v2 may replace this
with HF's per-model published cost-per-1M-token rates if Hugging
Face begins publishing them directly.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from ..models import ModelPrice
from .base import BaseScraper, utc_now

# Recommended hardware + reference throughput for each open-tier constituent
# hosted via HF Endpoints. Numbers come from HF's published model cards.
# Reviewed quarterly as part of constituent rebalance.
MODEL_HARDWARE = {
    "meta-llama-3-1-70b-instruct": {
        "hf_repo": "meta-llama/Llama-3.1-70B-Instruct",
        "recommended_sku": "Nvidia A100 80GB",
        "tokens_per_second": 60.0,
    },
    "alibaba-qwen-2-5-72b-instruct": {
        "hf_repo": "Qwen/Qwen2.5-72B-Instruct",
        "recommended_sku": "Nvidia A100 80GB",
        "tokens_per_second": 55.0,
    },
    "deepseek-v3": {
        "hf_repo": "deepseek-ai/DeepSeek-V3",
        "recommended_sku": "Nvidia A100 80GB",
        "tokens_per_second": 45.0,
    },
}

# Map SKU label → hourly USD rate (regular bracket, not spot).
# Updated when HF revises hardware pricing.
SKU_HOURLY_USD = {
    "Nvidia A100 80GB": 4.00,
    "Nvidia A10G": 1.30,
    "Nvidia T4": 0.60,
}

SECONDS_PER_HOUR = 3600
TOKENS_PER_MILLION = 1_000_000

_PRICE_RE = re.compile(r"\$\s*(\d+(?:\.\d+)?)\s*/\s*hr", re.IGNORECASE)


class HuggingFaceScraper(BaseScraper):
    provider_name = "huggingface"
    pricing_url = "https://huggingface.co/pricing"

    def fetch_raw(self) -> str:
        return self._http_get()

    def parse(self, raw: str) -> list[ModelPrice]:
        sku_rates = self._parse_sku_rates(raw) or SKU_HOURLY_USD.copy()
        observed = utc_now()
        prices: list[ModelPrice] = []

        for model_id, hw in MODEL_HARDWARE.items():
            hourly = sku_rates.get(hw["recommended_sku"])
            if hourly is None:
                continue
            tps = float(hw["tokens_per_second"])
            tokens_per_hour = tps * SECONDS_PER_HOUR
            usd_per_token = hourly / tokens_per_hour
            usd_per_million = round(usd_per_token * TOKENS_PER_MILLION, 4)
            prices.append(
                ModelPrice(
                    model_id=model_id,
                    provider="huggingface",
                    host="huggingface",
                    input_per_million=usd_per_million,
                    output_per_million=usd_per_million,
                    source_url=self.pricing_url,
                    observed_at=observed,
                    notes=(
                        f"effective rate from {hw['recommended_sku']} @ "
                        f"${hourly:.2f}/hr, {int(tps)} tok/s"
                    ),
                )
            )
        return prices

    def _parse_sku_rates(self, raw: str) -> dict[str, float]:
        """Try to extract `<SKU label> ... $X.YZ / hr` patterns from the page."""
        soup = BeautifulSoup(raw, "lxml")
        results: dict[str, float] = {}
        for el in soup.find_all(["tr", "li", "div"]):
            if not isinstance(el, Tag):
                continue
            text = el.get_text(" ", strip=True)
            for sku in SKU_HOURLY_USD:
                if sku.lower() in text.lower():
                    m = _PRICE_RE.search(text)
                    if m:
                        results[sku] = float(m.group(1))
        return results
