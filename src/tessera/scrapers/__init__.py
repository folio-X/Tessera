"""Per-provider scrapers that fetch + parse public list pricing.

Each scraper inherits from BaseScraper. The registry below maps provider
identifiers (as used in data/models.yaml) to the concrete scraper class.
"""

from __future__ import annotations

from .anthropic import AnthropicScraper
from .base import BaseScraper, ScraperFailure
from .deepinfra import DeepInfraScraper
from .fireworks import FireworksScraper
from .google import GoogleScraper
from .groq import GroqScraper
from .openai import OpenAIScraper
from .replicate import ReplicateScraper
from .together import TogetherScraper

ALL_SCRAPERS: dict[str, type[BaseScraper]] = {
    "openai": OpenAIScraper,
    "anthropic": AnthropicScraper,
    "google": GoogleScraper,
    "together": TogetherScraper,
    "fireworks": FireworksScraper,
    "groq": GroqScraper,
    "deepinfra": DeepInfraScraper,
    "replicate": ReplicateScraper,
}

__all__ = ["ALL_SCRAPERS", "BaseScraper", "ScraperFailure"]
