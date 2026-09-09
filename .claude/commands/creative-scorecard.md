---
description: Creative-level winners and losers — which specific ads are carrying the account and which are dead weight.
argument-hint: [date range, and optionally a campaign to narrow to]
allowed-tools: mcp__meta-ads__*, mcp__google-ads__*, Bash(python3:*), Read, Glob, Grep
---

# Creative winners and losers

Range: `$ARGUMENTS` — default to the last 30 days. Creative needs a longer
window than campaign reporting; 7 days of ad-level data is mostly noise.

This is the campaign summary's opposite: campaign-level numbers tell you where
money went, ad-level numbers tell you **which sentences are working**. That is
the input the copy agent actually needs.

## Pull

Every ad with enough delivery to judge, with: impressions, clicks, CTR,
conversions, CPA, spend, and how long it has been running. Then the creative
text itself — headline and body — because the point is to find out what the
winners have in common, not merely which IDs they are.

Apply the same significance gate the offline ranker uses, so live and export
analysis agree with each other. It is in `config/thresholds.toml`:

```bash
python3 -m adbrain limits          # character budgets
sed -n '/\[significance\]/,/^$/p' config/thresholds.toml
```

## Report

**Winners** — top performers, with the actual copy, and one line on what they
share. Look for the pattern, not the ranking: is it a shared angle, a shared
opening, a shared offer?

**Losers** — significant ads underperforming the account average, with the copy
and the most likely reason.

**Dead weight** — running a long time, spending, converting nothing. These are
the cheapest wins available.

## Then

Say explicitly whether the winning pattern is already recorded in
`memory/LEARNED.md`. If it is not, that is a finding worth logging:

```bash
python3 -m adbrain learned
```

Offer to turn the losers into a refresh run (`/refresh-ads`), and the winning
pattern into a logged experiment.

**Read-only.** Never pause or edit anything. Recommend; let a human act.
