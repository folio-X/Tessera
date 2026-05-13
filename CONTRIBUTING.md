# Contributing to Tessera

Thanks for your interest in contributing. Tessera is a public good, and the credibility of the index depends on it being transparent, well-tested, and conservative about change.

## What we welcome

- **Scraper bug reports and fixes.** Providers change their pricing pages without notice; if you spot a broken scraper, open an issue or PR.
- **Methodology proposals.** Open an issue labeled `methodology-proposal`. See [GOVERNANCE.md](./GOVERNANCE.md) for the 30-day public-comment process.
- **Constituent proposals.** New models, new hosts for existing open-weight models, or proposed removals. Issue label: `constituent-proposal`.
- **Documentation improvements.** Especially around methodology clarity.
- **Tests.** More edge cases for the index calculation are always welcome.

## What we don't accept

- **Hard-coded prices.** All prices must come from a scraper sourced from a public pricing page.
- **Interpolation, smoothing, or estimation.** If a scraper fails, we carry forward yesterday's value with a `STALE` flag. We do not invent data.
- **Provider-specific carve-outs that aren't documented in METHODOLOGY.md.** If a price needs special treatment, that has to be in the methodology, not buried in scraper code.
- **Quality adjustments.** Deferred to v2. Do not add benchmark scores to model records yet.

## Development setup

```bash
git clone https://github.com/folio-X/tessera
cd tessera
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
pytest
```

## Code style

- Python 3.11+
- `ruff` for linting and formatting (configured in `pyproject.toml`)
- `mypy --strict` for type checking
- All public functions need type hints and a one-line docstring

Run `ruff check . && ruff format . && mypy src/ && pytest` before opening a PR.

## Scraper contracts

Every scraper inherits from `tessera.scrapers.base.BaseScraper` and implements:

- `provider_name` — short, stable identifier (matches `data/models.yaml`)
- `pricing_url` — canonical public pricing page
- `fetch_raw()` — returns the response body as a string. Should respect the politeness contract: max one request per day per provider.
- `parse(raw)` — returns `list[ModelPrice]`. Must not raise on missing models; return only what was found.
- `validate(prices)` — applies sanity checks. Any price change >50% day-over-day flags for manual review.

Each scraper must also save the raw response to `data/snapshots/raw/YYYY-MM-DD/{provider}.{html,json}` for audit.

## Reporting a methodology bug

If you find what looks like a calculation error or methodology inconsistency, please **do not open a public PR with a corrected number**. Instead:

1. Open an issue labeled `methodology-bug`.
2. Include the date, the index, the published value, and what you believe the correct value is.
3. Show your calculation.

We will investigate and, if confirmed, publish a `CORRECTION` notice in CHANGELOG.md. See the corrections policy in [GOVERNANCE.md](./GOVERNANCE.md).

## License of contributions

By submitting a contribution, you agree that:

- Contributions to code (`src/`, `tests/`, `.github/`) are licensed under Apache 2.0.
- Contributions to data, methodology, or documentation (`data/`, `docs/`, `reports/`, methodology files) are licensed under CC-BY-NC 4.0.

For substantial contributions, FolioX may ask for a Contributor License Agreement to clarify commercial-licensing rights downstream. We will explain the reasoning when we do.
