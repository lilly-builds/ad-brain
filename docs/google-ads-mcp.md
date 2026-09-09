# Connecting Google Ads

**Recommendation: connect it.** Google shipped an official MCP server for the
Google Ads API on 28 April 2026, and unlike Meta's it is **read-only by
construction** — it cannot modify bids, pause campaigns, or create assets even
if asked to. That makes it strictly safer than the Meta integration.

The catch is setup cost: Google requires the same credential chain the Google
Ads API has always required. There is no one-click OAuth here. Budget an hour.

Repo: `https://github.com/googleads/google-ads-mcp` (Apache 2.0)
Docs: `https://developers.google.com/google-ads/api/docs/developer-toolkit/mcp-server`

> An earlier Google repo, `google-marketing-solutions/google_ads_mcp_server`,
> is archived. Use `googleads/google-ads-mcp`.

---

## What it exposes

Three tools, deliberately small:

| Tool | What it does |
|---|---|
| `list_accessible_customers` | Customer IDs and account names you can reach |
| `search` | Runs a GAQL query against the account — this is the workhorse |
| `get_resource_metadata` | Field names and structure for a resource type, so queries can be written correctly |

Everything is expressed as GAQL, which means the analysis commands in
`.claude/commands/` are just saved queries. That is a good trade: a small,
composable surface beats 200 pre-baked tools.

---

## What you need

1. **A Google Cloud project** with the Google Ads API enabled.
2. **A developer token** from your Google Ads manager account
   (Tools → API Center). A new token starts with test-account access only;
   production data needs at least **Explorer access**, which is an application
   with a review turnaround.
3. **OAuth credentials** with the `https://www.googleapis.com/auth/adwords`
   scope — either an OAuth client ID/secret or Application Default Credentials.
4. **The manager account customer ID**, if you access accounts through a manager.

Put the values in `.env` (see `.env.example`). None of them belong in the repo.

## Install

```bash
# requires pipx
claude mcp add google-ads -- pipx run --spec git+https://github.com/googleads/google-ads-mcp.git google-ads-mcp
```

Or as project config in `.mcp.json` (copy from `.mcp.json.example`):

```json
{
  "mcpServers": {
    "google-ads": {
      "command": "pipx",
      "args": ["run", "--spec", "git+https://github.com/googleads/google-ads-mcp.git", "google-ads-mcp"],
      "env": {
        "GOOGLE_PROJECT_ID": "your-project-id",
        "GOOGLE_ADS_DEVELOPER_TOKEN": "your-developer-token"
      }
    }
  }
}
```

Verify with `/mcp`, then ask: *"list my accessible Google Ads customers."*

---

## If you would rather not do the setup

Phase 1 runs entirely on CSV exports and does not need this. Google Ads Editor's
export is the same format the bulk upload has to match anyway, so exporting is
not wasted motion — it is a step you would take regardless.

The thing you lose by staying on exports is asking questions mid-conversation.
That is a real loss over time, but it is not blocking, and the setup can happen
whenever there is an hour to spare.
