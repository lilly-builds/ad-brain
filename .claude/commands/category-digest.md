---
description: Capture what competitors are running and report what changed since last time.
argument-hint: [path to a capture file, or nothing to use the API where it works]
allowed-tools: Bash(python3:*), Read, Write, Edit, Glob, Grep, Task, WebFetch
---

# Category digest

Argument: `$ARGUMENTS` — a capture file, or nothing.

The product here is **the diff, not the dump**. A list of competitor ads is not
useful; what changed since last time is.

## 1. Get a snapshot in

Check what already exists:

```bash
ls memory/category/snapshots/
```

**If a capture file was given:**

```bash
python3 -m adbrain category snapshot --from-file <path>
```

**If not,** try the API for competitors that advertise into the EU or UK:

```bash
python3 -m adbrain category snapshot --country GB
```

If that returns nothing, do not treat it as an error — for US-only commercial
advertisers the API has no coverage at all, by design. See
`docs/ad-library-access.md`. Generate a capture sheet and tell the user what to
fill in:

```bash
python3 -m adbrain category template
```

Be specific about `started_running`: it is the "Started running on" date in the
Ad Library UI, and without it every already-live ad looks new.

## 2. Classify before diffing

If the incoming ads have empty `angle` / `hook` / `offer` fields, dispatch the
`category-scout` agent to fill them, reusing the vocabulary already present in
earlier snapshots. Comparable labels are the whole point — four wordings of one
idea hide the finding that three competitors are running it.

Write the classified values back into the snapshot JSON before continuing.

## 3. Digest

```bash
python3 -m adbrain category digest
```

## 4. Interpret

Have `category-scout` read the digest and answer three things:

- **What is new** in the category
- **What died**, and what appeared in its place
- **Where the gap is**, and whether it is unclaimed or simply does not work

Weight a long-running ad that just stopped above everything else. It is the
strongest signal a public library offers.

## 5. Log what should change our writing

```bash
python3 -m adbrain category log --angle "..." --finding "..." --advertiser "..."
```

Log only observations that would change a future headline. These land in the
same experiment log as our own tests, tagged `external`, so the copy agent sees
what we have tested *and* what the category is running — which is the entire
reason this workflow exists.

## Rules

- Never state a competitor's CTR, spend, or conversion rate. None are public.
- Always frame longevity as a proxy: "has run 207 days, which usually means it
  is working", never "performs well".
- Do not scrape the Ad Library UI. Manual capture is the supported path.
