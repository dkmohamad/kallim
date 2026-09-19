---
name: distil-due
description: >-
  Check whether a recorded Arabic lesson is waiting to be distilled, and run
  `distil-lesson` on the newest one if so. Answers in a single line when there
  is nothing new, which is the usual case. Use when the session-start nudge
  fires, or whenever you wonder whether a lesson has gone unprocessed. It is
  only the check and the hand-off; `distil-lesson` does the work.
user-invocable: true
argument-hint: ""
allowed-tools:
  - Read
  - Write
  - Skill
  - mcp__claude_ai_Notion__notion-fetch
  - mcp__claude_ai_Notion__notion-query-data-sources
---

# Distil Due Skill

Answers one question: **is there a lesson worth distilling right now?**

The session-start hook that sends you here is a timer, not a check — it reads a
local ledger and knows only how long it has been. It cannot see Notion, because
the Recordings database is behind the claude.ai connector and there is no token
a shell script could use. So the hook says "it has been a while" and this skill
finds out whether that is true. **Answering "nothing new" is a success, not a
wasted run.**

## Steps

### 1. Read the ledger

`~/.local/state/kallim/distilled.json` — `lessons[]`, each with
`recording_id`, `date`, `title`, `page`, `distilled_at`.

Absent or unreadable is fine and means "nothing known", not an error. It is a
cache; step 3 is what actually prevents repeat work.

### 2. Find the candidates

Query the Recordings data source
`collection://f409a1e9-2eb6-47df-be16-3e29ac2da44d`:

```sql
SELECT date(`date:Date:start`) AS d, Title, Duration, id
FROM   <data source>
WHERE  Duration >= 25
ORDER  BY d DESC
```

The database holds coaching and debugging sessions too, so keep only rows whose
title names Arabic. Drop anything whose id is already in the ledger.

### 3. Confirm against Notion before doing anything

For the newest survivor, check the Arabic hub
(`374d9af2-a639-81ea-b3cc-f9a9656cb3f0`) for a script page already citing that
recording in its `**المصدر:**` line.

**This is the real guard, not the ledger.** The ledger is local and losable; a
page on the hub is the evidence that the work was done. If a page exists, add
the lesson to the ledger — it was distilled on a machine or a session that
never wrote one — and treat it as processed.

### 4. Report, and stop if nothing is due

Nothing new: **one line.** "Nothing to distil — the most recent lesson (2026-09-18)
is already done." Then stop. No table, no inventory of the backlog.

Something new: name the lesson, its date and duration, and say how many other
unprocessed lessons sit behind it — but offer only the newest. The backlog is a
separate decision and costs roughly 7k credits each.

### 5. Hand off

Invoke `distil-lesson` with the recording id. It owns every step from there:
the raw transcript, the harvest, the page, the audio, the Drive upload.

**Do not reimplement any of it here.** If it stumbles, that is a finding for
that skill.

### 6. Record it

On success append to `lessons[]`: the recording id, its date and title, the page
URL, and today as `distilled_at`. Write the whole file back; it is small.

If the run failed or was abandoned part-way, **write nothing** — a half-done
lesson must look undone next time.

## Guardrails

- **Never distil more than one lesson per invocation.** The backlog is 20-odd
  lessons at about 7k credits each; working through it is a decision Dave makes
  deliberately, not a side effect of a check.
- **Never commit.** `distil-lesson` leaves the harvested rows in `chunks.csv`
  uncommitted, and that diff is Dave's to read.
- **Never write to the ledger before the work succeeds.**
- **Never report a lesson as distilled without the page URL** to prove it.
