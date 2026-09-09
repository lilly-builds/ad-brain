"""Command line interface.

Each subcommand is one stage of the loop and reads what the previous one wrote:

    rank  ->  (sub-agents write candidates.json)  ->  validate  ->  build  ->  log

Output is written for a marketer: what changed and what it means, not stack
traces and object counts.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import brief as brief_mod
from . import bulk, config, ingest, platforms, rank, report, runs, validate


def _fail(message: str) -> int:
    print(f"\n  ✗ {message}\n", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------

def cmd_rank(args) -> int:
    ads = ingest.read(args.input, args.platform)
    if not ads:
        return _fail(f"no ads parsed from {args.input} — check it is a {args.platform} export")

    judged, cohort = rank.judge(ads)
    summary = rank.summarise(judged, cohort)
    run = runs.create(args.platform)
    payload, markdown = brief_mod.build(judged, cohort, args.platform, summary)
    payload["source_export"] = str(Path(args.input).resolve())
    payload["run_id"] = run.name
    runs.write_json(run, runs.BRIEF_JSON, payload)
    runs.write_text(run, runs.BRIEF_MD, markdown)

    print(f"\n  {summary['total_ads']} ads read from {Path(args.input).name}")
    print(f"  {summary['significant']} had enough data to judge "
          f"({summary['below_significance']} still proving themselves)")
    print(f"\n  ⚑ {summary['flagged']} flagged for iteration — "
          f"${summary['wasted_spend']:,.0f} of spend behind them")
    print(f"  ★ {summary['winners']} performing well enough to learn from")
    print(f"  account average ctr: {summary['account_mean_ctr']}%")
    if summary.get("age_unknown"):
        print("\n  ⚠ no start dates in this export — the minimum-age gate was skipped")

    worst = [j for j in judged if j.is_underperformer][:5]
    if worst:
        print("\n  worst offenders:")
        for j in worst:
            print(f"    {j.ad.ad_id:<12} {j.ad.metrics.ctr:>5.2f}% ctr  "
                  f"${j.ad.metrics.spend:>8,.0f}  {j.flags[0].plain_english}")

    print(f"\n  brief written to {run.name}/brief.md")
    print("  next: generate candidates with the copy sub-agents, then "
          "`adbrain validate --run latest`\n")
    return 0


def cmd_validate(args) -> int:
    run = runs.resolve(args.run)
    brief_data = runs.read_json(run, runs.BRIEF_JSON)
    platform = brief_data["platform"]
    try:
        candidates = runs.read_json(run, runs.CANDIDATES).get("generated", [])
    except FileNotFoundError:
        return _fail(
            f"{run.name}/candidates.json not found.\n"
            f"    The copy sub-agents write it. Read {run.name}/brief.md, generate\n"
            f"    replacements, and save them there."
        )
    if not candidates:
        return _fail("candidates.json contains no generated ads")

    results, blocking, warnings = [], [], []
    for c in candidates:
        entry = {"ad_id": c.get("ad_id"), "fields": {}}
        for field_name, texts in c.get("fields", {}).items():
            if field_name not in platforms.get(platform).fields:
                continue
            lines, set_level = validate.check_set(texts, platform, field_name)
            entry["fields"][field_name] = [
                {
                    "text": r.text, "chars": r.chars, "limit": r.limit, "ok": r.ok,
                    "violations": [
                        {"kind": v.kind, "severity": v.severity, "message": v.message,
                         "overage": v.overage, "text": v.text, "field_name": v.field_name}
                        for v in r.violations
                    ],
                }
                for r in lines
            ]
            for r in lines:
                for v in r.violations:
                    record = {"ad_id": c.get("ad_id"), "field_name": field_name,
                              "kind": v.kind, "message": v.message, "text": v.text,
                              "overage": v.overage}
                    (blocking if v.blocking else warnings).append(record)
            for v in set_level:
                blocking.append({"ad_id": c.get("ad_id"), "field_name": field_name,
                                 "kind": v.kind, "message": v.message, "text": "", "overage": 0})
        results.append(entry)

    payload = {"run_id": run.name, "platform": platform, "results": results,
               "blocking": blocking, "warnings": warnings,
               "passed": not blocking}
    runs.write_json(run, runs.VALIDATION, payload)

    total_lines = sum(len(f) for e in results for f in e["fields"].values())
    print(f"\n  checked {total_lines} lines across {len(candidates)} ads")

    if blocking:
        runs.write_text(run, runs.REGENERATE, _regeneration_request(blocking, platform))
        print(f"\n  ✗ {len(blocking)} must be regenerated:\n")
        for b in blocking[:15]:
            where = f"{b['ad_id']} · {b['field_name']}"
            print(f"    {where:<28} {b['message']}")
            if b["text"]:
                print(f"    {'':<28} in: {b['text']!r}")
        if len(blocking) > 15:
            print(f"    ... and {len(blocking) - 15} more")
        print(f"\n  full rewrite request: {run.name}/regenerate.md")
        print("  nothing was truncated. rewrite these and rerun validate.\n")
        return 1

    print(f"  ✓ every line fits and is on voice")
    if warnings:
        print(f"\n  {len(warnings)} worth a look (not blocking):")
        for w in warnings[:10]:
            print(f"    {w['ad_id']} · {w['field_name']} — {w['message']}")
    print(f"\n  next: adbrain build --run {run.name}\n")
    return 0


def _regeneration_request(blocking: list[dict], platform: str) -> str:
    spec = platforms.get(platform)
    by_ad: dict[str, list[dict]] = {}
    for b in blocking:
        by_ad.setdefault(b["ad_id"] or "unknown", []).append(b)

    lines = [
        "# regeneration request",
        "",
        "These lines did not pass. **Rewrite them — do not trim them.** A truncated "
        "line fits the box and says nothing, which is the failure this system exists "
        "to prevent.",
        "",
    ]
    for ad_id, items in by_ad.items():
        lines += [f"## {ad_id}", ""]
        for b in items:
            budget = ""
            if b["field_name"] in spec.fields:
                budget = f" (budget: {spec.field(b['field_name']).limit} chars)"
            lines.append(f"- **`{b['field_name']}`**{budget} — {b['message']}")
            if b["text"]:
                lines.append(f"    - rejected: {b['text']!r}")
            if b["overage"]:
                lines.append(f"    - needs to lose at least **{b['overage']}** characters")
        lines.append("")
    lines += [
        "---",
        "",
        "Rewrite in `candidates.json`, then run `adbrain validate --run latest` again.",
        "",
    ]
    return "\n".join(lines)


def cmd_build(args) -> int:
    run = runs.resolve(args.run)
    brief_data = runs.read_json(run, runs.BRIEF_JSON)
    validation = runs.read_json(run, runs.VALIDATION)
    if not validation.get("passed"):
        return _fail(
            "validation has not passed for this run — fix "
            f"{run.name}/regenerate.md and rerun validate first"
        )
    candidates = runs.read_json(run, runs.CANDIDATES).get("generated", [])
    for c in candidates:
        c.setdefault("run_id", run.name)

    platform = brief_data["platform"]
    csv_path = run / runs.BULK_CSV
    written = bulk.write(csv_path, platform, candidates)
    runs.write_text(run, runs.DIFF_MD, report.render(brief_data, candidates, validation))

    print(f"\n  ✓ {written} rows written to {run.name}/{runs.BULK_CSV}")
    print(f"    imports **paused** — nothing goes live until you enable it")
    print(f"  ✓ changes explained in {run.name}/{runs.DIFF_MD}")
    print(f"\n  next: adbrain log --run {run.name}  (records what we are testing)\n")
    return 0


def cmd_limits(args) -> int:
    keys = [args.platform] if args.platform else platforms.available()
    for key in keys:
        spec = platforms.get(key)
        print(f"\n  {spec.label}  ({key})")
        for name, f in spec.fields.items():
            extra = f"  [api max {f.hard_max}]" if f.hard_max else ""
            print(f"    {name:<16} {f.limit:>4} chars   {f.min_count}–{f.max_count} of them{extra}")
    print()
    return 0


def cmd_check(args) -> int:
    result = validate.check_line(args.text, args.platform, args.field)
    mark = "✓" if result.ok else "✗"
    print(f"\n  {mark} {result.chars}/{result.limit} chars — {args.text!r}")
    for v in result.violations:
        print(f"      ({v.severity}) {v.message}")
    print()
    return 0 if result.ok else 1


# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adbrain",
        description="Growth marketing automation. Brand rules live in brand/ and config/.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("rank", help="read an export, flag underperformers, write the generation brief")
    p.add_argument("--input", required=True, help="path to a platform export CSV")
    p.add_argument("--platform", required=True, choices=platforms.available())
    p.set_defaults(func=cmd_rank)

    p = sub.add_parser("validate", help="check generated copy against limits and voice")
    p.add_argument("--run", default="latest")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("build", help="write the bulk-upload CSV and the change report")
    p.add_argument("--run", default="latest")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("limits", help="show the character limits in force")
    p.add_argument("--platform", choices=platforms.available())
    p.set_defaults(func=cmd_limits)

    p = sub.add_parser("check", help="check one line of copy")
    p.add_argument("text")
    p.add_argument("--platform", required=True, choices=platforms.available())
    p.add_argument("--field", required=True)
    p.set_defaults(func=cmd_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        return _fail(str(exc).strip('"'))


if __name__ == "__main__":
    raise SystemExit(main())
