"""Experiment memory.

This is the part that makes the system improve rather than just run fast.
Everything else gets you to a draft quicker; only this stops you re-testing an
angle that already lost.

Two representations of the same facts, written together:

  memory/experiments/<id>.md   the human view — open it and read what happened
  memory/index.jsonl           the machine view — what retrieval actually reads

The markdown is not a rendering of the JSON, and the JSON is not a parse of the
markdown; both are written from the same record by `write()`. That is the one
place they can drift, which is why it is the only place that writes either.

An experiment starts life with verdict "pending", because performance data lands
days after the ads do. `record_outcome()` is how it gets resolved, and an
experiment that never gets resolved is a question we asked and never answered —
`LEARNED.md` lists those separately so they are visible rather than forgotten.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import config

VERDICTS = ("pending", "won", "lost", "flat")
_MARK = {"won": "✅", "lost": "❌", "flat": "➖", "pending": "⏳"}

# Words too common to indicate that two angles are actually related.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "that", "this", "it", "is", "are", "was", "be", "as", "at", "by", "from",
    "we", "our", "you", "your", "they", "their", "not", "no", "than", "then",
    "should", "will", "would", "can", "more", "most", "less", "new", "ad", "ads",
    "copy", "test", "testing", "angle", "current", "set", "lift", "improve",
}


def root() -> Path:
    path = config.repo_root() / "memory"
    (path / "experiments").mkdir(parents=True, exist_ok=True)
    return path


def index_path() -> Path:
    return root() / "index.jsonl"


@dataclass
class Experiment:
    """One thing we tried and what came of it."""

    id: str
    logged_at: str
    platform: str
    # "owned" for our own tests, "external" for category observations from
    # Phase 4. Both live in one log on purpose: when the copy agent generates,
    # it should see what we have tested AND what the category is running.
    source: str = "owned"
    hypothesis: str = ""
    angle: str = ""
    campaigns: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    variables: dict = field(default_factory=dict)
    generated: list[dict] = field(default_factory=list)
    baseline: dict = field(default_factory=dict)
    verdict: str = "pending"
    finding: str = ""
    outcome: dict = field(default_factory=dict)
    notes: str = ""

    def to_json(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------

def load_all() -> list[Experiment]:
    path = index_path()
    if not path.is_file():
        return []
    out: list[Experiment] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(Experiment(**json.loads(line)))
        except (json.JSONDecodeError, TypeError):
            # A hand-edited or half-written line should not take down the log.
            continue
    return out


def get(experiment_id: str) -> Experiment | None:
    for exp in load_all():
        if exp.id == experiment_id:
            return exp
    return None


# ---------------------------------------------------------------------------
# writing
# ---------------------------------------------------------------------------

def write(exp: Experiment) -> Path:
    """Write or replace an experiment in both representations."""
    existing = [e for e in load_all() if e.id != exp.id]
    existing.append(exp)
    existing.sort(key=lambda e: e.logged_at)
    index_path().write_text(
        "\n".join(json.dumps(e.to_json(), ensure_ascii=False) for e in existing) + "\n",
        encoding="utf-8",
    )
    path = root() / "experiments" / f"{exp.id}.md"
    path.write_text(_render(exp), encoding="utf-8")
    return path


def record_outcome(
    experiment_id: str,
    verdict: str,
    finding: str = "",
    metrics: dict | None = None,
) -> Experiment:
    """Resolve an experiment once its performance data has landed."""
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {', '.join(VERDICTS)} — got {verdict!r}")
    exp = get(experiment_id)
    if exp is None:
        known = [e.id for e in load_all()][-5:]
        raise KeyError(
            f"no experiment {experiment_id!r} in the log"
            + (f" — most recent are: {', '.join(known)}" if known else "")
        )
    exp.verdict = verdict
    if finding:
        exp.finding = finding
    if metrics:
        exp.outcome = {
            "recorded_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "metrics": metrics,
        }
    write(exp)
    return exp


def from_run(run_id: str, brief: dict, candidates: list[dict], notes: str = "") -> Experiment:
    """Build an experiment record from a completed generation run."""
    hypotheses = [c["hypothesis"] for c in candidates if c.get("hypothesis")]
    angles = [c["angle"] for c in candidates if c.get("angle")]
    targets = {t["ad_id"]: t for t in brief.get("targets", [])}
    touched = [c.get("ad_id") for c in candidates if c.get("ad_id")]

    baseline = {}
    for ad_id in touched:
        t = targets.get(ad_id)
        if t:
            baseline[ad_id] = {
                "ctr": t["metrics"]["ctr"],
                "conversions": t["metrics"]["conversions"],
                "spend": t["metrics"]["spend"],
                "cpa": t["metrics"]["cpa"],
                "flagged_for": t["reasons"],
            }

    return Experiment(
        id=run_id,
        logged_at=_dt.datetime.now().isoformat(timespec="seconds"),
        platform=brief.get("platform", ""),
        source="owned",
        hypothesis=" | ".join(hypotheses),
        angle=" | ".join(angles),
        campaigns=sorted({c.get("campaign", "") for c in candidates if c.get("campaign")}),
        targets=touched,
        variables={
            "ads_replaced": len(touched),
            "lines_generated": sum(len(v) for c in candidates for v in c.get("fields", {}).values()),
            "fields": sorted({f for c in candidates for f in c.get("fields", {})}),
        },
        generated=[
            {"ad_id": c.get("ad_id"), "field": fname, "text": text}
            for c in candidates
            for fname, texts in c.get("fields", {}).items()
            for text in texts
        ],
        baseline=baseline,
        verdict="pending",
        notes=notes,
    )


# ---------------------------------------------------------------------------
# retrieval — what the brief carries into generation
# ---------------------------------------------------------------------------

def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", (text or "").lower()) if w not in _STOPWORDS}


def _relevance(exp: Experiment, platform: str, campaigns: set[str], focus: set[str]) -> float:
    score = 0.0
    # A settled result is worth more than an open question, because the whole
    # point of retrieval is to stop us re-running a test we already answered.
    score += {"lost": 3.0, "won": 2.5, "flat": 1.5, "pending": 0.5}.get(exp.verdict, 0.0)
    if exp.platform == platform:
        score += 1.5
    if campaigns and set(exp.campaigns) & campaigns:
        score += 2.0
    # Category observations are always worth surfacing — they are the only
    # signal in the log about ground we do not own.
    if exp.source == "external":
        score += 1.0
    overlap = _tokens(f"{exp.angle} {exp.hypothesis} {exp.finding}") & focus
    score += min(len(overlap), 5) * 0.6
    return score


def recall(
    platform: str,
    campaigns: list[str] | None = None,
    focus: str = "",
    limit: int = 12,
) -> list[dict]:
    """Prior results relevant to a generation run, best first.

    Settled verdicts outrank pending ones, and losses outrank wins — an angle
    that failed is more urgent to surface than one that worked, because
    re-testing it is pure waste.
    """
    experiments = load_all()
    if not experiments:
        return []
    campaign_set = {c for c in (campaigns or []) if c}
    focus_tokens = _tokens(focus)
    scored = sorted(
        experiments,
        key=lambda e: (-_relevance(e, platform, campaign_set, focus_tokens), e.logged_at),
    )
    return [
        {
            "run_id": e.id,
            "verdict": e.verdict,
            "source": e.source,
            "angle": e.angle or "(no angle recorded)",
            "finding": e.finding or ("awaiting outcome" if e.verdict == "pending" else ""),
            "hypothesis": e.hypothesis,
            "campaigns": e.campaigns,
            "logged_at": e.logged_at[:10],
        }
        for e in scored[:limit]
    ]


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def _render(exp: Experiment) -> str:
    lines = [
        f"# {exp.id}",
        "",
        f"**{_MARK.get(exp.verdict, '')} {exp.verdict}**"
        + (f" · {exp.source}" if exp.source != "owned" else "")
        + f" · {exp.platform} · logged {exp.logged_at[:10]}",
        "",
    ]
    if exp.hypothesis:
        lines += ["## hypothesis", "", exp.hypothesis, ""]
    if exp.angle:
        lines += ["## angle", "", exp.angle, ""]
    if exp.campaigns:
        lines += ["## where", "", ", ".join(exp.campaigns), ""]

    if exp.baseline:
        lines += ["## what it replaced", "",
                  "| ad | ctr | conversions | spend | cpa | flagged for |",
                  "|---|---|---|---|---|---|"]
        for ad_id, b in exp.baseline.items():
            lines.append(
                f"| {ad_id} | {b.get('ctr', 0)}% | {b.get('conversions', 0):.0f} | "
                f"${b.get('spend', 0):,.0f} | ${b.get('cpa', 0):,.0f} | "
                f"{'; '.join(b.get('flagged_for', []))} |"
            )
        lines.append("")

    if exp.variables:
        lines += ["## variables", ""]
        for key, value in exp.variables.items():
            rendered = ", ".join(map(str, value)) if isinstance(value, list) else value
            lines.append(f"- **{key}:** {rendered}")
        lines.append("")

    if exp.generated:
        lines += ["## what we shipped", ""]
        by_field: dict[str, list[str]] = {}
        for g in exp.generated:
            by_field.setdefault(g["field"], []).append(g["text"])
        for fname, texts in by_field.items():
            lines.append(f"**{fname}**")
            lines.append("")
            for text in texts:
                lines.append(f"- {text}")
            lines.append("")

    lines += ["## outcome", ""]
    if exp.verdict == "pending":
        lines += [
            "_Not yet known. Performance data lands days after the ads do._",
            "",
            "When it arrives:",
            "",
            "```bash",
            f'python3 -m adbrain outcome --experiment {exp.id} \\',
            '    --verdict won|lost|flat --finding "what we now believe, in one sentence"',
            "```",
            "",
        ]
    else:
        lines += [f"**{exp.finding or '(no finding written — add one)'}**", ""]
        metrics = exp.outcome.get("metrics") or {}
        if metrics:
            lines += ["| metric | value |", "|---|---|"]
            for key, value in metrics.items():
                lines.append(f"| {key} | {value} |")
            lines.append("")
        if exp.outcome.get("recorded_at"):
            lines += [f"_recorded {exp.outcome['recorded_at'][:10]}_", ""]

    if exp.notes:
        lines += ["## notes", "", exp.notes, ""]
    return "\n".join(lines)


def render_learned() -> str:
    """Roll the log up into the standing conclusions."""
    experiments = load_all()
    owned = [e for e in experiments if e.source == "owned"]
    external = [e for e in experiments if e.source == "external"]
    settled = [e for e in owned if e.verdict != "pending"]
    pending = [e for e in owned if e.verdict == "pending"]

    lines = [
        "# what we have learned",
        "",
        "_Generated by `adbrain learned`. Edit the experiment files, not this one._",
        "",
        f"{len(owned)} experiments run · {len(settled)} settled · {len(pending)} awaiting "
        f"outcome · {len(external)} category observations",
        "",
    ]

    if not experiments:
        lines += [
            "Nothing logged yet.",
            "",
            "The log fills as runs complete: `adbrain log --run latest` after a "
            "generation run, then `adbrain outcome` once the numbers land. Until then "
            "every angle is untested and the copy agent is generating blind.",
            "",
        ]
        return "\n".join(lines)

    for verdict, heading, blurb in (
        ("lost", "angles that lost — do not re-test these",
         "Each of these cost a test cycle. Re-proposing one is the single most "
         "expensive mistake this system exists to prevent."),
        ("won", "angles that worked — write toward these", ""),
        ("flat", "angles that made no difference",
         "No signal either way. Worth retesting only with a genuinely different execution."),
    ):
        group = [e for e in settled if e.verdict == verdict]
        if not group:
            continue
        lines += [f"## {_MARK[verdict]} {heading}", ""]
        if blurb:
            lines += [blurb, ""]
        for e in sorted(group, key=lambda x: x.logged_at, reverse=True):
            lines.append(f"- **{e.angle or e.id}** — {e.finding or 'no finding recorded'}")
            lines.append(f"    - _{e.logged_at[:10]} · {e.platform} · "
                         f"[{e.id}](experiments/{e.id}.md)_")
        lines.append("")

    if external:
        lines += ["## 🔭 what the category is doing", "",
                  "Observed, not tested. Treat as ground that is already crowded or "
                  "newly opening — not as a result.", ""]
        for e in sorted(external, key=lambda x: x.logged_at, reverse=True)[:20]:
            lines.append(f"- **{e.angle or e.id}** — {e.finding or 'no finding recorded'}")
            lines.append(f"    - _{e.logged_at[:10]} · [{e.id}](experiments/{e.id}.md)_")
        lines.append("")

    if pending:
        lines += ["## ⏳ awaiting an outcome", "",
                  "Questions we asked and have not answered. An experiment that stays "
                  "here forever taught us nothing.", ""]
        for e in sorted(pending, key=lambda x: x.logged_at):
            age = _age_days(e.logged_at)
            overdue = " ⚠ **overdue**" if age is not None and age > 21 else ""
            lines.append(
                f"- **{e.angle or e.id}** — logged {e.logged_at[:10]}"
                + (f", {age} days ago" if age is not None else "") + overdue
            )
            lines.append(f"    - `adbrain outcome --experiment {e.id} --verdict won|lost|flat "
                         f"--finding \"...\"`")
        lines.append("")

    return "\n".join(lines)


def _age_days(timestamp: str) -> int | None:
    try:
        return (_dt.datetime.now() - _dt.datetime.fromisoformat(timestamp)).days
    except ValueError:
        return None


def save_learned() -> Path:
    path = root() / "LEARNED.md"
    path.write_text(render_learned(), encoding="utf-8")
    return path
