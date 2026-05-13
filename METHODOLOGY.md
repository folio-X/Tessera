# Tessera Methodology

**Version:** 1.0.0
**Effective:** 2026-05-04
**Publisher:** FolioX Inc.

This document specifies how Tessera index values are computed. It is the authoritative reference. The frozen text of each methodology version is preserved in `data/methodology-versions/` for audit.

---

## 1. Indexes

Tessera publishes five indexes. All are normalized to a base value of `1000.00` on the launch date (2026-05-04) and updated once per day at the fixing time (16:00 UTC).

### 1.1 Tessera Composite Index (TCI)

A weighted average of the three sub-indexes, expressed as an index level.

```
TCI = 0.40 · TFC + 0.30 · TMC + 0.30 · TOI
```

The weights reflect the published view that frontier capability dominates the dollar-value of AI workloads today, that mid-tier closed models carry a meaningful but smaller share of compute spend, and that open-weight models — while a much smaller dollar share — are the most important reference point for cost-floor dynamics.

### 1.2 Tessera Frontier Closed Index (TFC)

An equal-weighted basket of flagship closed-source models. The current constituents are listed in `data/models.yaml` under the `frontier_closed` tier.

Each model contributes a *blended cost per million tokens*:

```
blended_cost = 0.70 · input_price + 0.30 · output_price
```

The 70/30 input/output split reflects the typical workload mix observed in production agent traffic (cold-context-heavy generation flows). The TFC value on day *t* is:

```
TFC(t) = (TFC_base / mean_blended_cost(t_0)) · mean_blended_cost(t)
       = scale_factor · mean_blended_cost(t)
```

where `scale_factor` is fixed at index launch so that `TFC(t_0) = 1000.00`.

### 1.3 Tessera Mid-Tier Closed Index (TMC)

Identical methodology to TFC, applied to the basket of mid-tier closed models (e.g., GPT-mini class, Claude Haiku class, Gemini Flash class). Each model again contributes a 70/30 blended cost.

### 1.4 Tessera Open Index (TOI)

A basket of open-weight models. For each constituent, the per-model price is the **median across all hosting providers** in the index (currently Together AI, Fireworks AI, Groq, DeepInfra, Replicate). Models are equal-weighted within the basket.

Using the median across hosts insulates the index from a single host's promotional pricing or outage.

### 1.5 Tessera Closed-Open Spread (TCOS)

A measure of the frontier premium, reported both in absolute and percentage terms.

```
TCOS_absolute = TFC - TOI
TCOS_percent  = (TFC - TOI) / TOI · 100
```

---

## 2. Price sourcing

- **Public list prices only.** No negotiated enterprise pricing, no committed-use discounts, no private preview rates.
- **Standard tier only.** No batch discounts, no cached-input pricing, no fine-tuned-model surcharges, no priority lanes.
- **USD-denominated.** Prices listed in other currencies are converted using the day's WM/Reuters 16:00 UTC fix.
- **Per million tokens.** All prices are normalized to USD per million tokens. Where a provider lists per-1K tokens or per-call, we convert.
- **Daily snapshot at 16:00 UTC.** A single fixing time avoids intraday confusion. Prices observed outside this window are not used to compute that day's index level.
- **Source URL recorded** for every price, every day, in the daily snapshot file under `data/snapshots/YYYY-MM-DD.json`.

If a scraper fails to retrieve a current price, the previous day's price is carried forward with a `STALE` flag. We **do not interpolate, estimate, or invent prices**. If a value is stale, that fact is visible in the daily snapshot.

---

## 3. Model inclusion and deprecation

### 3.1 Inclusion

A model is added to the relevant sub-index when **all** of the following are true:

1. It is generally available (not waitlist or limited preview).
2. The provider publishes a public price.
3. It has been generally available for at least 30 days. This avoids index churn on launch-day pricing and gives the market time to settle.
4. It meets the tier classification criteria below.

### 3.2 Tier classification

- **Frontier Closed** — flagship closed-source models from a major lab. Currently: OpenAI GPT-5, Anthropic Claude Opus 4.7, Google Gemini 2.5 Pro.
- **Mid-Tier Closed** — non-flagship closed models from the same labs. Currently: OpenAI GPT-5 mini, Anthropic Claude Haiku 4.5, Google Gemini 2.5 Flash.
- **Open** — open-weight models hosted by multiple commercial providers. Currently: Llama 3.1 70B, Qwen 2.5 72B, DeepSeek V3.

Quality-adjusted classification is **deferred to methodology v2** (target: 6 months post-launch). v1 uses raw cost-per-token.

### 3.3 Deprecation

A model is removed from the index when:

1. The provider deprecates it. The effective date is the **provider's deprecation date**, not the announcement date.
2. It no longer meets tier classification criteria (e.g., reclassified by the provider).
3. Quarterly rebalance (next: 2026-08-01).

Forced deprecations bypass the quarterly cadence.

---

## 4. Governance

### 4.1 Methodology changes

Any change to the calculation rules in this document requires:

1. A published proposal, opened as an issue on the public repository.
2. A 30-day public comment period.
3. An explicit version increment (v1.0.0 → v1.1.0 for material changes; v1.0.0 → v1.0.1 for typo / clarification only).
4. Publication of the new version *before* it takes effect. Past index values are not restated when methodology changes.

### 4.2 Constituent changes

Adding or removing a model from the index requires 14 days' published notice, except for forced deprecations (provider end-of-life), which take effect on the provider's deprecation date.

### 4.3 Corrections

Published index values are **not silently restated**. If we discover an error, we publish a CORRECTION notice in `CHANGELOG.md` and apply the corrected value forward. The historical record retains the originally published value with a correction reference.

### 4.4 Methodology committee

For v1, methodology decisions are made by FolioX Inc. A formal methodology committee with external advisors will be constituted after the index has been in continuous operation for six months.

---

## 5. Quality adjustment (deferred to v2)

For v1, Tessera publishes raw cost-per-token. For v2 (target: six months post-launch), Tessera will publish quality-adjusted indexes using a methodology to be specified — likely incorporating standardized benchmarks (MMLU, GPQA, HumanEval, or successor benchmarks). Until v2 is published, the v1 raw-cost methodology is canonical.

---

## 6. Glossary

- **TCI** — Tessera Composite Index
- **TFC** — Tessera Frontier Closed Index
- **TMC** — Tessera Mid-Tier Closed Index
- **TOI** — Tessera Open Index
- **TCOS** — Tessera Closed-Open Spread
- **Constituent** — a model included in an index
- **Fixing time** — the daily moment (16:00 UTC) at which index values are computed and published
- **STALE flag** — indicator that a value was carried forward from a previous day due to a scraper failure
- **Blended cost** — 0.70 × input_price + 0.30 × output_price, in USD per million tokens

---

*Tessera is published for informational purposes only. It is not a financial product, financial instrument, or investment advice. No investment, hedging, or trading decisions should be made based solely on Tessera values.*
