"""Abstract scraper base class.

Each provider scraper inherits from BaseScraper and implements:
  - provider_name      stable string identifier
  - pricing_url        canonical public pricing page
  - fetch_raw()        returns the response body (HTML or JSON) as a string
  - parse(raw)         returns list[ModelPrice]

The base class handles politeness (User-Agent), raw caching for audit,
and error reporting. Scrapers should never invent prices: if parsing fails,
return [] and the daily pipeline will carry forward the previous day's
values with a STALE flag.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from ..models import ModelPrice

USER_AGENT = "Tessera-Index-Scraper/1.0 (https://foliox.ai/tessera; tessera@foliox.ai)"
DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class ScraperError(Exception):
    """Raised when a scraper cannot recover a usable price snapshot."""


# Backwards-compatible alias for older imports.
ScraperFailure = ScraperError


class BaseScraper(ABC):
    """Abstract base class for provider pricing scrapers."""

    #: Short, stable identifier — must match the `provider` field in models.yaml.
    provider_name: str

    #: Canonical public pricing page URL.
    pricing_url: str

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        cache_root: Path | None = None,
    ) -> None:
        self._client = client
        self._owns_client = client is None
        self._cache_root = cache_root

    def __enter__(self) -> BaseScraper:
        if self._client is None:
            self._client = httpx.Client(
                timeout=DEFAULT_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            )
        return self

    def __exit__(self, *exc: object) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            raise RuntimeError("scraper used outside a context manager")
        return self._client

    @abstractmethod
    def fetch_raw(self) -> str:
        """Fetch the provider's public pricing page. Returns raw response body."""

    @abstractmethod
    def parse(self, raw: str) -> list[ModelPrice]:
        """Parse the raw response into ModelPrice records.

        Implementations must:
          - Return only models that were unambiguously parsed.
          - Never invent or estimate a price.
          - Set `observed_at` to the current UTC time.
          - Set `source_url` to the page the price came from.
        """

    def run(self, *, today: date | None = None) -> list[ModelPrice]:
        """Full fetch → cache raw → parse pipeline.

        On parse failure, returns []; the caller is responsible for the
        STALE-fallback policy (see storage.load_yesterday_prices).
        """
        today = today or datetime.now(UTC).date()
        raw = self.fetch_raw()
        self._cache_raw(raw, today)
        return self.parse(raw)

    def _cache_raw(self, raw: str, today: date) -> Path | None:
        """Persist the raw response for audit. Returns the path, or None if no
        cache root was configured."""
        if self._cache_root is None:
            return None
        cache_dir = self._cache_root / today.isoformat()
        cache_dir.mkdir(parents=True, exist_ok=True)
        ext = "json" if raw.lstrip().startswith(("{", "[")) else "html"
        path = cache_dir / f"{self.provider_name}.{ext}"
        path.write_text(raw)
        return path

    def _http_get(self, url: str | None = None) -> str:
        url = url or self.pricing_url
        response = self.client.get(url)
        response.raise_for_status()
        return response.text


def utc_now() -> datetime:
    return datetime.now(UTC)
