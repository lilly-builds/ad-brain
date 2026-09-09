"""Run directories.

Each pass through the loop gets one directory under `data/out/`. Stages
communicate through files in it rather than through memory, so any stage can be
rerun, inspected, or hand-edited without rerunning the ones before it — which is
what makes the copy step debuggable when a sub-agent produces something odd.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

from . import config

BRIEF_JSON = "brief.json"
BRIEF_MD = "brief.md"
CANDIDATES = "candidates.json"
VALIDATION = "validation.json"
REGENERATE = "regenerate.md"
BULK_CSV = "bulk-upload.csv"
DIFF_MD = "changes.md"


def out_root() -> Path:
    path = config.repo_root() / "data" / "out"
    path.mkdir(parents=True, exist_ok=True)
    return path


def create(platform: str, now: _dt.datetime | None = None) -> Path:
    now = now or _dt.datetime.now()
    path = out_root() / f"{now:%Y-%m-%d-%H%M}-{platform}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve(ref: str) -> Path:
    """Resolve a run reference. `latest` means the most recent run directory."""
    if ref == "latest":
        runs = sorted((p for p in out_root().iterdir() if p.is_dir()), key=lambda p: p.name)
        if not runs:
            raise FileNotFoundError(
                "no runs yet — start one with: adbrain rank --input <export.csv> --platform <platform>"
            )
        return runs[-1]
    path = Path(ref)
    if path.is_dir():
        return path
    path = out_root() / ref
    if path.is_dir():
        return path
    raise FileNotFoundError(f"no such run: {ref}")


def write_json(run: Path, name: str, payload: dict) -> Path:
    path = run / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_json(run: Path, name: str) -> dict:
    path = run / name
    if not path.is_file():
        raise FileNotFoundError(
            f"{name} not found in {run.name} — run the previous stage first"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(run: Path, name: str, body: str) -> Path:
    path = run / name
    path.write_text(body, encoding="utf-8")
    return path
