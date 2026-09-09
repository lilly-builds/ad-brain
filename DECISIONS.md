# Decisions

Choices made while building, with the tradeoff and how to reverse each one. The
build brief said to surface tradeoffs rather than choose silently; the standing
instruction is hands-off. So: I chose, and wrote down the cost of each choice and
the one-line reversal.

---

### 1. Both Google Ads and Meta in scope, via a data-driven spec registry

**Tradeoff.** Building for two platforms normally doubles the surface area —
different limits, exports, and bulk formats.

**Why it did not here.** The `ad-creative` skill already carries verified specs
for Google RSA, Google PMax, Meta, LinkedIn and TikTok. Encoding them as *data*
in `config/platforms.toml` rather than as code means the validator, the brief
builder and the CSV writer are all platform-agnostic and adding a platform is
five lines of TOML. The doubling would only have happened if I had written
per-platform logic.

**What is genuinely per-platform** and therefore only built where needed: the
export parser and the bulk-upload writer. Google RSA and Meta are done; LinkedIn
and TikTok have limits registered but no parser yet.

**Reverse it:** delete the unwanted table from `config/platforms.toml`.

---

### 2. Zero runtime dependencies, Python 3.11 standard library only

**Tradeoff.** No pandas means the ranking code does its own arithmetic —
roughly 60 extra lines. No PyYAML means config is TOML rather than YAML.

**Why.** This system is run by a marketer, not maintained by an engineer. A
dependency-free tool runs on a clean machine forever with no install step,
no version conflicts, and nothing that breaks six months from now when a
transitive dependency ships a bad release. At this data size — hundreds of ads,
not millions — pandas buys nothing.

**Reverse it:** add to `dependencies` in `pyproject.toml`.

---

### 3. Config in TOML, not YAML or JSON

**Tradeoff.** TOML is slightly clumsier than YAML for deeply nested data.

**Why.** `tomllib` is in the standard library (decision #2), TOML supports
comments where JSON does not, and the config files are the *interface* for
changing behaviour without touching code — comments are the whole point. The
nesting here is shallow enough that TOML's awkwardness never bites.

**Reverse it:** swap the loader in `src/adbrain/config.py`.

---

### 4. Validation gates on the *display* limit, not the API maximum

**Tradeoff.** Meta's API accepts a 2,200-character primary text; we reject at
125. Some genuinely good long-form copy will be blocked.

**Why.** Copy that the API accepts but the feed truncates is a silent failure —
it ships, it looks fine in the dashboard, and it underperforms for a reason
nobody attributes correctly. Failing loudly at generation time is cheaper. Every
platform's true maximum is recorded as `hard_max` alongside, so nothing is lost.

**Reverse it:** set `limit = hard_max` for that field in `config/platforms.toml`.

**Open conflict to resolve:** the `ad-creative` skill states Meta description as
25 characters in `SKILL.md` and 30 in `references/platform-specs.md`. This repo
uses **30**, from the fuller reference doc. Worth reconciling the skill.

---

### 5. Experiment memory is markdown files plus a JSONL index, not a database

**Tradeoff.** No queries beyond what the retrieval code implements. Reconciling
the two representations is the system's job, and they can drift if something
writes one without the other.

**Why.** The brief was explicit that the log must be readable by a human, and a
SQLite file is not. Markdown per run means you can open `memory/experiments/`
and read what the system has learned; the JSONL index means retrieval does not
have to parse prose. Only `src/adbrain/memory.py` writes either, so drift has one
place to go wrong.

**Reverse it:** if the log passes ~500 runs and retrieval gets slow, the JSONL
index is already the schema — porting it to SQLite is mechanical, and the
markdown stays as the human view.

---

### 6. The official Meta Ads MCP, used read-only by convention

**Tradeoff.** The official server at `mcp.facebook.com/ads` grants **full write
access to the live ad account — no draft mode, no confirmation step, no undo.**
It is not possible to request a read-only scope; the beta does not offer one.

**Why use it anyway.** It is Meta's own, OAuth-authenticated, with no token to
create or rotate, and it replaces a third of the original build. The
alternatives are third-party servers that want long-lived credentials.

**How the risk is contained.** `CLAUDE.md` and `docs/meta-ads-mcp.md` require
that any campaign-mutating tool call be confirmed with Lilly first, every time.
The analysis commands in `.claude/commands/` are read-only by construction.
This is a convention, not a technical guarantee — it is the honest state of the
beta, and worth knowing before connecting.

**Reverse it:** disconnect the connector; fall back to CSV exports, which is how
Phase 1 already works.

---

### 7. Google Ads gets CSV export, not an MCP connection

**Tradeoff.** Google campaign analysis stays a manual export step.

**Why.** Google's official MCP offering does not currently match Meta's — the
credential path is a developer token plus OAuth client plus refresh token, which
is real setup work for a non-technical operator. Google Ads Editor's CSV export
is the format the bulk upload has to match anyway, so the export is not wasted
motion. Revisit when Google ships an OAuth-only server.

**Reverse it:** `docs/google-ads-mcp.md` has the full assessment and the
credential path if it becomes worth it.

---

### 8. Longevity as the performance proxy for competitor ads

**Tradeoff.** It is a proxy, not a measurement. A long-running ad might be a
neglected evergreen rather than a winner.

**Why.** Public ad libraries publish *creative*, never performance. There is no
public CTR, no public spend. Anyone selling category performance benchmarks is
selling estimates. Days-live is the one signal that is both public and
economically meaningful: nobody pays to keep a loser live for six months.

**How the weakness is handled.** The digest reports days-live as an observation
with its own uncertainty stated, never as "this ad performs well". Ads that
*just died* after a long run are treated as the higher-signal event.

---

### 9. Phase 5 targets Canva, not Figma

**Tradeoff.** Departs from the Anthropic system, which used a Figma plugin.

**Why.** Canva is already connected to this workspace as an MCP server with
design generation, brand templates, and bulk export. Figma is not connected and
there is no evidence Opterra's creative lives there. Building a Figma plugin
would mean introducing a tool as well as automating one. Full evaluation of both
open-source plugins is in `docs/creative-scale.md`.

**Reverse it:** if creative does live in Figma, `docs/creative-scale.md` has the
fork-vs-build assessment ready.
