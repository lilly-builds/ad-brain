# Connecting Meta Ads

Meta runs an official MCP server at **`https://mcp.facebook.com/ads`** (open
beta since 29 April 2026). We use it rather than building one or using a
third-party server, because it is Meta's own, it authenticates through Business
OAuth in the browser, and **there is no token to create, store, or rotate.**

That last point is the main reason this is worth doing: every third-party Meta
MCP server wants a long-lived access token sitting in a config file somewhere.
This one does not.

---

## Before you click anything: what you are granting

The OAuth screen offers a scope picker. **What you choose here is the whole
security decision** — read it before you agree to it.

| Scope | What it actually allows | Grant it? |
|---|---|---|
| `ads_read` | Read campaigns, ad sets, ads, creative, and all insights and reporting | **Yes** |
| `ads_management` | Everything above, **plus create, edit, pause, and change budgets on live campaigns** | **No — see below** |
| `business_management` | Read and manage Business Manager assets: pages, pixels, users, asset permissions | **No** |

### Grant `ads_read` only

This system does not need write access. Phase 1 produces a bulk-upload CSV that
imports **paused**, and you review it before enabling. That is the deliberate
design: a human sees every ad before it spends money.

`ads_management` would let a model change budgets and pause live campaigns
directly from a chat message. There is **no draft mode, no confirmation screen,
and no undo** on the other side of that call. The upside is convenience; the
downside is an ad account, and the two are not close.

If you later decide you want write access for a specific job, re-run the OAuth
flow and add the scope then. Widening later is easy. Narrowing after an
accident is not.

---

## Setup

1. **Check your account is eligible.** Meta is rolling this out gradually — US
   and higher-spend accounts first. If setup fails with
   `is_ads_mcp_enabled: false`, your ad account is not in the rollout yet.
   That is not something you can configure around; it is a waiting game.

2. **Add the server in Claude Code:**

   ```bash
   claude mcp add --transport http meta-ads https://mcp.facebook.com/ads
   ```

   Paste the endpoint exactly — no trailing slash, no extra path.

3. **Authenticate.** Run `/mcp` in Claude Code and follow the OAuth flow. It
   opens a browser and uses authorization-code OAuth with PKCE.

4. **At the scope picker, select read-only / `ads_read`.** Do not tick
   `ads_management` or `business_management`.

5. **Select the specific ad account** you want connected. Connect one, not all
   of them — if something goes wrong the blast radius is one account.

6. **Verify:**

   ```
   /mcp
   ```

   The server should list as connected. Then try: *"list my active Meta campaigns
   and their spend over the last 7 days."*

---

## What you get

Roughly 29 tools spanning reporting and insights, campaign management, catalog
operations, account diagnostics, and dataset quality. With `ads_read` granted,
the reporting and diagnostic tools work and the management tools will fail with
a permissions error — which is the intended outcome, not a misconfiguration.

## Standing rule for this repo

**Any tool call that would change a live campaign must be confirmed with the
account owner first, every time.** With `ads_read` this is enforced by Meta.
If write scope is ever granted, it becomes a convention only — and conventions
are exactly what fail at 6pm on a Friday. Prefer the enforced version.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `is_ads_mcp_enabled: false` | Account not yet in Meta's rollout. Wait. |
| OAuth completes but no accounts listed | The Meta user you authenticated as has no role on the ad account. |
| Only some employees can authorise | The app is in development mode; Live mode with Advanced Access is needed for everyone. |
| Management tools return permission errors | Expected with `ads_read`. This is the design working. |
