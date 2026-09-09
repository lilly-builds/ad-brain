# ad-brain

Growth marketing automation, modelled on the system Anthropic's own growth
marketing team built and documented in
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

## The brand layer

The engine is brand-agnostic. It enforces whatever it is told to enforce, and
every brand-specific fact is configuration:

| File | What goes in it |
|---|---|
| `brand/voice.md` | how the copy should sound, in prose, for the writers |
| `brand/icp.md` | who is being sold to, and what this replaces |
| `brand/proof.md` | the only claims the copy agent is allowed to make |
| `config/voice.toml` | the enforceable subset — what `validate` actually rejects |
| `config/competitors.toml` | who to watch in Phase 4 |

These ship as **templates**. Fill them in before the first real run. Until then
the validator still enforces platform character limits, bans emoji, catches
generic ad filler, and flags any number that does not trace to an approved
claim — so the system is useful on day one and gets sharper as the brand layer
is filled in.

Running for several brands: keep one filled-in `brand/` + `config/` pair per
client and swap the directory.

## Quick start

```bash
# no install step — zero dependencies, Python 3.11+
export PYTHONPATH=src
python3 -m adbrain --help          # or: pip install -e . && adbrain --help

# the loop, against the bundled synthetic export
python3 -m adbrain rank --input data/fixtures/google_rsa_sample.csv --platform google_rsa
#   ranks the account, flags underperformers, writes brief.md for the sub-agents
#   ...the copy sub-agents in .claude/agents/ write candidates.json...
python3 -m adbrain validate --run latest   # rejects anything over limit or off-voice
python3 -m adbrain build    --run latest   # bulk CSV (imports paused) + change report
python3 -m adbrain log      --run latest   # records what we are testing and why
```

Useful on their own:

```bash
python3 -m adbrain limits --platform meta          # what the limits currently are
python3 -m adbrain check "one tool, not five" --platform google_rsa --field headline
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
