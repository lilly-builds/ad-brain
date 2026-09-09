# memory

The experiment log. This is the part of the system that compounds — everything
else makes the work faster, this makes it better.

| Path | What it is |
|---|---|
| `experiments/<id>.md` | one file per run, written to be opened and read |
| `index.jsonl` | the same facts, machine-queryable — what retrieval reads |
| `LEARNED.md` | rolled-up standing conclusions, regenerated on every write |
| `category/snapshots/` | point-in-time captures of what competitors are running |
| `category/digests/` | what changed between captures |

It starts empty. That is correct — until a run is logged and an outcome
recorded, the copy agent is generating without history, and the brief says so
rather than pretending otherwise.

## Filling it

```bash
python3 -m adbrain log --run latest            # after a generation run
python3 -m adbrain outcome --experiment <id> \  # once performance lands, days later
    --verdict won|lost|flat --finding "what we now believe, in one sentence"
python3 -m adbrain learned                      # read the rolled-up conclusions
```

## Try it on the sample data first

The bundled fixtures replay the whole loop without touching a real account:

```bash
export PYTHONPATH=src
python3 -m adbrain rank --input data/fixtures/google_rsa_sample.csv --platform google_rsa
python3 -m adbrain category snapshot --from-file data/fixtures/category-capture-august.csv --date 2026-08-09
python3 -m adbrain category snapshot --from-file data/fixtures/category-capture-september.csv --date 2026-09-09
python3 -m adbrain category digest
```

Then clear `memory/` again before real use — sample findings in the log would
reach real generation briefs as if they were true.

## The rule that matters

Be accurate with verdicts. Retrieval weights **losses above wins**, because
re-testing an angle that already failed is the most expensive mistake here. A
mixed result is `flat`, not `won`. Overstating one outcome poisons every brief
that follows it.
