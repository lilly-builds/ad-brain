---
description: Fan approved ad copy out into sized creative variations in Canva.
argument-hint: [run id, or "latest"]
allowed-tools: mcp__Canva__*, Bash(python3:*), Read, Glob, Grep
---

# Creative variations

Run: `$ARGUMENTS` — defaults to `latest`.

Only ever build creative from copy that has already passed validation. That is
the point of the ordering: character limits and voice are settled before anything
reaches a design, so a rejected line never becomes forty exported PNGs.

## 1. Take the approved copy

```bash
python3 -m adbrain validate --run latest    # must pass before continuing
```

Read `<run>/candidates.json` and `<run>/changes.md`. If validation has not
passed, **stop** and say so — do not build from unvalidated copy.

## 2. Find a template that accepts variable content

```
search-brand-templates  with dataset: "non_empty"
```

Only templates with a non-empty dataset can take variable content. Then:

```
get-brand-template-dataset  template_id: <BTM...>
```

That returns the named fields — Canva's equivalent of Figma's named layers. Map
them onto the copy fields from the run (`headline`, `description`,
`primary_text`). If the names do not line up, show the user both lists and ask
which maps to which rather than guessing — a wrong mapping produces a batch of
confidently wrong designs.

If no template has a dataset, say so and offer the `create_url` so one can be set
up by hand once. It only has to happen once.

## 3. Build the batch

For each copy variation:

1. `create-design-from-brand-template` with the template ID
2. `edit-design` to set the text fields for that variation
3. `resize-design` for each aspect ratio needed — 1:1 feed, 9:16 stories/reels,
   4:5 feed. Design the most constrained ratio first; the taller formats have
   more room, which is space for context, not for padding.

**Confirm the count with the user before starting.** Each variation is several
API calls against their account, and forty variations is not a small ask of
someone's Canva workspace. State the number and wait.

> Canva's `autofill-design` — which would fill a whole template in one call — is
> referenced in the docs but is **not available in this connector**. So this is
> create → edit → export per variation. Fine for tens; revisit before hundreds.

## 4. Export

```
get-export-formats  design_id: <D...>     # always check first
export-design       design_id: <D...>, format: {type: "png"}
```

Never guess a format — `get-export-formats` first, every time; unsupported
formats fail the call. Show the user every download URL.

## 5. Log it

The creative that shipped is part of the experiment:

```bash
python3 -m adbrain log --run latest --notes "creative: <N> variations from <template name>, ratios 1:1 / 9:16"
```

## Rules

- Never build from copy that has not passed `adbrain validate`.
- Never invent a proof point at the design stage. If a template has a field the
  copy does not fill, leave it empty and flag it — do not write new copy here to
  fill a box. Copy is written by the sub-agents, against the brand rules, and
  validated. This step arranges it; it does not author it.
- Confirm the batch size before creating anything in the user's account.
