"""Platform spec registry.

Character limits are data (`config/platforms.toml`), not code. This module turns
that data into objects the validator and the CSV writers can ask questions of.
Adding a platform means adding a TOML table — no code change.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from . import config


def count_chars(text: str) -> int:
    """Count characters the way ad platforms do.

    Normalised to NFC first, so an accented character typed as base + combining
    mark counts as one character rather than two. Both Google and Meta count
    composed characters, and the difference is exactly the kind of off-by-one
    that gets an ad rejected at upload after it passed local validation.
    """
    return len(unicodedata.normalize("NFC", text))


@dataclass(frozen=True)
class FieldSpec:
    name: str
    limit: int
    min_count: int = 0
    max_count: int = 1
    hard_max: int | None = None

    def overage(self, text: str) -> int:
        """Characters over the limit. Zero or negative means it fits."""
        return count_chars(text) - self.limit


@dataclass(frozen=True)
class PlatformSpec:
    key: str
    label: str
    bulk_format: str
    fields: dict[str, FieldSpec]

    def field(self, name: str) -> FieldSpec:
        if name not in self.fields:
            raise KeyError(
                f"{self.key} has no field {name!r} — available: "
                f"{', '.join(sorted(self.fields))}"
            )
        return self.fields[name]

    @property
    def copy_fields(self) -> list[str]:
        """Fields that hold generated copy, in declaration order."""
        return list(self.fields)


def get(key: str) -> PlatformSpec:
    data = config.platforms()
    if key not in data:
        raise KeyError(
            f"unknown platform {key!r} — configured platforms: "
            f"{', '.join(sorted(data))}"
        )
    table = data[key]
    fields = {
        name: FieldSpec(
            name=name,
            limit=int(spec["limit"]),
            min_count=int(spec.get("min_count", 0)),
            max_count=int(spec.get("max_count", 1)),
            hard_max=int(spec["hard_max"]) if "hard_max" in spec else None,
        )
        for name, spec in table.get("fields", {}).items()
    }
    return PlatformSpec(
        key=key,
        label=table.get("label", key),
        bulk_format=table.get("bulk_format", "csv"),
        fields=fields,
    )


def available() -> list[str]:
    return sorted(config.platforms())
