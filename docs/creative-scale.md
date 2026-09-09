# Phase 5: creative variation at scale — evaluation

The brief asked for an evaluation before any building. Here it is, plus the one
question that has to be answered before this phase is worth starting.

---

## What Anthropic's team built

A Figma plugin that identifies frames and swaps headline and description text to
produce up to 100 variations per batch — reportedly about half a second per
batch. The mechanism is unremarkable and that is the point: a template with
named text layers, a list of copy, and a loop.

**The value is not in the plugin.** It is in having approved, character-validated
copy ready to pour into it. That is Phases 1 and 2, and they are built. This
phase is the last mile, and it is the least interesting part of the system —
which is why the brief correctly put it last and marked it optional.

## The two named open-source plugins: do not fork either

| Repo | Stars | Verdict |
|---|---|---|
| `milopraetzel/Agent-figma-creative-variations` | 5 | Could not verify it exists at that path. |
| `strombergmpd/figma-plugin-ad-copy` | 0 | Could not verify it exists at that path. |

Neither could be confirmed, and the star counts in the brief (5 and 0) tell you
what you need to know regardless: **a 0-star repo is not a maintained dependency,
it is someone else's weekend, and forking it means owning it immediately.**

The honest read: at this size there is nothing to fork that is cheaper than
writing the ~150 lines yourself against whichever API you land on. "Use existing
open source rather than writing your own" is the right instinct and it is why
Phases 3 and 4 wire into vendor servers — but it only applies when the existing
thing is actually load-bearing. These are not.

## Canva is already connected — and mostly covers this

Canva's MCP server is connected to this workspace today, with no build required:

| Tool | Use here |
|---|---|
| `search-brand-templates` (filter `dataset: non_empty`) | find templates that accept variable content |
| `get-brand-template-dataset` | discover the named fields — the equivalent of Figma's named layers |
| `create-design-from-brand-template` | one design per copy variation |
| `edit-design` | set the text in each |
| `resize-design` | 1:1 → 9:16 → 4:5 without redesigning |
| `get-export-formats` → `export-design` | PNG/JPG out, with a download URL |

**One gap worth knowing:** Canva's docs reference an `autofill-design` tool that
would fill a whole template from a dataset in a single call. It is **not exposed
in the connector build available here.** So a batch is create → edit → export per
variation rather than one autofill call — more round trips, and slower than the
"half a second per batch" figure. For tens of variations that is fine. For
hundreds, it would want revisiting.

## Recommendation

**Do not build a Figma plugin.** Two reasons, and the second is the real one:

1. Nothing forkable exists at a quality worth inheriting.
2. Figma is not connected to this workspace and there is no evidence creative
   lives there. Building a Figma plugin would mean **introducing a tool as well
   as automating one** — that is a workflow change wearing an automation costume,
   and it is how automation projects quietly fail.

**Use whatever tool the creative already lives in.** If that is Canva, it is
wired and ready. If it is Figma, the plugin is a genuinely small build — a
template with named layers, a JSON array of validated copy from a completed
`adbrain` run, and a loop over `figma.currentPage` cloning frames and setting
`characters` on each named node.

## The one question that gates this

**Where does the creative actually live?**

| Answer | What happens |
|---|---|
| **Canva** | `/creative-variations` works today. Point it at a brand template. |
| **Figma** | ~150-line plugin, one session's work, written fresh rather than forked. |
| **Neither / it's outsourced** | Skip this phase. Phase 1 already emits validated copy in a CSV that a designer can work from, which may be the whole job. |

Until that is answered, building either version is a coin flip, and the wrong
side costs a working system that nobody uses.

## What is ready now

`.claude/commands/creative-variations.md` — drives the Canva path end to end,
using only tools verified present in this workspace. It reads approved copy from
a completed run, so nothing reaches a design that has not already passed the
character-limit and voice gates.
