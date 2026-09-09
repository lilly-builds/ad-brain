# CLAUDE.md — operating manual for ad-brain

This repo is a growth marketing system. Read this before doing anything in it.
It is maintained as the system grows — when you learn something about how this
repo should behave, write it down here.

## The engine is brand-agnostic

Nothing about any particular brand's voice is hardcoded. The engine enforces
whatever it is told to enforce, and the brand is configuration:

| What | Where | Read by |
|---|---|---|
| Voice, in prose | `brand/voice.md` | the copy sub-agents |
| Voice, enforceable | `config/voice.toml` | `adbrain validate` |
| ICP and positioning | `brand/icp.md` | the copy sub-agents |
| Approved claims | `brand/proof.md` | `adbrain validate` |
| Competitor watchlist | `config/competitors.toml` | Phase 4 |

These ship as **templates**. Until they are filled in, the validator enforces
only the platform character limits and a neutral starter set of banned filler.
Running against an unfilled `brand/` will produce generic copy — that is the
system working correctly on an empty brief, not a bug.

**Running for more than one brand:** keep one filled-in `brand/` + `config/`
pair per client and swap the directory, or clone the repo per client. Do not add
per-client branches in code.

## Who you are working with

Lilly wants to be **hands-off**. That means:

- Make the call yourself on reversible decisions. Record it in `DECISIONS.md`
  with how to reverse it, rather than asking.
- Escalate only when a decision is expensive to undo (spending money, writing to
  a live ad account, granting a permission scope) or when you would have to
  invent a fact — a client metric, a competitor claim, a budget number.
- Explanations should assume marketing fluency and no interest in Python
  internals. Say what changed and what it means for the ads, not how the parser
  works.

## The prime directive

**Never invent a proof point.** Every number, customer name, or outcome in ad
copy must already exist in `brand/proof.md`. If a generated line needs a claim
that is not there, regenerate the line — do not add the claim. This is the one
rule that matters more than output volume, and it is enforced: `validate` flags
any number that does not trace to an approved claim.

## The loop

```
export ──▶ rank ──▶ brief ──▶ sub-agents ──▶ validate ──▶ build ──▶ log
             │        │                          │                    │
             │        └── retrieves prior         └── rejects and      └── writes
             │            results from memory/        regenerates,         memory/
             └── flags per config/thresholds.toml     never truncates
```

Every stage is a subcommand of `adbrain`. Run them in order; each reads the run
directory the previous one wrote. `--run latest` always means the most recent.

## Rules that are not negotiable

1. **Character limits are enforced in code, not in prompts.** `config/platforms.toml`
   is the source of truth. A prompt asking for "under 30 characters" is a
   suggestion; `validate` is the gate. Never bypass it.
2. **Over-limit copy is regenerated, never truncated.** Truncating produces
   copy that technically fits and says nothing. `validate` emits a regeneration
   request with the overage; the sub-agent rewrites.
3. **Two sub-agents, not one prompt.** Headlines and descriptions are written by
   `.claude/agents/headline-writer.md` and `description-writer.md` separately.
   Anthropic's team found this improves quality and makes failures debuggable —
   when output is bad you know which agent to fix. Do not merge them.
4. **Read memory before generating.** `adbrain brief` pulls prior results into
   the brief. If you generate without it you will re-propose angles that already
   lost. Never skip straight to writing copy.
5. **Config over code.** Thresholds, limits, voice rules and the watchlist all
   live in `config/*.toml` in plain language. If Lilly wants a different
   threshold, edit the TOML — do not write a new code path.

## Character limits — the current numbers

Authoritative values are in `config/platforms.toml`. At a glance:

| Platform | Headline | Description | Body |
|---|---|---|---|
| Google RSA | 30 (3–15 of them) | 90 (2–4) | — |
| Meta | 40 | 30 | primary text 125 |
| LinkedIn | 70 | 100 | intro 150 |
| TikTok | — | — | ad text 100 |

Meta's *API* accepts far longer strings than these. We gate on the display
limit, because copy that is accepted but truncated in the feed is a silent
failure. See `DECISIONS.md` #4.

## Voice

`brand/voice.md` for humans, `config/voice.toml` for the validator. A rule that
exists only in the markdown is not enforced — if it matters, encode it.

The validator ships checking: emoji, a neutral set of ad-copy filler, and any
number that does not trace to `brand/proof.md`. The letter-case rule
(`[case] rule`) defaults to `any`; set it to `lowercase` or `sentence` if the
brand has one, and list proper nouns in `allow_capitalized` so they survive it.

**Creative strategy is not this repo's job.** Angle selection, creative-type
choice, and the structure of a good ad belong in a skill. If the brand has one,
invoke it when generating and let this repo do what it is good at: enforcing and
remembering. Do not copy a skill's contents in here — it will drift out of sync.

## Memory

| File | What it is |
|---|---|
| `memory/experiments/<id>.md` | one file per run, written to be opened and read |
| `memory/index.jsonl` | the same facts, machine-queryable — what retrieval reads |
| `memory/LEARNED.md` | the rolled-up standing conclusions, regenerated on write |

Both representations are written by `memory.write()` from one record. Nothing
else may write either — that is the only place they can drift.

Outcomes land days after generation, so an experiment starts `pending` and is
resolved later with `adbrain outcome`. **An experiment that stays pending
forever taught us nothing**; `LEARNED.md` lists them separately and marks
anything over 21 days overdue.

Retrieval weights **losses above wins**, because re-testing an angle that
already failed is the single most expensive mistake this system exists to
prevent. Be accurate with verdicts — a mixed result is `flat`, not `won`.
Overstating one poisons every future brief.

Category observations from Phase 4 land in the same log tagged
`source: external`, so when the copy agent generates it sees both what we have
tested and what the category is currently running.

## Live campaign data

Two MCP servers, both connected **read-only**, set up in `docs/meta-ads-mcp.md`
and `docs/google-ads-mcp.md`:

- **Meta** — `https://mcp.facebook.com/ads`, granted `ads_read` only. The write
  scope (`ads_management`) has no draft mode and no undo; we do not grant it.
- **Google** — `googleads/google-ads-mcp`, read-only by construction, three
  tools with GAQL as the query surface.

**Never call a tool that changes a live campaign, budget, or ad status.** If the
right answer is "pause this", say so and let a human do it in the platform. The
system's output is a bulk CSV that imports paused and gets reviewed — keep that
property.

Named analysis commands: `/perf-summary`, `/creative-scorecard`, `/spend-pacing`.
These are a starting set built from the obvious questions. They should be
replaced by whatever actually gets checked manually each week — if a command is
not being rerun, rewrite it or delete it.

## When you touch this repo

- Commit at every checkpoint, with a message naming the phase.
- Run `PYTHONPATH=src python3 -m unittest discover -s tests` before committing.
  It is fast and needs nothing installed.
- Update this file when a convention changes.
