"""Category monitoring.

Public ad libraries publish *creative*, never performance. There is no public
CTR, no public spend, no public conversion rate. So the signal we use is
**longevity**: an ad that has run continuously for months is almost certainly
working, because nobody keeps paying to serve a loser. An ad that just died
after a long run is the higher-signal event — something changed.

That means the valuable artefact is not a snapshot, it is the **diff between
snapshots**. This module is deliberately agnostic about where a snapshot came
from (the Ad Library API, a manual capture, a third-party export), because API
coverage varies by region and by ad type — see docs/ad-library-access.md. The
analysis works the same either way, and a source that changes should not
invalidate the history.

Longevity is a proxy and it is stated as one. A long-running ad might be a
neglected evergreen rather than a winner. The digest reports days-running as an
observation with its uncertainty attached, never as "this ad performs well".
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import config, memory

# An ad that has run this long without being switched off is being paid for on
# purpose. Below this, it may simply not have been reviewed yet.
PROVEN_DAYS = 90
ESTABLISHED_DAYS = 30


def snapshots_dir() -> Path:
    path = config.repo_root() / "memory" / "category" / "snapshots"
    path.mkdir(parents=True, exist_ok=True)
    return path


def digests_dir() -> Path:
    path = config.repo_root() / "memory" / "category" / "digests"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class CompetitorAd:
    """One creative observed running for a competitor."""

    ad_id: str
    advertiser: str
    body: str = ""
    headline: str = ""
    cta: str = ""
    link_url: str = ""
    started_running: str = ""      # as reported by the library, if known
    first_seen: str = ""           # first time WE observed it
    last_seen: str = ""
    platforms: list[str] = field(default_factory=list)
    # Classification, filled in by the category-scout agent, not by code.
    angle: str = ""
    hook: str = ""
    offer: str = ""
    source: str = "manual"
    relationship: str = "direct"   # direct | adjacent

    def days_running(self, as_of: _dt.date | None = None) -> int | None:
        """How long this ad has been live, if we can tell."""
        as_of = as_of or _dt.date.today()
        start = _parse_date(self.started_running) or _parse_date(self.first_seen)
        if not start:
            return None
        end = _parse_date(self.last_seen) or as_of
        return max((end - start).days, 0)

    @property
    def confidence(self) -> str:
        """How much weight the longevity signal carries for this ad."""
        days = self.days_running()
        if days is None:
            return "unknown"
        if days >= PROVEN_DAYS:
            return "proven"
        if days >= ESTABLISHED_DAYS:
            return "established"
        return "new"


def _parse_date(value: str) -> _dt.date | None:
    text = (value or "").strip()[:10]
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return _dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def synth_id(advertiser: str, body: str, headline: str) -> str:
    """Stable id for an ad the source did not give one for.

    Hashing the creative text means the same ad captured twice matches itself
    across snapshots, which is what makes longevity tracking work at all when
    the source has no ad id (a manual capture, typically).
    """
    material = f"{advertiser}|{_normalise(body)}|{_normalise(headline)}"
    return "syn-" + hashlib.sha1(material.encode("utf-8")).hexdigest()[:12]


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


# ---------------------------------------------------------------------------
# snapshots
# ---------------------------------------------------------------------------

def save_snapshot(ads: list[CompetitorAd], captured_at: str | None = None) -> Path:
    """Write a snapshot, carrying `first_seen` forward from earlier ones.

    Carrying first_seen forward is what turns a series of point-in-time captures
    into a duration. Without it every snapshot would think every ad is new.
    """
    captured_at = captured_at or _dt.date.today().isoformat()
    history = _first_seen_index()
    for ad in ads:
        ad.first_seen = history.get(ad.ad_id, ad.first_seen or captured_at)
        ad.last_seen = captured_at
    path = snapshots_dir() / f"{captured_at}.json"
    path.write_text(
        json.dumps(
            {"captured_at": captured_at, "ads": [asdict(a) for a in ads]},
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def _first_seen_index() -> dict[str, str]:
    seen: dict[str, str] = {}
    for snap in list_snapshots():
        for ad in load_snapshot(snap)[1]:
            if ad.ad_id not in seen:
                seen[ad.ad_id] = ad.first_seen or snap.stem
    return seen


def list_snapshots() -> list[Path]:
    return sorted(snapshots_dir().glob("*.json"))


def load_snapshot(path: Path) -> tuple[str, list[CompetitorAd]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    ads = []
    for raw in data.get("ads", []):
        known = {k: v for k, v in raw.items() if k in CompetitorAd.__dataclass_fields__}
        ads.append(CompetitorAd(**known))
    return data.get("captured_at", path.stem), ads


# ---------------------------------------------------------------------------
# the diff — the actual product
# ---------------------------------------------------------------------------

@dataclass
class Digest:
    current_date: str
    previous_date: str | None
    launched: list[CompetitorAd] = field(default_factory=list)
    killed: list[CompetitorAd] = field(default_factory=list)
    still_running: list[CompetitorAd] = field(default_factory=list)
    new_advertisers: list[str] = field(default_factory=list)
    departed_advertisers: list[str] = field(default_factory=list)
    cadence: dict[str, int] = field(default_factory=dict)

    @property
    def is_first_run(self) -> bool:
        return self.previous_date is None


def diff(current: Path, previous: Path | None) -> Digest:
    current_date, current_ads = load_snapshot(current)
    if previous is None:
        return Digest(
            current_date=current_date,
            previous_date=None,
            launched=current_ads,
            still_running=current_ads,
            new_advertisers=sorted({a.advertiser for a in current_ads}),
            cadence=_cadence(current_ads),
        )

    previous_date, previous_ads = load_snapshot(previous)
    current_by_id = {a.ad_id: a for a in current_ads}
    previous_by_id = {a.ad_id: a for a in previous_ads}

    launched = [a for i, a in current_by_id.items() if i not in previous_by_id]
    # An ad present last time and absent now has been switched off. When it ran
    # a long time first, that is the strongest single signal available here:
    # something that was working has been retired or replaced.
    killed = [a for i, a in previous_by_id.items() if i not in current_by_id]
    survived = [a for i, a in current_by_id.items() if i in previous_by_id]

    current_advertisers = {a.advertiser for a in current_ads}
    previous_advertisers = {a.advertiser for a in previous_ads}

    return Digest(
        current_date=current_date,
        previous_date=previous_date,
        launched=sorted(launched, key=lambda a: a.advertiser),
        killed=sorted(killed, key=lambda a: -(a.days_running() or 0)),
        still_running=sorted(survived, key=lambda a: -(a.days_running() or 0)),
        new_advertisers=sorted(current_advertisers - previous_advertisers),
        departed_advertisers=sorted(previous_advertisers - current_advertisers),
        cadence=_cadence(current_ads),
    )


def _cadence(ads: list[CompetitorAd]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ad in ads:
        counts[ad.advertiser] = counts.get(ad.advertiser, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def render_digest(d: Digest) -> str:
    lines = [
        f"# category digest — {d.current_date}",
        "",
    ]
    if d.is_first_run:
        lines += [
            "**First capture.** There is nothing to compare against yet, so this is a "
            "baseline rather than a digest. The next capture is where the value starts: "
            "what launched, what got killed, and who arrived.",
            "",
        ]
    else:
        lines += [f"_changes since {d.previous_date}_", ""]
        lines += [
            f"**{len(d.launched)}** new creatives · **{len(d.killed)}** switched off · "
            f"**{len(d.still_running)}** still running",
            "",
        ]

    if d.new_advertisers and not d.is_first_run:
        lines += ["## new in the category", "",
                  "Advertisers running ads now that were not last time.", ""]
        for name in d.new_advertisers:
            lines.append(f"- **{name}**")
        lines.append("")

    if d.departed_advertisers:
        lines += ["## stopped advertising", ""]
        for name in d.departed_advertisers:
            lines.append(f"- **{name}** — no active creative observed this run")
        lines.append("")

    if d.killed:
        lines += [
            "## switched off since last run",
            "",
            "Longest-running first. An ad that ran for months and then stopped is the "
            "strongest signal available here — something that was being paid for has "
            "been retired or replaced.",
            "",
        ]
        for ad in d.killed:
            days = ad.days_running()
            span = f"ran ~{days} days" if days is not None else "run length unknown"
            lines.append(f"- **{ad.advertiser}** — {span}"
                         + (f" · {ad.angle}" if ad.angle else ""))
            if ad.headline or ad.body:
                lines.append(f"    - {(ad.headline or ad.body)[:160]}")
        lines.append("")

    if d.launched:
        heading = "## running at first capture" if d.is_first_run else "## launched since last run"
        lines += [heading, ""]
        by_advertiser: dict[str, list[CompetitorAd]] = {}
        for ad in d.launched:
            by_advertiser.setdefault(ad.advertiser, []).append(ad)
        for advertiser, ads in by_advertiser.items():
            lines.append(f"**{advertiser}** ({ads[0].relationship}) — {len(ads)} creative(s)")
            lines.append("")
            for ad in ads[:8]:
                bits = [b for b in (ad.angle, ad.hook, ad.offer) if b]
                lines.append(f"- {(ad.headline or ad.body)[:180]}")
                if bits:
                    lines.append(f"    - _{' · '.join(bits)}_")
            lines.append("")

    proven = [a for a in d.still_running if a.confidence == "proven"]
    if proven:
        lines += [
            "## proven creative — running over 90 days",
            "",
            "Longevity is a **proxy, not a measurement**. Nobody pays to keep a loser "
            "live, so these are probably working — but a neglected evergreen looks "
            "identical from the outside. Treat as a strong hint, not a result.",
            "",
        ]
        for ad in proven[:15]:
            lines.append(f"- **{ad.advertiser}** · ~{ad.days_running()} days — "
                         f"{(ad.headline or ad.body)[:140]}")
            if ad.angle:
                lines.append(f"    - _{ad.angle}_")
        lines.append("")

    if d.cadence:
        lines += ["## refresh cadence", "",
                  "How many distinct creatives each advertiser has live now. A rising "
                  "count means they are testing harder.", "",
                  "| advertiser | live creatives |", "|---|---|"]
        for advertiser, count in d.cadence.items():
            lines.append(f"| {advertiser} | {count} |")
        lines.append("")

    lines += [
        "---",
        "",
        "## what to do with this",
        "",
        "1. Angles appearing across several advertisers are **crowded ground** — "
        "entering there means competing on execution alone.",
        "2. Angles that just got killed after a long run are worth understanding "
        "before we adopt anything similar.",
        "3. Anything genuinely new in the category is the reason this workflow "
        "exists — our own experiment log can only ever learn to beat our own past.",
        "",
        "Observations worth carrying into generation get logged with "
        "`adbrain category log`, which writes them into the same experiment log as "
        "our own tests, tagged `external`.",
        "",
    ]
    return "\n".join(lines)


def save_digest(d: Digest) -> Path:
    path = digests_dir() / f"{d.current_date}.md"
    path.write_text(render_digest(d), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# feeding the experiment log
# ---------------------------------------------------------------------------

def log_observation(angle: str, finding: str, advertisers: list[str], when: str = "") -> memory.Experiment:
    """Record a category observation in the shared experiment log.

    Tagged `external` so the copy agent can tell the difference between "we
    tested this" and "they are running this". Both belong in one log: when
    generating, you want to see what has already lost AND what ground is
    already crowded.
    """
    when = when or _dt.date.today().isoformat()
    exp = memory.Experiment(
        id=f"category-{when}-{hashlib.sha1(angle.encode()).hexdigest()[:6]}",
        logged_at=_dt.datetime.now().isoformat(timespec="seconds"),
        platform="meta",
        source="external",
        angle=angle,
        finding=finding,
        # Observed, never tested — so it is settled by definition. Leaving it
        # "pending" would put it in the awaiting-outcome list forever.
        verdict="flat",
        campaigns=advertisers,
        notes="Observed in the category. Not a test result — longevity is a proxy.",
    )
    memory.write(exp)
    memory.save_learned()
    return exp
