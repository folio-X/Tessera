"""Together AI pricing scraper.

Together hosts a wide catalog of open-weight models. They publish per-model
pricing at https://together.ai/pricing in a paginated table. Their JS-rendered
data is also available via their public API (`/v1/models`).

For Tessera v1, we restrict to the three OPEN-tier constituents.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from ..models import ModelPrice
from .base import BaseScraper, utc_now

TARGET_MODELS = {
    "meta-llama-3-1-70b-instruct": ["llama 3.1 70b", "llama-3.1-70b"],
    "alibaba-qwen-2-5-72b-instruct": ["qwen 2.5 72b", "qwen-2.5-72b"],
    "deepseek-v3": ["deepseek-v3", "deepseek v3"],
}

_PRICE_RE = re.compile(r"\$\s*(\d+(?:\.\d+)?)")


class TogetherScraper(BaseScraper):
    provider_name = "together"
    pricing_url = "https://together.ai/pricing"

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
                    # Together commonly lists a single blended price for
                    # input+output on chat models; if so we apply it to both.
                    if len(dollars) >= 2:
                        input_p, output_p = dollars[0], dollars[1]
                    else:
                        input_p = output_p = dollars[0]
                    prices.append(
                        ModelPrice(
                            model_id=model_id,
                            provider=self.provider_name,
                            host="together",
                            input_per_million=input_p,
                            output_per_million=output_p,
                            source_url=self.pricing_url,
                            observed_at=observed,
                        )
                    )
                    break
        return prices
