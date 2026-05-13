"""Replicate pricing scraper.

Replicate's pricing model is a mix of per-second compute pricing and
per-token pricing. For Tessera, only LLMs with per-token pricing are
included. Replicate primarily lists Llama variants under the Tessera
OPEN tier.

The pricing page at https://replicate.com/pricing surfaces per-model
breakdowns; the per-model detail pages at https://replicate.com/<owner>/<model>
also publish the input/output rate. We pull from the main pricing page
when possible to minimize requests.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from ..models import ModelPrice
from .base import BaseScraper, utc_now

TARGET_MODELS = {
    "meta-llama-3-1-70b-instruct": ["llama-3.1-70b-instruct", "llama 3.1 70b"],
}

_PRICE_RE = re.compile(r"\$\s*(\d+(?:\.\d+)?)")


class ReplicateScraper(BaseScraper):
    provider_name = "replicate"
    pricing_url = "https://replicate.com/pricing"

    def fetch_raw(self) -> str:
        return self._http_get()

    def parse(self, raw: str) -> list[ModelPrice]:
        soup = BeautifulSoup(raw, "lxml")
        observed = utc_now()
        prices: list[ModelPrice] = []

        candidates = soup.find_all(["tr", "li", "div"])
        for el in candidates:
            if not isinstance(el, Tag):
                continue
            text = el.get_text(" ", strip=True).lower()
            for model_id, needles in TARGET_MODELS.items():
                if any(n in text for n in needles):
                    dollars = [float(m) for m in _PRICE_RE.findall(text)]
                    if not dollars:
                        continue
                    input_p = dollars[0]
                    output_p = dollars[1] if len(dollars) > 1 else dollars[0]
                    prices.append(
                        ModelPrice(
                            model_id=model_id,
                            provider=self.provider_name,
                            host="replicate",
                            input_per_million=input_p,
                            output_per_million=output_p,
                            source_url=self.pricing_url,
                            observed_at=observed,
                        )
                    )
                    break
        return prices
