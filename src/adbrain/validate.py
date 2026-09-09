"""The gate.

Character limits and voice rules are enforced here, in code — not asked for in a
prompt. A prompt saying "under 30 characters" is a suggestion; this module is
what actually decides.

Nothing in here truncates. Over-limit copy produces a regeneration request
carrying the overage, and the sub-agent rewrites it. Truncated copy fits the
box and says nothing, which is the failure mode this system exists to avoid.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config, platforms

# Emoji and pictographic ranges. Deliberately broad: where a brand bans emoji,
# a false positive costs one rewrite while a false negative ships to the feed.
_EMOJI = re.compile(
    "["
    "\U0001f000-\U0001faff"  # pictographs, emoticons, transport, symbols
    "☀-➿"          # misc symbols and dingbats
    "←-⇿"          # arrows
    "️"                 # variation selector-16 (emoji presentation)
    "‍"                 # zero-width joiner (compound emoji)
    "]"
)

_NUMBER = re.compile(r"\d+(?:[.,/\-]\d+)*%?")


@dataclass
class Violation:
    kind: str          # "length" | "case" | "emoji" | "banned" | "claim" | "style"
    severity: str      # "error" -> regenerate | "warn" -> human review
    message: str
    text: str = ""
    field_name: str = ""
    overage: int = 0

    @property
    def blocking(self) -> bool:
        return self.severity == "error"


@dataclass
class LineResult:
    text: str
    field_name: str
    chars: int
    limit: int
    violations: list[Violation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(v.blocking for v in self.violations)

    @property
    def warnings(self) -> list[Violation]:
        return [v for v in self.violations if not v.blocking]


# ---------------------------------------------------------------------------
# proof points
# ---------------------------------------------------------------------------

def _approved_numbers() -> set[str]:
    """Numbers that appear in an approved proof point in brand/proof.md.

    Only the rows above the "Pending verification" heading count. A claim
    sitting in Pending is explicitly not usable yet.
    """
    path = config.repo_root() / "brand" / "proof.md"
    if not path.is_file():
        return set()
    approved: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().lower().startswith("## pending"):
            break
        if line.lstrip().startswith("|"):
            approved.update(_NUMBER.findall(line))
    return approved


# ---------------------------------------------------------------------------
# individual checks
# ---------------------------------------------------------------------------

def _check_length(text: str, spec: platforms.FieldSpec) -> list[Violation]:
    over = spec.overage(text)
    if over <= 0:
        return []
    return [
        Violation(
            kind="length",
            severity="error",
            message=(
                f"{platforms.count_chars(text)} characters, limit is {spec.limit} "
                f"— {over} over. Rewrite shorter; do not trim."
            ),
            text=text,
            field_name=spec.name,
            overage=over,
        )
    ]


def _check_case(text: str, rules: dict) -> list[Violation]:
    """Enforce the brand's letter-case rule, if it has one.

    Three modes, set in config/voice.toml:
      any        no rule (the default — most brands)
      lowercase  no capitals at all outside the allow-list
      sentence   no ALL-CAPS words outside the allow-list
    """
    section = rules.get("case", {})
    mode = section.get("rule", "any")
    if mode == "any":
        return []

    stripped = text
    # Remove permitted proper nouns before looking for capitals, longest first
    # so a two-word name is consumed before either word could match alone.
    for token in sorted(section.get("allow_capitalized", []), key=len, reverse=True):
        stripped = stripped.replace(token, "")

    if mode == "lowercase":
        offenders = sorted(set(re.findall(r"\b[A-Z][\w'-]*", stripped)))
        detail = "all ad copy is lowercase"
    elif mode == "sentence":
        offenders = sorted(set(re.findall(r"\b[A-Z]{2,}\b", stripped)))
        detail = "no ALL-CAPS words"
    else:
        raise ValueError(
            f"unknown case rule {mode!r} in config/voice.toml — "
            f"use any, lowercase, or sentence"
        )

    if not offenders:
        return []
    return [
        Violation(
            kind="case",
            severity=section.get("severity", "error"),
            message=(
                f"capitalised outside the allow-list: {', '.join(offenders)}. "
                f"{section.get('plain_english') or detail}"
            ),
            text=text,
        )
    ]


def _check_emoji(text: str, rules: dict) -> list[Violation]:
    section = rules.get("emoji", {})
    found = _EMOJI.findall(text)
    if not found:
        return []
    return [
        Violation(
            kind="emoji",
            severity=section.get("severity", "error"),
            message=f"contains emoji ({''.join(found)}) — {section.get('plain_english', '')}",
            text=text,
        )
    ]


def _check_banned(text: str, rules: dict) -> list[Violation]:
    section = rules.get("banned_terms", {})
    severity = section.get("severity", "error")
    out: list[Violation] = []
    for entry in section.get("entries", []):
        match = re.search(entry["pattern"], text, flags=re.IGNORECASE)
        if match:
            out.append(
                Violation(
                    kind="banned",
                    severity=severity,
                    message=f"uses {match.group(0)!r} — {entry['reason']}",
                    text=text,
                )
            )
    return out


def _check_claims(text: str, rules: dict, approved: set[str]) -> list[Violation]:
    section = rules.get("claims", {})
    if not section:
        return []
    allowed = set(section.get("always_allowed", [])) | approved
    unverified = [n for n in _NUMBER.findall(text) if n not in allowed]
    if not unverified:
        return []
    return [
        Violation(
            kind="claim",
            severity=section.get("severity", "warn"),
            message=(
                f"unverified number(s): {', '.join(unverified)}. Every figure in "
                f"ad copy must trace to brand/proof.md — verify and add it there, "
                f"or rewrite the line without the number."
            ),
            text=text,
        )
    ]


def _check_style(text: str, field_name: str, rules: dict) -> list[Violation]:
    section = rules.get("soft_checks", {})
    severity = section.get("severity", "warn")
    out: list[Violation] = []
    for entry in section.get("entries", []):
        applies = entry.get("applies_to")
        if applies and field_name not in applies:
            continue
        if "requires_any" in entry:
            words = entry["requires_any"]
            if not any(re.search(rf"\b{re.escape(w)}\b", text, re.IGNORECASE) for w in words):
                out.append(
                    Violation(
                        kind="style",
                        severity=severity,
                        message=f"{entry['name']}: {entry['reason']}",
                        text=text,
                        field_name=field_name,
                    )
                )
        if "pattern" in entry and re.search(entry["pattern"], text.strip()):
            out.append(
                Violation(
                    kind="style",
                    severity=severity,
                    message=f"{entry['name']}: {entry['reason']}",
                    text=text,
                    field_name=field_name,
                )
            )
    return out


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def check_line(text: str, platform: str, field_name: str) -> LineResult:
    """Run every check against one line of copy."""
    spec = platforms.get(platform).field(field_name)
    rules = config.voice()
    approved = _approved_numbers()

    violations: list[Violation] = []
    violations += _check_length(text, spec)
    violations += _check_case(text, rules)
    violations += _check_emoji(text, rules)
    violations += _check_banned(text, rules)
    violations += _check_claims(text, rules, approved)
    violations += _check_style(text, field_name, rules)

    for v in violations:
        v.field_name = v.field_name or field_name

    return LineResult(
        text=text,
        field_name=field_name,
        chars=platforms.count_chars(text),
        limit=spec.limit,
        violations=violations,
    )


def check_set(texts: list[str], platform: str, field_name: str) -> tuple[list[LineResult], list[Violation]]:
    """Check a group of lines for one field, plus the count rules for that field.

    Returns (per-line results, set-level violations). Set-level covers the
    things a single line cannot know about: too few headlines for a valid RSA,
    too many, or duplicates that waste an ad slot.
    """
    spec = platforms.get(platform).field(field_name)
    results = [check_line(t, platform, field_name) for t in texts]
    passing = [r for r in results if r.ok]
    set_level: list[Violation] = []

    if len(passing) < spec.min_count:
        set_level.append(
            Violation(
                kind="count",
                severity="error",
                message=(
                    f"{len(passing)} valid {field_name}(s) but {platform} requires at "
                    f"least {spec.min_count}. Generate "
                    f"{spec.min_count - len(passing)} more."
                ),
                field_name=field_name,
            )
        )
    if len(passing) > spec.max_count:
        set_level.append(
            Violation(
                kind="count",
                severity="error",
                message=(
                    f"{len(passing)} valid {field_name}(s) but {platform} allows at "
                    f"most {spec.max_count}. Drop the weakest "
                    f"{len(passing) - spec.max_count}."
                ),
                field_name=field_name,
            )
        )

    seen: dict[str, int] = {}
    for r in passing:
        key = r.text.strip().lower()
        seen[key] = seen.get(key, 0) + 1
    for text, n in seen.items():
        if n > 1:
            set_level.append(
                Violation(
                    kind="count",
                    severity="error",
                    message=f"{text!r} appears {n} times — duplicates waste an ad slot",
                    field_name=field_name,
                )
            )

    return results, set_level
