"""Bulk-upload writers.

One writer per platform, because this is the part that genuinely is
platform-specific — the column names are dictated by the tool that ingests the
file (Google Ads Editor, Meta Ads Manager), not by us.

Every row written here has already passed validation. These functions do not
check limits; `validate` is the gate and it runs first.
"""

from __future__ import annotations

import csv
from pathlib import Path

from . import platforms


def _rows_google_rsa(candidates: list[dict]) -> tuple[list[str], list[dict]]:
    spec = platforms.get("google_rsa")
    max_h = spec.field("headline").max_count
    max_d = spec.field("description").max_count
    columns = (
        ["Campaign", "Ad group", "Ad status", "Ad type"]
        + [f"Headline {i}" for i in range(1, max_h + 1)]
        + [f"Description {i}" for i in range(1, max_d + 1)]
        + ["Path 1", "Path 2", "Final URL", "Label"]
    )
    rows = []
    for c in candidates:
        fields = c["fields"]
        row = {
            "Campaign": c.get("campaign", ""),
            "Ad group": c.get("ad_group", ""),
            # Paused on upload, always. A generated ad going live unreviewed is
            # the one failure this system must not have.
            "Ad status": "Paused",
            "Ad type": "Responsive search ad",
            "Path 1": (fields.get("path1") or [""])[0],
            "Path 2": (fields.get("path2") or [""])[0],
            "Final URL": c.get("final_url", ""),
            "Label": f"adbrain:{c.get('run_id', '')}",
        }
        for i, text in enumerate(fields.get("headline", [])[:max_h], start=1):
            row[f"Headline {i}"] = text
        for i, text in enumerate(fields.get("description", [])[:max_d], start=1):
            row[f"Description {i}"] = text
        rows.append(row)
    return columns, rows


def _rows_meta(candidates: list[dict]) -> tuple[list[str], list[dict]]:
    columns = [
        "Campaign Name", "Ad Set Name", "Ad Name", "Ad Status",
        "Primary Text", "Headline", "Link Description", "Link URL", "Label",
    ]
    rows = []
    for c in candidates:
        fields = c["fields"]
        # Meta takes one text per ad, so a 5x5x5 set becomes one row per
        # combination the generator chose to ship — we do not cross-product
        # here, because that decision belongs to the person reviewing.
        primaries = fields.get("primary_text", [""])
        headlines = fields.get("headline", [""])
        descriptions = fields.get("description", [""]) or [""]
        for i in range(max(len(primaries), len(headlines))):
            rows.append({
                "Campaign Name": c.get("campaign", ""),
                "Ad Set Name": c.get("ad_group", ""),
                "Ad Name": f"{c.get('ad_id', 'new')}-v{i + 1}",
                "Ad Status": "PAUSED",
                "Primary Text": primaries[i % len(primaries)],
                "Headline": headlines[i % len(headlines)],
                "Link Description": descriptions[i % len(descriptions)],
                "Link URL": c.get("final_url", ""),
                "Label": f"adbrain:{c.get('run_id', '')}",
            })
    return columns, rows


_WRITERS = {
    "google_rsa": _rows_google_rsa,
    "meta": _rows_meta,
}


def write(path: Path, platform: str, candidates: list[dict]) -> int:
    if platform not in _WRITERS:
        raise KeyError(
            f"no bulk writer for {platform!r} — writers exist for "
            f"{', '.join(sorted(_WRITERS))}"
        )
    columns, rows = _WRITERS[platform](candidates)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in columns})
    return len(rows)
