---
name: extract-vocab
description: >-
  Extract Arabic vocabulary from raw input (teacher chats, notes,
  lesson recordings) into structured vocab pairs for the learning
  pipeline
user-invocable: true
argument-hint: "<file>"
allowed-tools:
  - Read
  - Write
  - Bash(.venv/bin/python *)
  - Bash(.venv/bin/kallim *)
---

# Extract Vocabulary Skill

Extract Arabic vocabulary from any raw input file and feed it into
the Kallim learning pipeline. This skill replaces manual extraction
scripts by using your language understanding directly.

## Input

`$ARGUMENTS` is the path to the input file. If empty, ask the user
to provide a file path or paste content.

## Steps

Follow these steps in order. Do NOT skip or reorder steps.

### 1. Read the input

Read the file at `$ARGUMENTS`. Understand its format — it could be:
- A teacher chat log (WhatsApp, Telegram, etc.)
- Pasted lesson notes
- A plain list of Arabic words/phrases
- A transcript of a conversation

### 2. Read existing chunks for deduplication

Read `chunks.csv` in the project root. Note every Arabic entry so
you can skip duplicates later.

### 3. Extract vocabulary

Scan the input for Arabic vocabulary — words, phrases, and short
sentences that a learner would want to memorise. Use your knowledge
of Arabic, not regex.

**Include:** vocabulary items, useful phrases, example sentences,
dialect expressions, greetings, idioms.

**Exclude:** conversational noise (e.g. "ok", "yes", timestamps),
platform UI text, file attachment notices, emoji-only messages,
English-only messages, duplicate entries.

### 4. Build structured entries

For each extracted item, determine:

| Field | How to decide |
|-------|---------------|
| `arabic` | The Arabic text, cleaned of stray punctuation or formatting artifacts |
| `english` | English translation — take from the source if present, otherwise translate it yourself |
| `register` | `msa`, `egyptian`, or `iraqi` — infer from dialect markers, context, or explicit labels in the source |
| `concept_tag` | One of the tags below, based on meaning **and** register |

**Concept tag taxonomy.** There are two schemes — pick from the one matching the
register. `greetings` is shared by both. (Source of truth: `ConceptTag` in
`scripts/generate.py`; validate with `kallim lint`.)

*Situational — for `egyptian` (travel-phrasebook scenes):*

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

### 5. Deduplicate

Remove any entry whose `arabic` text already appears in
`chunks.csv` (loaded in step 2). Report how many duplicates
were skipped.

### 6. Write vocab_pairs.csv

Write the results to `vocab_pairs.csv` in the project root with
columns: `arabic,english,register,concept_tag`

Do **not** include an `id` column — IDs are assigned later by
the promote step.

### 7. Show summary and wait for approval

Present a markdown table of all extracted entries to the user.
Include counts:
- Total entries extracted
- Duplicates skipped
- Entries by register
- Entries by concept_tag

**Stop and wait for the user to review.** Ask if they want to
add, remove, or edit any entries before proceeding. If the user
requests changes, update `vocab_pairs.csv` and show the revised
summary.

Do NOT proceed until the user explicitly approves.

### 8. Run promote

Run the promote command to generate example sentences for single
words and prepare the review CSV:

```bash
.venv/bin/kallim promote
```

This reads `vocab_pairs.csv`, generates example sentences for
single words (requires `ANTHROPIC_API_KEY`), and writes
`vocab_chunks_review.csv`.

Tell the user the promote step is complete and that they should
review `vocab_chunks_review.csv`. When they are satisfied, they
can append the approved rows to `chunks.csv`.

## Error handling

- If the input file doesn't exist, tell the user and stop.
- If `chunks.csv` doesn't exist, skip dedup (there's nothing to
  deduplicate against).
- If `ANTHROPIC_API_KEY` is not set when running promote, it
  will fail with an error. Tell the user to add the key to
  their `.env` file and retry.
