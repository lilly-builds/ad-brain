# Category monitoring: what is actually observable

Read this before trusting anything in a category digest. The constraints here
are real, and a monitoring system that pretends otherwise produces confident
nonsense.

---

## 1. Performance is never public

Public ad libraries publish **creative**, not results. There is no public CTR,
no public spend, no public conversion rate for commercial advertisers. Any tool
promising "competitor performance benchmarks" is selling panel estimates or
modelled guesses, and neither belongs in a decision about your own copy.

**What we use instead: longevity.** An ad running continuously for months is
probably working, because nobody keeps paying to serve a loser. An ad that just
stopped after a long run is a stronger signal still — something that was being
paid for got retired.

This is a **proxy, not a measurement**, and the digest says so every time. A
long-running ad might be a neglected evergreen that nobody has reviewed. Treat
it as a strong hint.

## 2. The Ad Library API does not cover US commercial ads

This is the constraint that shapes the whole workflow, and it surprises people:

| What | Where | How far back |
|---|---|---|
| Political and social-issue ads | Worldwide | 7 years |
| **All ad types** | **EU and UK only** | 1 year |
| Commercial ads | Everywhere else | **Not available** |

The EU/UK coverage exists because the Digital Services Act requires it. There is
no equivalent obligation in the US, so **a US-only SaaS competitor's ads are not
in the API at all.** No parameter changes that. The Ad Library *web UI* shows
them; the API does not expose them.

### What this means in practice

- **Competitors that advertise into the EU or UK** — the API works. Many
  software vendors run UK campaigns, so this covers more of a watchlist than you
  would expect. Always worth trying first.
- **US-only advertisers** — capture manually. It is genuinely a few minutes per
  competitor, and it only has to happen at whatever cadence the digest runs.

**We do not scrape the Ad Library web UI.** It is against Meta's terms, it
breaks without warning, and a longevity history built on a scraper cannot be
trusted precisely when it matters.

## 3. Getting API access, if the EU/UK path is useful to you

1. **Confirm your identity** at `facebook.com/ID` — government ID, country of
   residence. Takes 1–3 business days. This is the same confirmation required to
   run political ads, which is why it feels heavier than expected.
2. **Create a Meta for Developers app** and add the **Ad Library API** product.
3. **Generate an access token**, put it in `.env` as `META_AD_LIBRARY_TOKEN`.
4. Test: `adbrain category snapshot --country GB`

A 400 from the API almost always means step 1 has not finished.

---

## The manual capture path

This is a first-class source, not a fallback. The analysis layer does not care
where a snapshot came from, so a watchlist can mix API and manual sources, and
the longevity history survives switching between them.

```bash
adbrain category template          # writes data/inbox/category-capture.csv
```

Then, for each competitor, open the Ad Library web UI, filter to their page, and
fill one row per distinct creative:

| column | notes |
|---|---|
| `advertiser` | required |
| `headline` / `body` | at least one required |
| `started_running` | **worth the effort** — the UI shows "Started running on ..." |
| `angle`, `hook`, `offer` | leave blank; the scout agent classifies them |
| `relationship` | `direct` or `adjacent` |

`started_running` is the one field to be diligent about. Without it, longevity is
counted from your first capture, which understates every ad that was already
live — and the ads already live for six months are exactly the ones you most
want to notice.

```bash
adbrain category snapshot --from-file data/inbox/category-capture.csv
adbrain category digest
```

## 4. Watch adjacent advertisers, not only direct competitors

A watchlist of direct competitors tells you what you already know. New angles
usually arrive from companies selling to the same buyer about a different
problem — they invent the framing, it works, and it reaches your category six
months later. `config/competitors.toml` has a separate `adjacent` list for
exactly this reason. Use it.

## 5. Cadence

The digest reports **what changed**, so it is only as useful as the gap between
captures. Monthly is a sensible default: long enough for something to have
happened, short enough that an ad's death is still attributable.

Weekly produces mostly noise. Quarterly means finding out about a category shift
a quarter late.
