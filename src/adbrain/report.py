"""The human-readable diff.

The bulk CSV is for the platform. This is for the person deciding whether to
upload it. It answers, per ad: what was running, why we flagged it, what
replaced it, and how much room each new line left against the limit.
"""

from __future__ import annotations

import datetime as _dt

from . import platforms


def render(brief: dict, candidates: list[dict], validation: dict) -> str:
    spec = platforms.get(brief["platform"])
    targets = {t["ad_id"]: t for t in brief["targets"]}
    warnings = validation.get("warnings", [])

    lines = [
        f"# what changed — {brief['platform_label']}",
        "",
        f"_generated {_dt.datetime.now():%Y-%m-%d %H:%M}_",
        "",
        f"**{len(candidates)}** replacement ads for **{len(targets)}** flagged originals. "
        f"Every line below passed the character limit and voice checks.",
        "",
        "> Uploads are set to **paused**. Nothing goes live until you enable it.",
        "",
    ]

    if warnings:
        lines += [
            f"## {len(warnings)} things to look at before uploading",
            "",
            "These passed, but a human should confirm them.",
            "",
        ]
        for w in warnings:
            lines.append(f"- `{w.get('field_name', '')}` — {w['message']}")
            if w.get("text"):
                lines.append(f"    - in: {w['text']!r}")
        lines.append("")

    for c in candidates:
        target = targets.get(c.get("ad_id"), {})
        lines += [
            "---",
            "",
            f"## {c.get('ad_id', 'new ad')} — {c.get('campaign', '')} / {c.get('ad_group', '')}",
            "",
        ]
        if target:
            m = target["metrics"]
            lines += [
                f"**why it was flagged:** " + "; ".join(target["reasons"]),
                "",
                f"{m['impressions']:,.0f} impressions · {m['ctr']}% ctr · "
                f"{m['conversions']:.0f} conversions · ${m['spend']:,.0f} spent",
                "",
            ]
        if c.get("hypothesis"):
            lines += [f"**hypothesis:** {c['hypothesis']}", ""]
        if c.get("angle"):
            lines += [f"**angle:** {c['angle']}", ""]

        for field_name, texts in c["fields"].items():
            if field_name not in spec.fields:
                continue
            limit = spec.field(field_name).limit
            old = target.get("current", {}).get(field_name, [])
            lines += [f"### {field_name} · limit {limit}", "", "| | copy | chars |", "|---|---|---|"]
            for text in old:
                lines.append(f"| was | {text} | {platforms.count_chars(text)} |")
            for text in texts:
                n = platforms.count_chars(text)
                room = limit - n
                lines.append(f"| **now** | **{text}** | {n} _({room} spare)_ |")
            lines.append("")

    lines += [
        "---",
        "",
        "## next",
        "",
        "1. Read the replacements above. Kill anything that does not sound like us.",
        "2. Upload `bulk-upload.csv` — it imports paused.",
        "3. Run `adbrain log --run latest` to record what we are testing and why.",
        "4. In 7–14 days, run `adbrain outcome` to record how it went. That is what "
        "makes the next run smarter.",
        "",
    ]
    return "\n".join(lines)
