"""Generation brief.

The brief is what the two copy sub-agents actually read. It carries four things
they need and nothing else: which ads are being replaced and why, what is
currently winning, what we have already learned, and the exact character budget
per field.

It is written as markdown on purpose — the sub-agents read it, and so can Lilly.
"""

from __future__ import annotations

import datetime as _dt

from . import memory, platforms
from .models import Judged
from .rank import Cohort


def build(judged: list[Judged], cohort: Cohort, platform: str, summary: dict) -> tuple[dict, str]:
    spec = platforms.get(platform)
    flagged = [j for j in judged if j.is_underperformer]
    winners = [j for j in judged if j.is_winner]
    prior = memory.recall(platform, [j.ad.campaign for j in flagged])

    payload = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "platform": platform,
        "platform_label": spec.label,
        "summary": summary,
        "budgets": {
            name: {"limit": f.limit, "min": f.min_count, "max": f.max_count}
            for name, f in spec.fields.items()
        },
        "targets": [
            {
                "ad_id": j.ad.ad_id,
                "campaign": j.ad.campaign,
                "ad_group": j.ad.ad_group,
                "severity": j.worst_severity,
                "reasons": [f.plain_english for f in j.flags],
                "evidence": [e for f in j.flags for e in f.evidence],
                "current": {k: v for k, v in j.ad.fields.items()},
                "metrics": {
                    "impressions": j.ad.metrics.impressions,
                    "clicks": j.ad.metrics.clicks,
                    "ctr": round(j.ad.metrics.ctr, 2),
                    "conversions": j.ad.metrics.conversions,
                    "spend": j.ad.metrics.spend,
                    "cpa": round(j.ad.metrics.cpa, 2),
                    "days_live": j.ad.metrics.days_live,
                },
            }
            for j in flagged
        ],
        "winners": [
            {
                "ad_id": j.ad.ad_id,
                "campaign": j.ad.campaign,
                "ctr": round(j.ad.metrics.ctr, 2),
                "conversions": j.ad.metrics.conversions,
                "won_by": j.winner_of,
                "current": {k: v for k, v in j.ad.fields.items()},
            }
            for j in winners
        ],
        "prior_learnings": prior,
    }
    return payload, _render(payload)


def _render(p: dict) -> str:
    s = p["summary"]
    lines: list[str] = [
        f"# generation brief — {p['platform_label']}",
        "",
        f"_{p['generated_at']}_",
        "",
        "## the state of the account",
        "",
        f"- **{s['total_ads']}** ads in the export, **{s['significant']}** with enough "
        f"data to judge ({s['below_significance']} still proving themselves)",
        f"- **{s['flagged']}** flagged for iteration, carrying **${s['wasted_spend']:,.0f}** in spend",
        f"- **{s['winners']}** performing well enough to learn from",
        f"- account average click-through rate: **{s['account_mean_ctr']}%**",
    ]
    if s.get("age_unknown"):
        lines.append(
            "- ⚠ this export carried no start dates, so the minimum-age part of "
            "the significance gate was skipped"
        )

    lines += ["", "## character budget — enforced, not suggested", "",
              "| field | limit | how many |", "|---|---|---|"]
    for name, b in p["budgets"].items():
        count = f"{b['min']}–{b['max']}" if b["max"] != b["min"] else str(b["max"])
        lines.append(f"| {name} | {b['limit']} chars | {count} |")
    lines += [
        "",
        "Anything over the limit is rejected and sent back, never trimmed. Write to "
        "roughly 90% of the budget so the line has room to be edited.",
    ]

    if p["prior_learnings"]:
        lines += ["", "## what we have already learned", "",
                  "Do not re-propose an angle listed as lost.", ""]
        for item in p["prior_learnings"]:
            verdict = item.get("verdict", "pending")
            mark = {"won": "✅", "lost": "❌", "flat": "➖"}.get(verdict, "⏳")
            lines.append(
                f"- {mark} **{item.get('angle', 'unknown angle')}** — {item.get('finding', 'no finding recorded yet')}"
                + (f" _(run {item['run_id']})_" if item.get("run_id") else "")
            )
    else:
        lines += ["", "## what we have already learned", "",
                  "_Nothing logged yet. This is the first run, so every angle is untested. "
                  "After this run completes, `adbrain log` records the hypothesis and "
                  "future briefs will carry it._"]

    if p["winners"]:
        lines += ["", "## what is working — write in this direction", ""]
        for w in p["winners"][:6]:
            heads = w["current"].get("headline") or w["current"].get("primary_text") or []
            lines.append(f"- **{w['ctr']}% ctr**, {w['conversions']:.0f} conversions — {w['campaign']}")
            for h in heads[:3]:
                lines.append(f"    - {h!r}")

    lines += ["", "## what to replace", ""]
    for t in p["targets"]:
        lines += [
            f"### {t['ad_id']} — {t['campaign']} / {t['ad_group']}  `{t['severity']}`",
            "",
            f"{t['metrics']['impressions']:,.0f} impressions · {t['metrics']['ctr']}% ctr · "
            f"{t['metrics']['conversions']:.0f} conversions · ${t['metrics']['spend']:,.0f} spent · "
            f"{t['metrics']['days_live']:.0f} days live",
            "",
            "**flagged because:**",
        ]
        for reason in t["reasons"]:
            lines.append(f"- {reason}")
        lines.append("")
        lines.append("**currently running:**")
        lines.append("")
        for fname, texts in t["current"].items():
            for text in texts:
                lines.append(f"- `{fname}` — {text}")
        lines.append("")

    lines += [
        "---",
        "",
        "## how to use this",
        "",
        "1. Invoke the `ad-creative` skill for angle selection and the creative-type menu.",
        "2. Dispatch `headline-writer` and `description-writer` separately — never one prompt.",
        "3. Write candidates to `candidates.json` in this run directory.",
        "4. Run `adbrain validate --run latest`. Fix what it rejects. Repeat until clean.",
        "",
        "Every claim must already exist in `brand/proof.md`. If a line needs a number "
        "that is not there, rewrite the line — do not add the number.",
        "",
    ]
    return "\n".join(lines)
