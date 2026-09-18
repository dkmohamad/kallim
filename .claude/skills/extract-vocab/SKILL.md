---
name: extract-vocab
description: >-
  Mine authentic Arabic chunks from a cleaned Notion lesson transcript,
  the Arabic Scratchpad, or a text file into chunks.csv — via a Sonnet
  first-pass agent plus the deterministic `kallim ingest` command
user-invocable: true
argument-hint: "<cleaned recording title|date|url> | scratchpad | <file path>"
allowed-tools:
  - Read
  - Write
  - Task
  - Bash(.venv/bin/kallim *)
  - mcp__claude_ai_Notion__notion-fetch
  - mcp__claude_ai_Notion__notion-search
  - mcp__claude_ai_Notion__notion-query-data-sources
---

# Extract Vocabulary Skill

Mine **authentic** Arabic chunks from one named source into the Kallim
learning pipeline. Everything practiced must be real — a teacher's own
Arabic, a phrase she corrected, or an entry you captured yourself — never
synthetic. A Sonnet sub-agent does the first-pass extraction; the
deterministic `kallim ingest` command does the dedup, id assignment, and
validation.

## Input

`$ARGUMENTS` names **one** source:

- `scratchpad` — the Notion *Arabic — Scratchpad* page.
- a **cleaned** lesson recording — by title, date, or Notion URL.
- a path to a local text file (transcript or notes).

If `$ARGUMENTS` is empty, ask the user which source to use.

## Steps

Follow these steps in order. Do NOT skip or reorder steps.

### 1. Resolve and fetch the source

- **`scratchpad`** → `notion-fetch` page
  `374d9af2-a639-817a-adca-ec8bf4b66aa5`.
- **A recording** → `notion-fetch` the page directly if given a URL,
  otherwise `notion-query-data-sources` the Recordings data source
  `collection://f409a1e9-2eb6-47df-be16-3e29ac2da44d` to find it by
  title/date, then fetch it with `include_transcript: true`.

  **Fail-fast — cleaned transcripts only.** The extractor needs a cleaned
  transcript: bold **named** speaker labels (`**المعلِّمة:**` for the teacher,
  `**ديفيد:**` for David) with a per-line italic English gloss. If
  the fetched body lacks that format — raw ASR, `SPEAKER S2/S3` labels, no
  labels, or a non-lesson recording (the Recordings DB also holds coaching
  and debugging sessions) — **stop** and tell the user to run the
  transcript-cleanup workflow (verify speakers, add glosses, write back to
  Notion) first. Do not guess speakers from unlabelled text.
- **A file path** → `Read` it. A file is taken as authoritative input.

### 2. First-pass extraction (Sonnet sub-agent)

First, fetch the current topic registry (see **Topic** below) so the sub-agent
files against the live registry, not a copy.

Dispatch a `Task` sub-agent with `model: sonnet`, passing the fetched source
text, that tag menu, and the extraction rules. Ask it to **write
`scratch/vocab_pairs.csv`** (columns
`arabic,english,register,topic,priority`, **no `id`**) and to **return
only a short count summary** — this keeps the long transcript out of the main
context.

The sub-agent's brief:

**What counts as a high-authority chunk**

- *Cleaned recording:* the **teacher's** (`المعلِّمة`) correct Arabic, and
  any of David's lines the teacher **explicitly corrected or confirmed** in
  context. Skip David's error-attempts, filler, Fusha scaffolding he used to
  reach for a word, bare single words, and trip-logistics chatter.
- *Scratchpad:* its entries are authentic by its own capture rules — take
  the `English⇥Arabic` tab-table pairs and the bullet chunk-lists; ignore
  the italic grammar-frame annotations `*(...)*` and correction notes.
- *File:* the useful phrases/sentences a learner would memorise.

**Validity gate.** Keep a candidate only if it is teacher-origin/corrected
(or a scratchpad/file entry) **and** it passes the sub-agent's own
linguistic check — well-formed, correct meaning, sensible tashkeel. Drop
anything doubtful rather than pass it through.

**Fields, per candidate**

| Field | How to decide |
|-------|---------------|
| `arabic` | The Arabic text, cleaned of stray formatting; keep the transcript's tashkeel. **One surface form only** — never slash-alternates like عايز/عايزة (lint rejects them); emit each variant as its own row if both matter |
| `english` | Reuse the transcript's italic gloss if present, else translate |
| `register` | **Per phrase:** `egyptian` for Egyptian colloquial, `msa` for Fusha, `iraqi` for Iraqi — one lesson mixes registers, so decide line by line |
| `topic` | What it is about. Must be a topic `kallim tags` lists — an unregistered one is rejected by ingest. If the source is a genuinely new dossier, say so in the summary rather than coining a slug |
| `priority` | `high` only for frames and discourse operators (see below); everything else `normal` (may be omitted — ingest defaults it) |

**Emit the frames, not just the sentences.** This is the highest-value thing the
extraction does, and the easiest to get wrong.

