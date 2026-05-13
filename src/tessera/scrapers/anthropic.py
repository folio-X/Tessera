"""Anthropic pricing scraper.

Anthropic publishes pricing at https://docs.claude.com/en/docs/about-claude/pricing
as a structured HTML table inside a docs site (Mintlify-based). Cells follow
a consistent "$X / MTok" pattern.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from ..models import ModelPrice
from .base import BaseScraper, utc_now

# api_model_id (matches data/models.yaml) → substring(s) we expect in the row label
TARGET_MODELS = {
    "anthropic-claude-opus-4-7": ["opus 4.7", "claude opus 4.7"],
    "anthropic-claude-haiku-4-5": ["haiku 4.5", "claude haiku 4.5"],
}

_PRICE_RE = re.compile(r"\$\s*(\d+(?:\.\d+)?)")


class AnthropicScraper(BaseScraper):
    provider_name = "anthropic"
    pricing_url = "https://docs.claude.com/en/docs/about-claude/pricing"

    def fetch_raw(self) -> str:
        return self._http_get()

    def parse(self, raw: str) -> list[ModelPrice]:
        soup = BeautifulSoup(raw, "lxml")
        observed = utc_now()
        prices: list[ModelPrice] = []

        for row in soup.find_all("tr"):
            if not isinstance(row, Tag):
                continue
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
            if len(cells) < 3:
                continue
            row_text = " ".join(cells).lower()

            for model_id, needles in TARGET_MODELS.items():
                if any(n in row_text for n in needles):
                    dollars = _PRICE_RE.findall(row_text)
                    if len(dollars) >= 2:
                        prices.append(
                            ModelPrice(
                                model_id=model_id,
                                provider=self.provider_name,
                                input_per_million=float(dollars[0]),
                                output_per_million=float(dollars[1]),
                                source_url=self.pricing_url,
                                observed_at=observed,
                            )
                        )
                    break
        return prices
