---
description: Spend pacing — are we on track against budget, and where is money going that shouldn't be.
argument-hint: [monthly budget, if not already recorded]
allowed-tools: mcp__meta-ads__*, mcp__google-ads__*, Bash(python3:*), Read, Glob, Grep
---

# Spend pacing

Budget: `$ARGUMENTS` — if not given, ask once. Pacing without a target is just
a spend report.

## Work out

1. **Where we are.** Month-to-date spend, days elapsed, days remaining.
2. **Where we should be.** Straight-line pace for today.
3. **The gap**, as an amount and a percentage — over, under, or on track.
4. **Projected end-of-month** at the current daily rate.
5. **Where the drift comes from.** Which campaigns are ahead of or behind their
   share. A total that looks on-pace often hides one campaign overspending and
   another starved.

## Report

Lead with one sentence: on track, over by X, or under by X, and the projection.

Then the campaign breakdown, sorted by how far off pace each is. Then:

- **Money going somewhere it shouldn't** — campaigns spending with no
  conversions, ads with a CPA far above target, anything ramping without a
  matching result.
- **Money not going somewhere it should** — budget-limited campaigns that are
  converting well. Underspending a winner is a real cost and it does not show up
  as a problem anywhere else.

## Rules

- Under-pacing on a converting campaign is a bigger problem than over-pacing on
  one, and should be reported that way.
- Do not extrapolate from fewer than 5 days. Say the projection is unreliable.
- **Read-only.** Never change a budget. Recommend the change and let a human
  make it — a budget edit through a chat message with no undo is exactly the
  thing this repo declines to do.
