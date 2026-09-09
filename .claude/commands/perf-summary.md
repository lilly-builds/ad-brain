---
description: Performance summary by campaign for a date range, with what changed since the previous period.
argument-hint: [date range, e.g. "last 7 days" or "september so far"]
allowed-tools: mcp__meta-ads__*, mcp__google-ads__*, Bash(python3:*), Read, Glob, Grep
---

# Performance summary by campaign

Range: `$ARGUMENTS` — default to the last 7 days if not given.

Pull for every active campaign: spend, impressions, clicks, CTR, conversions,
CPA. Then pull **the same metrics for the preceding period of equal length**,
because a number without a comparison is not information.

Query whichever platform is connected. If both are, report them separately —
a blended CTR across search and social is a meaningless average.

## Present it like this

A table, sorted by spend descending, with the change against the prior period:

| campaign | spend | Δ | ctr | Δ | conv | Δ | cpa | Δ |
|---|---|---|---|---|---|---|---|---|

Then **three sentences at most** on what actually matters:

- what moved enough to care about, and the most likely reason
- anything that looks like a delivery problem rather than a performance problem
  (spend collapsed, impressions collapsed, frequency spiked)
- the single thing worth doing about it this week

## Rules

- Never present a percentage change on a base too small to mean anything. Under
  ~100 clicks or ~500 impressions, give the raw numbers and say the sample is thin.
- Do not recommend pausing anything without checking `memory/LEARNED.md` first —
  a campaign may be running a test that is deliberately unprofitable while it
  gathers data.
- **Read-only.** Never call a tool that changes a campaign, budget, or status.
  If the right answer is "pause this", say so and let a human do it.
