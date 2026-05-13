"""Fireworks AI pricing scraper.

Fireworks publishes pricing at https://fireworks.ai/pricing. Their model
table groups by size bucket; smaller per-million prices for larger volume
tiers are *not* used (Tessera takes standard tier only).
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from ..models import ModelPrice
from .base import BaseScraper, utc_now

TARGET_MODELS = {
    "meta-llama-3-1-70b-instruct": ["llama 3.1 70b", "llama-v3p1-70b"],
    "alibaba-qwen-2-5-72b-instruct": ["qwen 2.5 72b", "qwen2p5-72b"],
    "deepseek-v3": ["deepseek-v3", "deepseek v3"],
}

_PRICE_RE = re.compile(r"\$\s*(\d+(?:\.\d+)?)")


class FireworksScraper(BaseScraper):
    provider_name = "fireworks"
    pricing_url = "https://fireworks.ai/pricing"

    def fetch_raw(self) -> str:
        return self._http_get()

    def parse(self, raw: str) -> list[ModelPrice]:
        soup = BeautifulSoup(raw, "lxml")
        observed = utc_now()
        prices: list[ModelPrice] = []

        for row in soup.find_all("tr"):
            if not isinstance(row, Tag):
                continue
            row_text = row.get_text(" ", strip=True).lower()
            for model_id, needles in TARGET_MODELS.items():
                if any(n in row_text for n in needles):
                    dollars = [float(m) for m in _PRICE_RE.findall(row_text)]
                    if not dollars:
                        continue
                    input_p = dollars[0]
                    output_p = dollars[1] if len(dollars) > 1 else dollars[0]
                    prices.append(
                        ModelPrice(
                            model_id=model_id,
                            provider=self.provider_name,
                            host="fireworks",
                            input_per_million=input_p,
                            output_per_million=output_p,
                            source_url=self.pricing_url,
                            observed_at=observed,
                        )
                    )
                    break
        return prices
