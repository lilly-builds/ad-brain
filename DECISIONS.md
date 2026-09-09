# Decisions

Choices made while building, with the tradeoff and how to reverse each one. The
build brief said to surface tradeoffs rather than choose silently; the standing
instruction is hands-off. So: I chose, and wrote down the cost of each choice and
the one-line reversal.

---

### 0. The engine is brand-agnostic; the brand is configuration

**Tradeoff.** A system hardwired to one brand's voice can be more opinionated —
it can bake the rules into the prompts and skip the config layer entirely.

**Why not.** Voice, ICP, proof points and the competitor list all live in
`brand/` and `config/` as templates, and the code knows nothing about any
particular brand. That means the same repo runs for a second brand by swapping a
directory, the voice rules can change without a code change, and — most
importantly — the enforcement layer stays honest: it checks what it is *told* to
check, so nobody has to guess whether a rule is live.

**The cost:** an unfilled `brand/` produces generic copy. That is the system
working correctly on an empty brief, but it does mean the templates are a real
prerequisite, not optional polish.

**Reverse it:** there is nothing to reverse — fill in `brand/` and the system
becomes exactly as opinionated as the brand is.

---

### 1. Both Google Ads and Meta in scope, via a data-driven spec registry

**Tradeoff.** Building for two platforms normally doubles the surface area —
different limits, exports, and bulk formats.

**Why it did not here.** Encoding limits as *data* in `config/platforms.toml`
rather than as code means the validator, the brief builder and the CSV writer are
all platform-agnostic, and adding a platform is five lines of TOML. The doubling
would only have happened with per-platform logic. Google RSA, Google PMax, Meta,
LinkedIn and TikTok limits ship registered.

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

**Note.** Published Meta description limits vary between 25 and 30 characters
depending on the source. This repo uses **30**. If uploads start getting
truncated in a placement that matters, drop it to 25 — one number, one file.

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

### 6. The official Meta Ads MCP, granted read-only scope

**Tradeoff.** With `ads_read` only, nothing in this system can pause an ad,
change a budget, or launch a campaign from a chat message. Every action needs a
human in Ads Manager.

**Why.** The scope picker in Meta's OAuth flow offers read-only, read/write, and
read/write/financial. Read/write (`ads_management`) has **no draft mode, no
confirmation screen, and no undo** — a model that misreads a request can change
live spend directly. The convenience it buys is real but small; this system's
output is a bulk CSV that imports paused and gets reviewed anyway.

So the safety property is enforced by Meta rather than promised by a convention
in a markdown file. Conventions are exactly what fail under time pressure.

**Why this server at all:** it is Meta's own, OAuth-authenticated in the browser,
with no token to create, store, or rotate. Every third-party alternative wants a
long-lived credential in a config file.

**Correction to an earlier draft of this file:** it claimed the beta offered no
read-only scope. That was wrong — `ads_read` exists and is what we grant. Setup
and the full scope table are in `docs/meta-ads-mcp.md`.

**Reverse it:** re-run the OAuth flow and add `ads_management`. Widening later
is easy; narrowing after an accident is not.

---

### 7. Google Ads gets the official MCP too — it is read-only by construction

**Tradeoff.** Setup is genuinely more work than Meta's: a Google Cloud project,
a developer token (with an access-level application and review), and OAuth
credentials. Roughly an hour, versus Meta's few minutes.

**Why it is still worth it.** Google shipped an official server on 28 April 2026
(`googleads/google-ads-mcp`, Apache 2.0) that **cannot write at all** — it
exposes three read-only tools and no mutation path. It is structurally safer
than the Meta integration, not just configured more carefully.

Its surface is deliberately small: `list_accessible_customers`,
`get_resource_metadata`, and `search`, which runs GAQL. That makes the analysis
commands in `.claude/commands/` saved queries rather than wrappers around
pre-baked tools, which ages better.

**Correction to an earlier draft of this file:** it said Google had no offering
matching Meta's and recommended CSV exports instead. That was wrong.

**Not blocking:** Phase 1 runs entirely on CSV exports, and Google Ads Editor's
export format is what the bulk upload has to match anyway. Connect the server
when there is an hour spare, not before the system is useful.

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

### 8a. Manual capture is a first-class snapshot source, not a fallback

**The finding that forced this.** The build brief described the Meta Ad Library
API as "every currently-active ad from every advertiser, queryable". That is not
what it is. Coverage is:

| What | Where | How far back |
|---|---|---|
| Political and social-issue ads | Worldwide | 7 years |
| **All ad types** | **EU and UK only** (a DSA obligation) | 1 year |
| Commercial ads | Anywhere else | **Not available** |

**A US-only commercial competitor is not in the API at all**, and no parameter
changes that. The web UI shows those ads; the API does not expose them.

**What was built instead.** The snapshot layer is source-agnostic. `fetch()`
queries the API and is genuinely useful for competitors that advertise into the
EU or UK — many software vendors do. `from_file()` reads a capture sheet filled
in from the Ad Library web UI. Both produce the same snapshot, so a watchlist can
mix sources and the longevity history survives switching between them.

**What was deliberately not built: a scraper.** Scraping the Ad Library UI
violates Meta's terms, breaks without notice, and a longevity history built on it
becomes untrustworthy exactly when it matters. The manual path costs a few
minutes per competitor per digest cycle and the data is reliable.

**The real consequence:** the value of this phase was never the fetch. It is the
diff between snapshots, the longevity tracking, and the classification — all of
which work identically whatever the source.

---

### 8b. Phase 4 calls into `comp-ad-analyzer` rather than reimplementing it

The build brief asked directly. The answer is **call into it** — for
classification only.

`comp-ad-analyzer` is a prompt-level framework with no code behind it: creative
analysis, messaging strategy, positioning against category norms,
counter-positioning. That is a taxonomy, and taxonomies belong in a skill where
they can be revised without a commit.

What it cannot do is collection, longevity tracking across snapshots, diffing, or
persistence — it has no state. So the split is clean: the skill decides *how to
classify*, `adbrain category` handles everything that requires memory. The
`category-scout` agent is wired to invoke the skill rather than carry its own
copy of the framework, so the two cannot drift.

---

### 9. Phase 5 targets Canva, not Figma

**Tradeoff.** Departs from the Anthropic system, which used a Figma plugin.

**Why.** Canva is already connected to this workspace as an MCP server with
design generation, brand templates, and bulk export. Figma is not connected, and
building a Figma plugin would mean introducing a tool as well as automating one.
Full evaluation of both open-source plugins is in `docs/creative-scale.md`.

**Reverse it:** if creative does live in Figma, `docs/creative-scale.md` has the
fork-vs-build assessment ready.
