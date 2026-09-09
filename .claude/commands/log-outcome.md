---
description: Record how a past experiment actually performed, now that the numbers have landed.
argument-hint: [experiment id, or leave blank to be shown what is outstanding]
allowed-tools: Bash(python3:*), Read, Glob, Grep
---

# Close the loop on an experiment

Performance data lands days after the ads do. This is the step that turns a run
from "something we did" into "something we know", and it is the step that
actually makes the next run better.

Argument: `$ARGUMENTS` — an experiment id, or nothing.

## If no experiment was named

```bash
python3 -m adbrain learned
```

Show what is outstanding, oldest first, flagging anything marked overdue. Ask
which one to close. If several are outstanding, offer to work through them.

## For the experiment being closed

1. Read `memory/experiments/<id>.md` — it states the hypothesis, what it
   replaced, and the baseline numbers to compare against.
2. Get the current numbers. Either the user has them, or pull them live via the
   Meta Ads MCP for a Meta experiment (see `docs/meta-ads-mcp.md`).
3. Compare against the recorded baseline, not against a general sense of how
   things are going. The baseline is in the file for exactly this reason.
4. Reach a verdict:

   | verdict | when |
   |---|---|
   | `won` | it beat the baseline on the metric the hypothesis named |
   | `lost` | it did worse, or the same at higher cost |
   | `flat` | no meaningful difference either way |

   Do not record `won` on a mixed result — a genuinely mixed outcome is `flat`
   with a finding that explains the split. Overstating a result here poisons
   every future brief, because this is what retrieval reads.

5. Write the finding as **one sentence stating what we now believe**, not what
   happened. "ctr went up" is a measurement. "framing against the manual status
   quo beats competitor comparison for this audience" is a finding, and it is
   the thing that changes the next run.

```bash
python3 -m adbrain outcome --experiment <id> \
    --verdict won|lost|flat \
    --finding "what we now believe, in one sentence" \
    --metric ctr=4.9 --metric conversions=31 --metric cpa=118
```

## Then

Confirm what was recorded and note that `memory/LEARNED.md` has been updated.
If the verdict was `lost`, say so plainly — a lost angle is the most valuable
entry in the log, because it is the one that stops the system spending another
cycle on ground that has already been tested.
