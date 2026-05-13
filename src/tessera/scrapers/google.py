"""Google Gemini pricing scraper.

Google publishes Gemini API pricing at https://ai.google.dev/pricing.
The page is structured with model-named sections; we look for known model
names and pull the input/output rates beneath them.

Gemini Pro historically uses tiered pricing (≤200K tokens vs. >200K).
Tessera methodology uses the standard (lowest-tier) public list price.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from ..models import ModelPrice
from .base import BaseScraper, utc_now

TARGET_MODELS = {
    "google-gemini-2-5-pro": ["gemini 2.5 pro"],
    "google-gemini-2-5-flash": ["gemini 2.5 flash"],
}

_PRICE_RE = re.compile(r"\$\s*(\d+(?:\.\d+)?)")


class GoogleScraper(BaseScraper):
    provider_name = "google"
    pricing_url = "https://ai.google.dev/pricing"

    def fetch_raw(self) -> str:
        return self._http_get()

    def parse(self, raw: str) -> list[ModelPrice]:
        soup = BeautifulSoup(raw, "lxml")
        observed = utc_now()
        prices: list[ModelPrice] = []

        for model_id, needles in TARGET_MODELS.items():
            section = self._find_model_section(soup, needles)
            if not section:
                continue
            text = section.get_text(" ", strip=True).lower()
            input_p, output_p = self._extract_input_output(text)
            if input_p is None or output_p is None:
                continue
            prices.append(
                ModelPrice(
                    model_id=model_id,
                    provider=self.provider_name,
                    input_per_million=input_p,
                    output_per_million=output_p,
                    source_url=self.pricing_url,
                    observed_at=observed,
                )
            )
        return prices

    def _find_model_section(self, soup: BeautifulSoup, needles: list[str]) -> Tag | None:
        """Return the smallest enclosing block whose text mentions the model name."""
        for header in soup.find_all(["h2", "h3", "h4"]):
            if not isinstance(header, Tag):
                continue
            label = header.get_text(" ", strip=True).lower()
            if any(n in label for n in needles):
                container = header.find_parent("section") or header.parent
                if isinstance(container, Tag):
                    return container
        return None

    def _extract_input_output(self, text: str) -> tuple[float | None, float | None]:
        """Look for explicit `input ... $X` and `output ... $Y` patterns in text."""
        input_p = self._extract_labeled_price(text, "input")
        output_p = self._extract_labeled_price(text, "output")
        return input_p, output_p

    @staticmethod
    def _extract_labeled_price(text: str, label: str) -> float | None:
        # First $ amount after the label.
        idx = text.find(label)
        if idx < 0:
            return None
        match = _PRICE_RE.search(text[idx:])
        return float(match.group(1)) if match else None
