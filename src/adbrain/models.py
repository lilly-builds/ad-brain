"""Core data types.

An `Ad` is one row of a platform export: its copy fields plus its performance.
Derived metrics (ctr, cpc, cpa, conv_rate) are computed rather than trusted from
the export, because platforms round them and the rounding matters when you are
ranking hundreds of ads against a percentile cutoff.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _safe_div(numerator: float, denominator: float) -> float:
    """Division that returns 0.0 rather than raising on an empty denominator.

    An ad with zero impressions has a CTR of zero, not an error — the
    significance gate in config/thresholds.toml is what excludes it from
    judgement, not an exception here.
    """
    return numerator / denominator if denominator else 0.0


@dataclass
class Metrics:
    impressions: float = 0.0
    clicks: float = 0.0
    conversions: float = 0.0
    spend: float = 0.0
    days_live: float = 0.0
    # Exports do not always carry a start date. When they do not we must not
    # silently treat the ad as 0 days old, because the significance gate would
    # then exclude every ad in the file. Ranking skips the age check instead
    # and the report says so.
    days_live_known: bool = True

    @property
    def ctr(self) -> float:
        """Click-through rate as a percentage."""
        return _safe_div(self.clicks, self.impressions) * 100.0

    @property
    def cpc(self) -> float:
        return _safe_div(self.spend, self.clicks)

    @property
    def cpa(self) -> float:
        """Cost per acquisition. Zero conversions yields 0.0, not infinity.

        Rules that target expensive acquisition must pair a cpa condition with a
        conversions condition, or they will silently match unconverted ads. The
        shipped `spend_no_conversions` rule handles that case separately and on
        purpose.
        """
        return _safe_div(self.spend, self.conversions)

    @property
    def conv_rate(self) -> float:
        """Conversion rate as a percentage of clicks."""
        return _safe_div(self.conversions, self.clicks) * 100.0

    def get(self, name: str) -> float:
        """Look up any metric by the name used in config/thresholds.toml."""
        if not hasattr(self, name):
            raise KeyError(
                f"unknown metric {name!r} — available: impressions, clicks, "
                f"conversions, spend, days_live, ctr, cpc, cpa, conv_rate"
            )
        return float(getattr(self, name))


@dataclass
class Ad:
    """One ad from a platform export."""

    ad_id: str
    platform: str
    campaign: str = ""
    ad_group: str = ""
    status: str = ""
    final_url: str = ""
    # field name -> the copy in it. Google RSAs carry many headlines, so every
    # field is a list even when the platform only allows one.
    fields: dict[str, list[str]] = field(default_factory=dict)
    metrics: Metrics = field(default_factory=Metrics)
    raw: dict[str, Any] = field(default_factory=dict)

    def texts(self, field_name: str) -> list[str]:
        return self.fields.get(field_name, [])

    @property
    def label(self) -> str:
        """Short human identifier for reports."""
        bits = [b for b in (self.campaign, self.ad_group) if b]
        return f"{' / '.join(bits)} [{self.ad_id}]" if bits else self.ad_id


@dataclass
class Flag:
    """Why one ad was flagged."""

    rule: str
    plain_english: str
    severity: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class Judged:
    """An ad plus the verdict the ranking pass reached about it."""

    ad: Ad
    significant: bool
    flags: list[Flag] = field(default_factory=list)
    winner_of: list[str] = field(default_factory=list)
    percentiles: dict[str, float] = field(default_factory=dict)

    @property
    def is_underperformer(self) -> bool:
        return bool(self.flags)

    @property
    def is_winner(self) -> bool:
        return bool(self.winner_of)

    @property
    def worst_severity(self) -> str:
        order = {"high": 3, "medium": 2, "low": 1}
        if not self.flags:
            return "none"
        return max(self.flags, key=lambda f: order.get(f.severity, 0)).severity
