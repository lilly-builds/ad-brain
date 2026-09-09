"""Platform export parsers.

Column names drift between export types, report versions, and locales, so
parsing is alias-driven rather than positional: we normalise every header and
look it up in a list of known spellings. An unrecognised column is kept in
`Ad.raw` rather than dropped, so nothing is lost if a header changes.

If a real export does not parse cleanly, add its spelling to the alias lists
below — that is the intended maintenance path, not a new parser.
"""

from __future__ import annotations

import csv
import datetime as _dt
import re
from pathlib import Path

from .models import Ad, Metrics

# --- header aliases ---------------------------------------------------------

_ALIASES: dict[str, list[str]] = {
    "ad_id": ["ad id", "adid", "ad_id", "ad name", "ad", "creative id"],
    "campaign": ["campaign", "campaign name"],
    "ad_group": ["ad group", "ad group name", "ad set name", "adset name", "ad set"],
    "status": ["ad state", "status", "ad status", "delivery", "delivery status"],
    "final_url": ["final url", "website url", "link url", "destination url", "url"],
    "impressions": ["impressions", "impr.", "impr", "reach"],
    "clicks": ["clicks", "link clicks", "clicks (all)", "clicks all"],
    "conversions": ["conversions", "conv.", "results", "leads", "conversion"],
    "spend": ["cost", "spend", "amount spent", "amount spent (usd)", "cost (usd)"],
    "days_live": ["days live", "days running", "age (days)"],
    "start_date": ["start date", "reporting starts", "ad delivery start", "created"],
    "end_date": ["end date", "reporting ends", "ad delivery end"],
}

# Copy fields, per platform, matched by regex so numbered columns
# ("Headline 3") collapse into one list.
_COPY_PATTERNS: dict[str, dict[str, str]] = {
    "google_rsa": {
        "headline": r"^headline\s*\d*$",
        "description": r"^description\s*\d*$",
        "path1": r"^path\s*1$",
        "path2": r"^path\s*2$",
    },
    "google_pmax": {
        "headline": r"^headline\s*\d*$",
        "long_headline": r"^long headline\s*\d*$",
        "description": r"^description\s*\d*$",
        "business_name": r"^business name$",
    },
    "meta": {
        "primary_text": r"^(primary text|body|ad body|message)\s*\d*$",
        "headline": r"^(headline|title)\s*\d*$",
        "description": r"^(description|link description)\s*\d*$",
    },
}


def _norm(header: str) -> str:
    return re.sub(r"\s+", " ", header.replace("﻿", "").strip().lower())


def _to_float(value: str) -> float:
    """Parse a number out of an export cell.

    Exports carry currency symbols, thousands separators, percent signs, and
    locale decimal commas. Anything unparseable becomes 0.0 rather than raising —
    one malformed cell should not abort a 400-row file.
    """
    if value is None:
        return 0.0
    text = str(value).strip()
    if not text or text in {"--", "-", "—", "n/a", "N/A"}:
        return 0.0
    text = re.sub(r"[^\d.,\-]", "", text)
    if not text:
        return 0.0
    # "1.234,56" is European; "1,234.56" is US.
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".") if text.rindex(",") > text.rindex(".") else text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".") if len(text.split(",")[-1]) == 2 else text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _parse_date(value: str) -> _dt.date | None:
    text = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%b %d, %Y", "%d %b %Y"):
        try:
            return _dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _build_index(headers: list[str]) -> dict[str, str]:
    """Map our canonical field names onto this file's actual column names."""
    index: dict[str, str] = {}
    normalised = {_norm(h): h for h in headers}
    for canonical, spellings in _ALIASES.items():
        for spelling in spellings:
            if spelling in normalised:
                index[canonical] = normalised[spelling]
                break
    return index


def read(path: str | Path, platform: str, today: _dt.date | None = None) -> list[Ad]:
    """Parse a platform export into Ads.

    `platform` selects which copy-field patterns apply; performance columns are
    shared across platforms.
    """
    path = Path(path)
    if platform not in _COPY_PATTERNS:
        raise KeyError(
            f"no parser for platform {platform!r} — parsers exist for: "
            f"{', '.join(sorted(_COPY_PATTERNS))}. Character limits are "
            f"registered for more platforms than have parsers; add the column "
            f"patterns to ingest._COPY_PATTERNS to extend."
        )
    today = today or _dt.date.today()
    patterns = _COPY_PATTERNS[platform]

    with path.open(newline="", encoding="utf-8-sig") as fh:
        # Google Ads reports prepend title/date rows before the real header.
        # Find the first line that looks like a header for this platform.
        sample = fh.read(8192)
        fh.seek(0)
        reader = csv.reader(fh)
        rows = list(reader)

    header_row = 0
    for i, row in enumerate(rows[:10]):
        cells = {_norm(c) for c in row}
        if cells & set(_ALIASES["impressions"]) or any(
            re.match(p, c) for c in cells for p in patterns.values()
        ):
            header_row = i
            break

    headers = [h for h in rows[header_row]]
    index = _build_index(headers)
    ads: list[Ad] = []

    for n, row in enumerate(rows[header_row + 1:], start=1):
        if not any(cell.strip() for cell in row):
            continue
        record = dict(zip(headers, row))
        # Google reports end with a "Total" summary row; it is not an ad.
        first = _norm(row[0]) if row else ""
        if first.startswith("total"):
            continue

        fields: dict[str, list[str]] = {}
        for field_name, pattern in patterns.items():
            texts = [
                value.strip()
                for header, value in record.items()
                if re.match(pattern, _norm(header)) and value and value.strip()
            ]
            if texts:
                fields[field_name] = texts

        if not fields:
            continue  # a row with no copy is not an ad we can iterate on

        days, known = _days_live(record, index, today)
        metrics = Metrics(
            impressions=_to_float(record.get(index.get("impressions", ""), "")),
            clicks=_to_float(record.get(index.get("clicks", ""), "")),
            conversions=_to_float(record.get(index.get("conversions", ""), "")),
            spend=_to_float(record.get(index.get("spend", ""), "")),
            days_live=days,
            days_live_known=known,
        )

        ads.append(
            Ad(
                ad_id=(record.get(index.get("ad_id", ""), "") or f"row-{n}").strip(),
                platform=platform,
                campaign=record.get(index.get("campaign", ""), "").strip(),
                ad_group=record.get(index.get("ad_group", ""), "").strip(),
                status=record.get(index.get("status", ""), "").strip(),
                final_url=record.get(index.get("final_url", ""), "").strip(),
                fields=fields,
                metrics=metrics,
                raw=record,
            )
        )

    return ads


def _days_live(record: dict, index: dict, today: _dt.date) -> tuple[float, bool]:
    """Work out how long an ad has been running, and whether we actually know."""
    if "days_live" in index:
        raw = record.get(index["days_live"], "")
        if str(raw).strip():
            return _to_float(raw), True
    if "start_date" in index:
        start = _parse_date(record.get(index["start_date"], ""))
        if start:
            end = _parse_date(record.get(index.get("end_date", ""), "")) or today
            return float(max((end - start).days, 0)), True
    return 0.0, False
