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
  transcript: bold **named** speaker labels (`**المعلِّمة:**` for teacher
  Haya, `**ديفيد:**` for David) with a per-line italic English gloss. If
  the fetched body lacks that format — raw ASR, `SPEAKER S2/S3` labels, no
  labels, or a non-lesson recording (the Recordings DB also holds coaching
  and debugging sessions) — **stop** and tell the user to run the
  transcript-cleanup workflow (verify speakers, add glosses, write back to
  Notion) first. Do not guess speakers from unlabelled text.
- **A file path** → `Read` it. A file is taken as authoritative input.

### 2. First-pass extraction (Sonnet sub-agent)

Dispatch a `Task` sub-agent with `model: sonnet`, passing the fetched source
text, the taxonomy below, and the extraction rules. Ask it to **write
`vocab_pairs.csv`** in the project root (columns
`arabic,english,register,concept_tag`, **no `id`**) and to **return only a
short count summary** — this keeps the long transcript out of the main
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
| `arabic` | The Arabic text, cleaned of stray formatting; keep the transcript's tashkeel |
| `english` | Reuse the transcript's italic gloss if present, else translate |
| `register` | **Per phrase:** `egyptian` for Egyptian colloquial, `msa` for Fusha, `iraqi` for Iraqi — one lesson mixes registers, so decide line by line |
| `concept_tag` | A tag from the scheme matching the register (below) |

**Concept tag taxonomy.** Two schemes — pick from the one matching the
register. `greetings` is shared. (Source of truth: `ConceptTag` in
`scripts/model.py`; `kallim lint` validates.)

*Situational — for `egyptian` (travel-phrasebook situations):*

| Tag | Covers |
|-----|--------|
| `greetings` | hello, goodbye, pleasantries |
| `smalltalk` | casual chit-chat, "first time here?", traffic |
| `dining` | cafe/restaurant: ordering, menus, the bill |
| `hotel` | check-in, rooms, hotel amenities |
| `taxis` | hailing/agreeing rides, fares |
| `directions` | "walk from here", finding places |
| `sightseeing` | landmarks, mosques, tours, excursions, boat trips |
| `beach_and_vendors` | beach, sellers, hawkers |
| `shopping` | shops, markets, haggling, "too expensive", "best price?" |
| `money` | prices, change, paying amounts |

*Topical — for `msa` / `iraqi` (conversation topics):*

| Tag | Covers |
|-----|--------|
| `greetings` | hello, goodbye, pleasantries |
| `food` | diet, cooking, ingredients, meals, cafes/drinks |
| `travel` | transport, directions, sightseeing |
| `people` | family, society, relationships, community |
| `emotions` | feelings, dreams, personality traits |
| `leisure` | nature, parks, daily life, weather, hobbies |
| `culture` | religion, traditions, proverbs, reading |
| `health` | health system, body, exercise |
| `work` | business, career, pressure |

If no tag fits well, pick the closest match within the register's scheme.

### 3. Ingest — dedup, id, validate

Run the deterministic ingest command over the sub-agent's candidates:

```bash
.venv/bin/kallim ingest vocab_pairs.csv
```

This dedups each candidate against `chunks.csv` (diacritics-insensitive —
vocalized and bare spellings of the same phrase collapse to one), assigns a
new id, validates the register/tag against the taxonomy, and writes
`vocab_chunks_review.csv`. It never calls an external API or invents text.

### 4. Show the summary and wait for approval

Read `vocab_chunks_review.csv` and present a markdown table of the new
chunks with counts:

- New chunks written
- Duplicates skipped (from the ingest log)
- By register
- By concept_tag

**Stop and wait for the user to review.** They may edit
`vocab_chunks_review.csv` directly — add, remove, retag, or fix Arabic.
Do NOT proceed until they explicitly approve.

### 5. Append and validate

On approval, commit the reviewed rows and lint:

```bash
.venv/bin/kallim ingest --append
.venv/bin/kallim lint
```

`--append` writes the reviewed chunks into `chunks.csv` (matching its
CRLF + minimal-quoting dialect); `lint` confirms the taxonomy. Report the
result. Regenerating audio / the Anki deck is left to the user.

## Error handling

- **Notion fetch fails / page not found** → tell the user and stop.
- **Recording isn't a cleaned transcript** → fail-fast per step 1; point the
  user at the transcript-cleanup workflow.
- **Input file doesn't exist** → tell the user and stop.
- **`chunks.csv` doesn't exist** → ingest simply skips dedup (nothing to
  compare against).
