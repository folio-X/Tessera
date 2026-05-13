"""OpenAI pricing scraper.

OpenAI publishes pricing at https://openai.com/api/pricing in a structured
HTML table. The page is React-rendered, but the underlying Next.js data is
serialized into a `<script id="__NEXT_DATA__">` tag, which is the most
robust extraction surface. If that pattern breaks, we fall back to a
heuristic table parse.
"""

from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..models import ModelPrice
from .base import BaseScraper, utc_now

# Models we care about. Mapping: needle (matched against the first table-cell
# text, case-insensitive, after a startswith() check) → Tessera model_id.
# Keys are ordered longest-first when iterated so that "gpt-5 mini" wins over
# the prefix-match "gpt-5".
TARGET_MODELS = {
    "gpt-5 mini": "openai-gpt-5-mini",
    "gpt-5-mini": "openai-gpt-5-mini",
    "gpt-5": "openai-gpt-5",
}


class OpenAIScraper(BaseScraper):
    provider_name = "openai"
    pricing_url = "https://openai.com/api/pricing"

    def fetch_raw(self) -> str:
        return self._http_get()

    def parse(self, raw: str) -> list[ModelPrice]:
        prices = self._parse_next_data(raw)
        if prices:
            return prices
        return self._parse_html_table(raw)

    def _parse_next_data(self, raw: str) -> list[ModelPrice]:
        """Extract pricing from the __NEXT_DATA__ script tag."""
        match = re.search(
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            raw,
            re.DOTALL,
        )
        if not match:
            return []
        try:
            payload: Any = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []

        observed = utc_now()
        prices: list[ModelPrice] = []
        for record in _walk_pricing(payload):
            api_id = record.get("model_id") or record.get("id")
            if api_id not in TARGET_MODELS:
                continue
            try:
                input_p = float(record["input_per_million"])
                output_p = float(record["output_per_million"])
            except (KeyError, TypeError, ValueError):
                continue
            prices.append(
                ModelPrice(
                    model_id=TARGET_MODELS[api_id],
                    provider=self.provider_name,
                    input_per_million=input_p,
                    output_per_million=output_p,
                    source_url=self.pricing_url,
                    observed_at=observed,
                )
            )
        return prices

    def _parse_html_table(self, raw: str) -> list[ModelPrice]:
        """Heuristic fallback: look for table rows naming our target models.

        Matches against the first cell only, longest-target-first, so that
        "gpt-5 mini" wins over the prefix-match "gpt-5".
        """
        soup = BeautifulSoup(raw, "lxml")
        observed = utc_now()
        prices: list[ModelPrice] = []
        targets_by_length = sorted(TARGET_MODELS.items(), key=lambda kv: -len(kv[0]))

        for row in soup.find_all("tr"):
            if not isinstance(row, Tag):
                continue
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
            if len(cells) < 3:
                continue
            first_cell = cells[0].lower().strip()
            row_text = " ".join(cells)

            for api_id, model_id in targets_by_length:
                if first_cell.startswith(api_id):
                    dollar_values = _extract_dollar_values(row_text)
                    if len(dollar_values) >= 2:
                        prices.append(
                            ModelPrice(
                                model_id=model_id,
                                provider=self.provider_name,
                                input_per_million=dollar_values[0],
                                output_per_million=dollar_values[1],
                                source_url=self.pricing_url,
                                observed_at=observed,
                            )
                        )
                    break
        return prices


def _walk_pricing(node: Any) -> list[dict[str, Any]]:
    """Walk arbitrary nested JSON looking for objects that carry pricing fields."""
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if any(k in node for k in ("input_per_million", "input_per_1m", "input_price")):
            normalized = dict(node)
            if "input_per_1m" in normalized:
                normalized["input_per_million"] = normalized["input_per_1m"]
            if "output_per_1m" in normalized:
                normalized["output_per_million"] = normalized["output_per_1m"]
            if "input_price" in normalized:
                normalized["input_per_million"] = normalized["input_price"]
            if "output_price" in normalized:
                normalized["output_per_million"] = normalized["output_price"]
            found.append(normalized)
        for v in node.values():
            found.extend(_walk_pricing(v))
    elif isinstance(node, list):
        for v in node:
            found.extend(_walk_pricing(v))
    return found


_DOLLAR_RE = re.compile(r"\$\s*(\d+(?:\.\d+)?)")


def _extract_dollar_values(text: str) -> list[float]:
    return [float(m) for m in _DOLLAR_RE.findall(text)]
