"""Experiment memory.

Fully implemented in Phase 2. Phase 1 depends only on `recall()`, which returns
the prior results the brief should carry into generation.
"""

from __future__ import annotations


def recall(platform: str, campaigns: list[str] | None = None, limit: int = 12) -> list[dict]:
    """Prior experiment results relevant to this generation run."""
    return []
