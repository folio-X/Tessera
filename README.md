# Tessera

**An open-source, transparent index of AI inference costs across major language model providers.**

Tessera is published by [FolioX Inc.](https://foliox.ai) as a public good. We build AI agents whose unit economics are dominated by inference cost; we needed to understand, monitor, and eventually hedge that cost. So we built an index — the way fuel companies have always referenced WTI, Brent, and OPIS for their underlying commodity. We're publishing it openly because every AI-native company has the same problem we did.

Live data and methodology: **[foliox.ai/tessera](https://foliox.ai/tessera)**

---

## What Tessera publishes

| Index | Code | Composition |
|---|---|---|
| Tessera Composite Index | `TCI` | 40% Frontier Closed, 30% Mid-Tier Closed, 30% Open |
| Tessera Frontier Closed Index | `TFC` | Equal-weighted basket of flagship closed models |
| Tessera Mid-Tier Closed Index | `TMC` | Equal-weighted basket of mid-tier closed models |
| Tessera Open Index | `TOI` | Volume-hosted-weighted basket of open-weight models |
| Tessera Closed-Open Spread | `TCOS` | Frontier Closed minus Open (the frontier premium) |

All indexes are normalized to a base of `1000.00` on the launch date and updated daily at 16:00 UTC.

See [METHODOLOGY.md](./METHODOLOGY.md) for full computation rules, constituent selection, and governance.

---

## Repository layout

```
tessera/
├── METHODOLOGY.md              full computation methodology
├── GOVERNANCE.md               how methodology changes get made
├── CHANGELOG.md                versioned methodology + constituent changes
├── LICENSE-CODE                Apache 2.0 (covers src/, tests/, .github/)
├── LICENSE-DATA                CC-BY-NC 4.0 (covers data/, docs/, reports/)
├── COMMERCIAL-LICENSE.md       terms for commercial use of index data
├── src/tessera/                Python pipeline
│   ├── scrapers/               one module per provider
│   ├── models.py               canonical model registry loader
│   ├── normalize.py            unit conversion (per-million tokens, USD)
│   ├── index.py                index computation (TCI, TFC, TMC, TOI, TCOS)
│   ├── storage.py              snapshot + daily CSV persistence
│   └── validators.py           outlier detection, STALE flag handling
├── data/
│   ├── models.yaml             canonical constituents
│   ├── weights.yaml            sub-index weights
│   ├── snapshots/YYYY-MM-DD.json   daily raw price snapshots
│   ├── snapshots/raw/          cached HTML/JSON responses (audit trail)
│   └── index/tessera-daily.csv     computed daily index values
├── tests/                      pytest suite
├── docs/                       rendered methodology pages
└── reports/                    monthly research reports
```

## Using the data

**Read it directly from this repo.** The canonical files are:

- `data/index/tessera-daily.csv` — one row per fixing day, all sub-indexes
- `data/snapshots/YYYY-MM-DD.json` — raw per-model prices behind each day's values
- `data/models.yaml` — current constituents

Or fetch the most recent published value from the public API:

```
GET https://foliox.ai/api/tessera/current
```

```json
{
  "as_of": "2026-05-04T16:00:00Z",
  "tci": 1000.00,
  "tfc": 1000.00,
  "tmc": 1000.00,
  "toi": 1000.00,
  "tcos": 0.00,
  "methodology_version": "1.0.0"
}
```

## Running the pipeline locally

```bash
pip install -e .
python -m tessera.cli compute --date 2026-05-04
python -m tessera.cli scrape --provider openai
pytest
```

## Licensing

Tessera is dual-licensed:

- **Code** (everything in `src/`, `tests/`, `.github/`): [Apache 2.0](./LICENSE-CODE)
- **Data, methodology, reports** (everything in `data/`, `docs/`, `reports/`, plus `METHODOLOGY.md`): [CC-BY-NC 4.0](./LICENSE-DATA)

**Commercial use** of the data — including use in derivatives, ETFs, structured products, fintech platforms, internal enterprise data subscriptions at companies with revenue above $10M, or any redistribution as part of a paid product — requires a separate commercial license. See [COMMERCIAL-LICENSE.md](./COMMERCIAL-LICENSE.md) or email tessera@foliox.ai.

## Contributing

Methodology questions, scraper bugs, and constituent proposals are welcome. See [CONTRIBUTING.md](./CONTRIBUTING.md).

## Governance

Methodology changes require a published proposal, a 30-day public comment period, and an explicit version increment. Constituent changes require 14-day notice except for forced deprecations. See [GOVERNANCE.md](./GOVERNANCE.md).

## Citing Tessera

```
Tessera Index, FolioX Inc. (2026-). https://foliox.ai/tessera
```

---

*Tessera is published for informational purposes only. It is not a financial product, financial instrument, or investment advice. See the [legal notice](https://foliox.ai/tessera/legal) for the full disclaimer.*
