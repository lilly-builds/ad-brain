"""Underperformer detection.

The rules live in `config/thresholds.toml` in plain language and every flag
carries the sentence that explains it, which is what gets printed in the report.
Changing what counts as an underperformer is a config edit, never a code change.

The significance gate matters more than the rules. Without it you flag ads that
have not had a fair chance to run, generate replacements for them, and destroy
the only thing that was actually accumulating — impressions on a fair test.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass

from . import config
from .models import Ad, Flag, Judged

_OPS = {
    "<": operator.lt, "<=": operator.le, ">": operator.gt,
    ">=": operator.ge, "==": operator.eq, "!=": operator.ne,
}


def _percentile(value: float, population: list[float]) -> float:
    """Where `value` sits in `population`, 0-100.

    Uses the share of the population strictly below the value, which is the
    reading a marketer expects from "bottom 25%".
    """
    if not population:
        return 50.0
    below = sum(1 for v in population if v < value)
    return below / len(population) * 100.0


@dataclass
class Cohort:
    """The comparison set: every ad that cleared the significance gate."""

    means: dict[str, float]
    populations: dict[str, list[float]]
    size: int
    age_unknown: bool = False


_METRICS = ["impressions", "clicks", "conversions", "spend", "ctr", "cpc", "cpa", "conv_rate", "days_live"]


def build_cohort(ads: list[Ad], significant: list[bool]) -> Cohort:
    pool = [a for a, sig in zip(ads, significant) if sig]
    populations = {m: [a.metrics.get(m) for a in pool] for m in _METRICS}
    means = {
        m: (sum(values) / len(values) if values else 0.0)
        for m, values in populations.items()
    }
    return Cohort(
        means=means,
        populations=populations,
        size=len(pool),
        age_unknown=any(not a.metrics.days_live_known for a in ads),
    )


def _is_significant(ad: Ad, gate: dict) -> bool:
    if ad.metrics.impressions < float(gate.get("min_impressions", 0)):
        return False
    # If the export carried no start date we cannot judge age. Skipping the
    # check is right; treating the ad as zero days old would exclude the
    # entire file.
    if ad.metrics.days_live_known:
        if ad.metrics.days_live < float(gate.get("min_days_live", 0)):
            return False
    return True


def _evaluate(ad: Ad, condition: dict, cohort: Cohort) -> tuple[bool, str]:
    """Test one condition. Returns (matched, human-readable evidence)."""
    metric = condition["metric"]
    mode = condition.get("compare", "absolute")
    op = _OPS[condition["operator"]]
    target = float(condition["value"])
    actual = ad.metrics.get(metric)

    if mode == "absolute":
        observed = actual
        rendered = f"{metric} is {observed:,.2f}"
    elif mode == "percentile":
        observed = _percentile(actual, cohort.populations.get(metric, []))
        rendered = f"{metric} sits at the {observed:.0f}th percentile ({actual:,.2f})"
    elif mode == "ratio_to_account_mean":
        mean = cohort.means.get(metric, 0.0)
        observed = actual / mean if mean else 0.0
        rendered = (
            f"{metric} is {observed:.2f}x the account average "
            f"({actual:,.2f} vs {mean:,.2f})"
        )
    else:
        raise ValueError(
            f"unknown compare mode {mode!r} in config/thresholds.toml — "
            f"use absolute, percentile, or ratio_to_account_mean"
        )

    return op(observed, target), rendered


def _match_rule(ad: Ad, rule: dict, cohort: Cohort) -> tuple[bool, list[str]]:
    """All conditions in a rule must match."""
    evidence: list[str] = []
    for condition in rule.get("conditions", []):
        matched, rendered = _evaluate(ad, condition, cohort)
        if not matched:
            return False, []
        evidence.append(rendered)
    return bool(rule.get("conditions")), evidence


def judge(ads: list[Ad], thresholds: dict | None = None) -> tuple[list[Judged], Cohort]:
    """Rank every ad and decide which need iteration.

    Winners are checked first and are never flagged — an ad in the top decile
    that also happens to be old should not be sent for rewriting.
    """
    cfg = thresholds or config.thresholds()
    gate = cfg.get("significance", {})

    significant = [_is_significant(a, gate) for a in ads]
    cohort = build_cohort(ads, significant)

    judged: list[Judged] = []
    for ad, sig in zip(ads, significant):
        record = Judged(ad=ad, significant=sig)
        record.percentiles = {
            m: _percentile(ad.metrics.get(m), cohort.populations.get(m, []))
            for m in ("ctr", "conv_rate", "cpa", "spend")
        }
        if sig:
            for winner in cfg.get("winners", []):
                matched, _ = _match_rule(ad, winner, cohort)
                if matched:
                    record.winner_of.append(winner["name"])
            if not record.winner_of:
                for rule in cfg.get("rules", []):
                    matched, evidence = _match_rule(ad, rule, cohort)
                    if matched:
                        record.flags.append(
                            Flag(
                                rule=rule["name"],
                                plain_english=rule["plain_english"],
                                severity=rule.get("severity", "medium"),
                                evidence=evidence,
                            )
                        )
        judged.append(record)

    order = {"high": 3, "medium": 2, "low": 1, "none": 0}
    judged.sort(key=lambda j: (-order.get(j.worst_severity, 0), -j.ad.metrics.spend))
    return judged, cohort


def summarise(judged: list[Judged], cohort: Cohort) -> dict:
    flagged = [j for j in judged if j.is_underperformer]
    winners = [j for j in judged if j.is_winner]
    return {
        "total_ads": len(judged),
        "significant": cohort.size,
        "below_significance": len(judged) - cohort.size,
        "flagged": len(flagged),
        "winners": len(winners),
        "wasted_spend": round(sum(j.ad.metrics.spend for j in flagged), 2),
        "account_mean_ctr": round(cohort.means.get("ctr", 0.0), 2),
        "age_unknown": cohort.age_unknown,
    }
