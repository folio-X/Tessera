# Tessera Governance

This document describes how decisions about Tessera are made. The published methodology lives in [METHODOLOGY.md](./METHODOLOGY.md); this document covers the *process* by which methodology and constituents can change.

## Decision authority

For v1, methodology and constituent decisions are made by FolioX Inc. as the index publisher. A formal methodology committee with external members will be constituted after the index has been in continuous operation for six months.

## Methodology change process

1. **Proposal** — opened as a GitHub issue on this repository with the `methodology-proposal` label. The proposal must describe (a) the specific change, (b) the motivation, (c) any expected impact on published index values.
2. **Public comment** — 30 days, during which the proposal remains open for community discussion.
3. **Decision** — FolioX reviews comments and either accepts, modifies, or rejects the proposal, with rationale published in the issue.
4. **Version increment** — accepted proposals are merged with an explicit methodology version bump (semver: major for breaking, minor for material changes, patch for clarifications).
5. **Effective date** — the new methodology version takes effect *after* publication. Past index values are not restated when methodology changes.

## Constituent change process

Adding or removing a model from a sub-index follows the same process but with a 14-day notice period instead of 30 days, since these changes are operationally driven (provider availability, deprecations).

**Forced deprecations** — when a provider deprecates a model, it is removed on the provider's effective deprecation date without the 14-day notice. The CHANGELOG records the forced removal.

## Quarterly rebalance

A scheduled quarterly review on the first business day of February, May, August, and November confirms that:

- All listed constituents still meet inclusion criteria
- No new models have been generally available for 30+ days and warrant inclusion
- The 30/70 input/output split and the 40/30/30 TCI weights still reflect typical workload mix

If the review concludes that weights need adjustment, that proposal enters the normal 30-day methodology change process.

## Corrections

Published index values are **not silently restated**. If an error is discovered:

1. A `CORRECTION` entry is added to CHANGELOG.md describing the error, the affected dates, and the corrected values.
2. The corrected value is applied forward from the next fixing date.
3. The historical record retains the originally published value, annotated with a reference to the correction.

This rule protects users who have already cited or relied on a published value.

## Conflicts of interest

FolioX Inc. uses AI inference services from several index constituents in our own products. We disclose this in the LICENSE page on the public website. Inclusion criteria are documented in METHODOLOGY.md and are applied without regard to whether FolioX is a customer of the provider.

## Contacting governance

- **Methodology questions** — open a GitHub issue with the `methodology-question` label.
- **Constituent proposals** — open a GitHub issue with the `constituent-proposal` label.
- **Commercial licensing inquiries** — tessera@foliox.ai.
- **Press and research inquiries** — tessera@foliox.ai.
