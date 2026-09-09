# CLAUDE.md — operating manual for ad-brain

This repo is Opterra's growth marketing system. Read this before doing anything
in it. It is maintained as the system grows — when you learn something about how
this repo should behave, write it down here.

## Who you are working with

Lilly runs Opterra Ventures and wants to be **hands-off**. That means:

- Make the call yourself on reversible decisions. Record it in `DECISIONS.md`
  with how to reverse it, rather than asking.
- Escalate only when a decision is expensive to undo (spending money, writing to
  a live ad account, granting a permission scope) or when you would have to
  invent a fact — a client metric, a competitor claim, a budget number.
- Explanations should assume marketing fluency and no interest in Python
  internals. Say what changed and what it means for the ads, not how the parser
  works.

## The prime directive

**Never invent a proof point.** Every number, client name, or outcome in ad copy
must already exist in `brand/proof.md`. If a generated line needs a claim that is
not there, regenerate the line — do not add the claim. This is the one rule that
matters more than output volume.

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

`brand/voice.md` for humans, `config/voice.toml` for the validator. The rules the
validator hard-fails on: lowercase, no emoji, no fear framing, no corporate
filler, never "healer". Proper nouns keep their capitals via an allow-list.

The `ad-creative` skill (user-level, not in this repo) holds the fuller creative
framework — angle selection, the 15 creative types, the 5×5×5 Meta rule.
**Invoke that skill when generating**; this repo enforces and remembers, the
skill decides what to write. Do not copy its contents in here — it will drift.

## Memory

`memory/experiments/*.md` — one file per run, human-readable, meant to be
opened and read. `memory/index.jsonl` — the same facts, machine-queryable, for
retrieval. `memory/LEARNED.md` — the rolled-up standing conclusions.

Outcomes land days after generation. `adbrain outcome` backfills them. A run
with no outcome yet is not a failure; it is pending.

Category observations from Phase 4 land in the same log tagged
`source: external` so the copy agent sees owned tests and category movement
together.

## When you touch this repo

- Commit at every checkpoint, with a message naming the phase.
- Run `python3 -m pytest tests/ -q` before committing. It is fast and has no
  dependencies.
- Update this file when a convention changes.