A corpus review of 2026-08-25 found the bank running at roughly 4% in-speech
discourse operators against 26% topic-bound content sentences, with most core
operators — `فِي الوَاقِعِ`, `بِصَرَاحَةٍ`, `عَلَى سَبِيلِ المِثَالِ`,
`مِنْ نَاحِيَةٍ أُخْرَى` — appearing **zero** times. It diagnosed the cause as this
brief: *the extractor selects for things that look like sentences, and the
highest-leverage material in any language does not look like a sentence.* The
material is in the lessons; it was being discarded.

So, alongside the sentences:

- **Discourse and stance operators** — `يَعْنِي`, `أَيْضًا`, `إِذَنْ`, `مَثَلًا`,
  `فِي الوَاقِعِ`, `بِالمُنَاسَبَةِ`, `بِالمُقَارَنَةِ مَعَ …`, `أَعْتَقِدُ أَنَّ …`. These
  manage the conversation itself and are topic-free. Take them even when they
  are a single word in the middle of a turn. `priority=high`.
- **Repair and metalinguistic phrases** — `كَيْفَ أَقُولُ …؟`, `مَا مَعْنَى …؟`,
  `لَمْ أَفْهَمْ، أَعِدْ مِنْ فَضْلِكَ`. Maximal use in a lesson, and the bank has
  almost none. `priority=high`.
- **Reusable frames trapped inside a sentence.** When a sentence is built on a
  generally applicable frame, emit the bare frame as its own row *in addition*
  to the sentence: Arabic + `...`, gloss + `...`, `priority=high`. The full
  sentence stays `normal`. Example in the bank: `كان لديَّ اهتمامٌ بـ...` —
  "I have been interested in...". Emit a frame once even if several sentences
  share it; dedup guards re-ingest.

**What `high` means, precisely.** That a chunk is *structurally* high-leverage
for building an argument — a frame, a connector, a stance marker. It is a fact
about the chunk, true whether or not David knows it yet. It does **not** mean
"he needs to learn this": that is learning state, it lives as a flag in Anki,
and per `DESIGN.md` it must never enter the CSV. A full sentence is essentially
never `high`.

**Topic.** One registered slug. Fetch the registry live so this skill can never
drift from the code — the hardcoded tag table that used to live here drifted and
mis-tagged a run, which is why it was removed:

```bash
.venv/bin/kallim tags
```

Topics marked `*` are under current study. Source of truth: `TOPICS` in
`scripts/model.py`; ingest rejects anything else, so if the source really is a
new dossier, report it rather than inventing a slug — it needs a line in
`TOPICS` first.

**Register fidelity.** Egyptian rows keep their colloquial forms verbatim
(`عايز`, `بكام`, `ما ينفعش`). Never convert dialect to Fusha: in a dialect
lesson the dialect *is* the target, not an error.

### 3. Ingest — dedup, id, validate

Run the deterministic ingest command over the sub-agent's candidates:

```bash
.venv/bin/kallim ingest scratch/vocab_pairs.csv
```

This dedups each candidate against `chunks.csv` (diacritics-insensitive —
vocalized and bare spellings of the same phrase collapse to one), assigns a
new id, validates the register, topic and priority, and writes
`scratch/vocab_chunks_review.csv`. It never calls an external API or invents text.

> `ingest` rewrites that file wholesale each run, so don't run it again over a
> different candidates file while rows are waiting there — the unreviewed batch
> is lost.

### 4. Review the batch

Dispatch the `chunk-review` agent on `scratch/vocab_chunks_review.csv`.

This is the cheapest possible moment to catch a wrong topic, an unearned
`priority`, a gloss that drifts from the Arabic, or a frame left trapped inside
a sentence: nothing has been appended, so a fix costs an edit to a scratch file.
The same mistake found after `--append` costs a migration over `chunks.csv`.

Fold its proposals into the summary in step 5 rather than reporting them
separately — the user is deciding about one batch, not reading two reports.

### 5. Show the summary and wait for approval

Read `scratch/vocab_chunks_review.csv` and present a markdown table of the new
chunks with counts:

- New chunks written
- Duplicates skipped (from the ingest log)
- By register
- By topic
- **The review agent's proposals**, with reasons — and in particular any frame
  it says is still trapped inside a sentence, since those are new rows to add
  rather than edits to existing ones

**Stop and wait for the user to review.** They may edit
`scratch/vocab_chunks_review.csv` directly — add, remove, retag, or fix Arabic.
Do NOT proceed until they explicitly approve.

### 6. Append and validate

On approval, commit the reviewed rows and lint:

```bash
.venv/bin/kallim ingest --append
.venv/bin/kallim lint
```

`--append` writes the reviewed chunks into `chunks.csv` (matching its
CRLF + minimal-quoting dialect); `lint` confirms register, topic and priority.
Report the result. Regenerating audio / the Anki deck is left to the user.

## Error handling

- **Notion fetch fails / page not found** → tell the user and stop.
- **Recording isn't a cleaned transcript** → fail-fast per step 1; point the
  user at the transcript-cleanup workflow.
- **Input file doesn't exist** → tell the user and stop.
- **`chunks.csv` doesn't exist** → ingest simply skips dedup (nothing to
  compare against).
