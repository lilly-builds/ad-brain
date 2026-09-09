"""Config loading.

Every tunable in this system lives in `config/*.toml` in plain language so it
can be changed without touching code. This module is the only thing that reads
those files.
"""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path


def repo_root(start: Path | None = None) -> Path:
    """Walk up from this file until we find the repo (identified by config/)."""
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "config").is_dir() and (candidate / "pyproject.toml").is_file():
            return candidate
    raise FileNotFoundError(
        "could not locate the ad-brain repo root (looked for a directory "
        "containing both config/ and pyproject.toml)"
    )


@lru_cache(maxsize=None)
def load(name: str) -> dict:
    """Load `config/<name>.toml`. Cached — configs do not change mid-run."""
    path = repo_root() / "config" / f"{name}.toml"
    if not path.is_file():
        raise FileNotFoundError(f"missing config file: {path}")
    with path.open("rb") as fh:
        return tomllib.load(fh)


def platforms() -> dict:
    return load("platforms")


def thresholds() -> dict:
    return load("thresholds")


def voice() -> dict:
    return load("voice")


def competitors() -> dict:
    return load("competitors")
