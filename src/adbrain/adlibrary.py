"""Meta Ad Library API client, and the manual capture path that covers its gap.

**Read this before relying on the API.** Coverage is far narrower than it
appears, and the gap is region-shaped:

  * **Political and social-issue ads** — worldwide, seven years.
  * **All ad types** — only where delivered to the **EU or UK**, past year
    (this is a DSA obligation, not a product decision).
  * **US commercial ads** — *not available through the API at all* unless the
    advertiser also targets the EU/UK or the ad is classified political.

So for a US-only SaaS competitor, `ads_archive` returns nothing, and no
parameter fixes that. The Ad Library *web UI* does show those ads; the API does
not expose them. See docs/ad-library-access.md.

Two consequences shape this module:

1. `fetch()` is worth running for any competitor that advertises into the EU or
   UK — which many software vendors do, so it is not a dead end.
2. `from_file()` exists so a manual capture is a first-class snapshot source.
   The analysis layer does not care where a snapshot came from, and the
   longevity history stays intact across a change of source.

We do not scrape the Ad Library UI. It is against Meta's terms, it breaks
without warning, and a snapshot history built on it cannot be trusted.
"""

from __future__ import annotations

import csv
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .category import CompetitorAd, synth_id

GRAPH_VERSION = "v21.0"
ENDPOINT = f"https://graph.facebook.com/{GRAPH_VERSION}/ads_archive"

FIELDS = [
    "id", "page_name", "page_id",
    "ad_creative_bodies", "ad_creative_link_titles",
    "ad_creative_link_captions", "ad_creative_link_descriptions",
    "ad_delivery_start_time", "ad_delivery_stop_time",
    "publisher_platforms", "ad_snapshot_url",
]

# Countries where the API returns all ad types rather than only political ones.
FULL_COVERAGE = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
    "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
    "SI", "ES", "SE", "GB",
}


class AdLibraryError(RuntimeError):
    pass


def token() -> str:
    value = os.environ.get("META_AD_LIBRARY_TOKEN", "").strip()
    if not value:
        raise AdLibraryError(
            "META_AD_LIBRARY_TOKEN is not set. The Ad Library API needs a token "
            "from an identity-confirmed Meta developer app — see "
            "docs/ad-library-access.md. To work without one, capture manually and "
            "use: adbrain category snapshot --from-file <path>"
        )
    return value


def coverage_warning(countries: list[str]) -> str | None:
    """Warn when a query is aimed where the API only returns political ads."""
    outside = [c for c in countries if c.upper() not in FULL_COVERAGE]
    if not outside:
        return None
    return (
        f"{', '.join(outside)} is outside the EU/UK, where the Ad Library API "
        f"returns only political and social-issue ads. Commercial competitors "
        f"advertising only there will not appear, however the query is written. "
        f"Capture manually instead — see docs/ad-library-access.md."
    )


def fetch(
    page_ids: list[str] | None = None,
    search_terms: str | None = None,
    countries: list[str] | None = None,
    active_status: str = "ALL",
    limit: int = 100,
    relationship: str = "direct",
    advertiser_hint: str = "",
) -> list[CompetitorAd]:
    """Query ads_archive. Returns [] rather than raising when nothing matches."""
    countries = countries or ["GB"]
    params = {
        "access_token": token(),
        "ad_reached_countries": json.dumps([c.upper() for c in countries]),
        "ad_active_status": active_status,
        "ad_type": "ALL",
        "fields": ",".join(FIELDS),
        "limit": str(limit),
    }
    if page_ids:
        params["search_page_ids"] = json.dumps(page_ids)
    elif search_terms:
        params["search_terms"] = search_terms
    else:
        raise AdLibraryError("give either page_ids or search_terms")

    url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise AdLibraryError(
            f"Ad Library API returned {exc.code}. {detail}\n"
            f"A 400 here usually means the token lacks Ad Library access "
            f"(identity confirmation incomplete) — see docs/ad-library-access.md."
        ) from exc
    except urllib.error.URLError as exc:
        raise AdLibraryError(f"could not reach the Ad Library API: {exc.reason}") from exc

    return [_to_ad(row, relationship, advertiser_hint) for row in payload.get("data", [])]


def _first(row: dict, key: str) -> str:
    value = row.get(key)
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def _to_ad(row: dict, relationship: str, advertiser_hint: str) -> CompetitorAd:
    return CompetitorAd(
        ad_id=str(row.get("id") or ""),
        advertiser=row.get("page_name") or advertiser_hint or "unknown",
        body=_first(row, "ad_creative_bodies"),
        headline=_first(row, "ad_creative_link_titles"),
        cta=_first(row, "ad_creative_link_captions"),
        link_url=row.get("ad_snapshot_url", ""),
        started_running=(row.get("ad_delivery_start_time") or "")[:10],
        platforms=row.get("publisher_platforms") or [],
        source="api",
        relationship=relationship,
    )


# ---------------------------------------------------------------------------
# manual capture
# ---------------------------------------------------------------------------

MANUAL_COLUMNS = [
    "advertiser", "headline", "body", "started_running",
    "cta", "link_url", "relationship", "angle", "hook", "offer",
]


def from_file(path: str | Path, default_relationship: str = "direct") -> list[CompetitorAd]:
    """Load a snapshot captured by hand, as CSV or JSON.

    Only `advertiser` and one of `headline`/`body` are required. `started_running`
    is worth the effort to fill in — the Ad Library UI shows it as "Started
    running on ...", and without it longevity only counts from our first capture,
    which understates every ad already live.
    """
    path = Path(path)
    if not path.is_file():
        raise AdLibraryError(f"no such file: {path}")

    if path.suffix.lower() == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows = raw.get("ads", raw) if isinstance(raw, dict) else raw
    else:
        with path.open(newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))

    ads: list[CompetitorAd] = []
    for row in rows:
        row = {str(k).strip().lower(): (v or "") for k, v in row.items()}
        advertiser = str(row.get("advertiser", "")).strip()
        body = str(row.get("body", "")).strip()
        headline = str(row.get("headline", "")).strip()
        if not advertiser or not (body or headline):
            continue
        ads.append(
            CompetitorAd(
                ad_id=str(row.get("ad_id") or "").strip() or synth_id(advertiser, body, headline),
                advertiser=advertiser,
                body=body,
                headline=headline,
                cta=str(row.get("cta", "")).strip(),
                link_url=str(row.get("link_url", "")).strip(),
                started_running=str(row.get("started_running", "")).strip()[:10],
                angle=str(row.get("angle", "")).strip(),
                hook=str(row.get("hook", "")).strip(),
                offer=str(row.get("offer", "")).strip(),
                source="manual",
                relationship=str(row.get("relationship") or default_relationship).strip(),
            )
        )
    if not ads:
        raise AdLibraryError(
            f"no usable rows in {path}. Each row needs an `advertiser` and at "
            f"least one of `headline` or `body`. Columns: {', '.join(MANUAL_COLUMNS)}"
        )
    return ads


def template_csv() -> str:
    """A blank capture sheet, for pasting Ad Library findings into."""
    return ",".join(MANUAL_COLUMNS) + "\n"
