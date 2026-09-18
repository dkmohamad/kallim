---
name: review-chunks
description: >-
  Audit a slice of the chunk bank for the judgement `kallim lint` can't reach —
  drifted topic, unearned priority, a gloss that doesn't match the Arabic, and
  reusable frames trapped inside topic-bound sentences. Proposes with reasons;
  never edits a bank.
user-invocable: true
argument-hint: "--topic history | review | <path.csv>"
allowed-tools:
  - Read
  - Write
  - Task
  - Bash(.venv/bin/kallim *)
  - Bash(uv run *)
---

# Review Chunks Skill

`kallim lint` checks mechanics: the register is an enum member, the topic is a
registered slug, the Arabic carries no slash-alternate. It cannot tell you that
*"We don't have palm trees in Britain"* is not history, or that a `high`
priority was never earned. That judgement is this skill.

**It proposes; it never writes to a bank.** Output is a proposals CSV and a
report. Applying them is a separate, deliberate step.

## Input

`$ARGUMENTS` names **one** slice. Reviewing the whole bank in a single pass is
not supported: it produces a wall of proposals nobody reads.

- `--topic history` — every row carrying that topic.
- `review` — `scratch/vocab_chunks_review.csv`, the batch waiting to be
  appended. **The highest-value moment to run this**: a wrong topic caught here
  costs nothing, and caught after `--append` costs a migration.
- a path to any chunks-shaped CSV.

If `$ARGUMENTS` is empty, ask which slice.

## Steps

Follow these steps in order. Do NOT skip or reorder steps.

### 1. Cut the slice

Read the vocabulary the bank actually uses, so the sub-agent judges against the
real registry rather than its own idea of one:

```bash
.venv/bin/kallim tags
```

Then cut the slice to `scratch/chunk_review_input.csv`, preserving the header.
Report the row count. **If the slice is over 120 rows, stop and tell the user
to narrow it** — beyond that the agent's attention thins and the proposals get
worse in a way that is hard to see.

### 2. Dispatch the review agent

One `Task` call, `subagent_type: chunk-review`. Hand it the slice path and the
`kallim tags` output. The rubric — leverage class, topic, priority, gloss, authenticity and register
fidelity — lives in the agent definition
(`.claude/agents/chunk-review.md`), which is the single source of truth for the
durable chunk rules. Do not restate it here; a second copy will drift.

### 3. The proposals

The agent writes `scratch/chunk_review.csv`
(`id,arabic,english,field,current,proposed,reason` — the text is carried so the
file can be read without joining it back against the bank) and returns a report. Relay the report: the leverage census, the proposals
grouped by field with their reasons, and what it deliberately did not flag.

The **discourse-operator share** in the census is the number to watch: it is what
the rubric exists to move. Record it each run so the trend is visible.

A corpus-wide census of 2026-08-25 measured the baseline and is the origin of
the leverage classes in the agent's rubric. It is **not** in the repo — it
quotes lesson material and names the teacher, and this repo is public. Ask Dave
for it rather than looking for a path.

### 4. Applying

There is no apply command, deliberately. Dave reads the proposals and edits the
bank, or asks for the ones he accepts to be applied. Build an apply path only
once the proposals have proved good enough to trust in bulk — which is a thing
to find out, not assume.

## Calibration

Run it first on `--topic history`, the rows a keyword pass assigned. Their
right answer is already roughly known: the Ottoman, Abbasid, Umayyad and Arab
Revolt cluster is solidly history; the family-migration rows and *"We don't have
palm trees in Britain"* are not.

If the agent lands near that, it is calibrated and can be trusted on a slice
whose answer isn't known. If it doesn't, the rubric needs work before the
proposals mean anything — and that is the point of running it somewhere the
answer is already visible.
