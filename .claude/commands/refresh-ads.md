---
description: Run the full ad refresh loop — rank an export, generate replacements through the copy sub-agents, validate, and build the upload.
argument-hint: [path to export CSV] [platform]
allowed-tools: Bash(python3:*), Bash(adbrain:*), Read, Write, Edit, Glob, Grep, Task
---

# Refresh underperforming ads

Arguments: `$ARGUMENTS` — an export path and a platform key. If either is
missing, look in `data/inbox/` for the most recent CSV and infer the platform
from its columns; if that is ambiguous, ask rather than guess.

Work through these steps in order. Do not skip step 2 — generating without the
brief means re-proposing angles that already lost.

## 1. Rank

```bash
python3 -m adbrain rank --input <export> --platform <platform>
```

Report the headline numbers: how many ads, how many flagged, how much spend sits
behind them. Then read the generated `brief.md` in full.

## 2. Read the brief

It carries four things you need: which ads are being replaced and why, what is
currently winning, what prior experiments have already established, and the
exact character budget per field. Everything you generate must respect all four.

Also read `brand/voice.md`, `brand/icp.md`, and `brand/proof.md`. If they are
still unfilled templates, say so plainly before generating — the output will be
generic and the user should know that going in.

## 3. Generate — two sub-agents, always

For each flagged ad, dispatch **both** in parallel:

- `headline-writer` for headline fields
- `description-writer` for descriptions, primary text, and body copy

Never merge these into one prompt. They fail differently and are debugged
differently, which is the entire reason they are separate.

Collect their JSON into `<run>/candidates.json`:

```json
{
  "generated": [
    {
      "ad_id": "rsa-2118",
      "campaign": "search - brand",
      "ad_group": "brand exact",
      "final_url": "https://example.com/product",
      "angle": "...",
      "hypothesis": "...",
      "fields": {
        "headline": ["...", "..."],
        "description": ["...", "..."],
        "path1": ["..."],
        "path2": ["..."]
      }
    }
  ]
}
```

Carry `campaign`, `ad_group` and `final_url` across from the brief's target
entry — the bulk upload needs them and cannot invent them.

## 4. Validate

```bash
python3 -m adbrain validate --run latest
```

If anything is rejected, read `<run>/regenerate.md`, send the failures back to
the sub-agent that wrote them, and rerun. **Rewrite, never trim.** Repeat until
it passes. Do not edit a line yourself to squeeze it under the limit — that is
how copy ends up fitting the box and saying nothing.

## 5. Build

```bash
python3 -m adbrain build --run latest
```

## 6. Report back

Show the user:

- how many ads were flagged and why, in their language, not in metrics jargon
- the replacements, grouped by ad, with character counts
- anything the validator warned about but let through
- where the upload CSV is, and that **it imports paused**

Then remind them of the two follow-ups that make the next run better: run
`adbrain log --run latest` now, and `adbrain outcome` once performance data
lands in a week or two.
