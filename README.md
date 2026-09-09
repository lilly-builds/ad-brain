# ad-brain

Growth marketing automation for **Opterra Ventures**, modelled on the system
Anthropic's own growth marketing team built and documented in
[How Anthropic teams use Claude Code](https://www-cdn.anthropic.com/58284b19e702b49db9302d5b6f135ad8871e7658.pdf)
(section: *Claude Code for growth marketing*).

Their system is four workflows built by a non-technical team of one. This repo
reconstructs those four and adds two more that close a gap in the original.

## The workflows

| # | Workflow | What it does | Status |
|---|---|---|---|
| 1 | **Ad copy agent** | Ingests a performance export, ranks and flags underperformers, regenerates replacements through two specialised sub-agents, enforces character limits programmatically, emits a bulk-upload CSV plus a diff explaining every change | ✅ |
| 2 | **Experiment memory** | Logs the hypothesis, variables and outcome of every run; pulls prior results into context before generating, so the system stops re-testing angles that already lost | ✅ |
| 3 | **Live campaign data** | Queries campaign performance in-session through the official Meta Ads MCP, instead of exporting CSVs | ✅ |
| 4 | **Category monitoring** | Watches competitor and adjacent-category ads through the Meta Ad Library, using creative longevity as the performance proxy, and reports what *changed* | ✅ |
| 5 | **Creative variation at scale** | Fans one approved angle out into many sized creatives | 📋 assessed, see `docs/creative-scale.md` |

Workflow 2 is the one that compounds. Everything else gets faster; only memory
gets *better*.

### Why 4 exists

All four of Anthropic's workflows are inward-facing — their ads, their
campaigns, their experiment log. A loop like that only ever learns to beat its
own past performance and has no way to notice that the category has moved.
Workflow 4 closes that, and writes its findings into the same log as workflow 2
so the copy agent sees both what we have tested and what the category is
currently running.

## Quick start

```bash
# no install step — zero dependencies, Python 3.11+
python3 -m adbrain --help          # from repo root, or:
pip install -e .  &&  adbrain --help

# run the whole loop against the bundled sample export
adbrain rank    --input data/fixtures/google_rsa_sample.csv --platform google_rsa
adbrain brief   --run latest       # writes the generation brief the sub-agents read
# ...Claude generates candidates via .claude/agents/ ...
adbrain validate --run latest      # rejects anything over limit or off-voice
adbrain build   --run latest       # bulk CSV + human-readable diff
adbrain log     --run latest       # writes the experiment record
```

Or just open Claude Code in this repo and say **"refresh the underperforming
Google ads"** — `.claude/commands/` wires the whole sequence.

## Layout

```
brand/            voice, ICP, and approved proof points — the human source of truth
config/           character limits, flagging thresholds, voice rules, watchlist
                  (all plain-language TOML; change these, not the code)
src/adbrain/      the engine — ingest, ranking, validation, memory, output
.claude/agents/   the two specialised copy sub-agents + the category scout
.claude/commands/ named workflows you rerun
memory/           the experiment log — readable as plain markdown
data/inbox/       drop platform exports here
data/out/         generated bulk CSVs and diff reports
docs/             auth setup, MCP assessment, and the Phase 5 evaluation
```

## Reading order

New to the repo: `CLAUDE.md` → `DECISIONS.md` → `memory/LEARNED.md`.
