# Kallim

Arabic language learning toolkit. Generates shadowing audio, Anki flashcard
decks, and transcripts from a structured vocabulary bank (`chunks.csv`).

## What it does

- **Shadowing audio** — English phrase, pause, Arabic phrase, pause. Grouped
  by topic into section MP3s for car/walk listening.
- **Anki decks** — Flashcards with audio. English on front, Arabic on back.
- **Multi-register** — Supports Egyptian, MSA, and Iraqi Arabic with separate
  ElevenLabs voices per register.

## Prerequisites

- Python 3.12+
- ffmpeg (`sudo apt install ffmpeg` or `brew install ffmpeg`)
- ElevenLabs API key + voice IDs (one per register + English)

## Setup

```bash
uv sync
cp .env.example .env
# Edit .env with your API key and voice IDs
```

Run commands with `uv run` (e.g. `uv run kallim generate`).

One extra step per clone, which wires the shared commit-message and pre-push
gates:

```bash
npm install
```

This is a dev-only npm layer (husky + `@casomoltd/tooling`) that exists solely
to carry those hooks. uv remains the project toolchain — dependencies, checks
and versioning all go through it.

## Usage

```bash
# Generate shadowing audio for all sections
kallim generate

# Single section only
kallim generate --section dining

# Custom pause duration (seconds, applied uniformly)
kallim generate --pause 3.0

# Force-regenerate audio, ignoring the cache (e.g. after a voice change)
kallim generate --force

# Generate Anki deck with audio
kallim anki

# Text-only Anki cards (no API calls)
kallim anki --no-audio

# Render a distilled lesson script to a two-voice MP3 (dry run shows the cost)
kallim script scratch/damascus.md
kallim script scratch/damascus.md --render

# Validate chunks.csv (register is an enum, topic is a registered slug)
kallim lint

# Delete orphaned audio cache files (dry run; add --apply to delete)
kallim prune

# List available ElevenLabs voices
kallim voices
```

## Output

Each run creates a timestamped directory under `output/` containing everything
from that run, flat:

```
output/
└── 20260603_141523/
    ├── 01_greetings.mp3              # shadowing audio
    ├── 01_greetings.txt
    ├── 02_smalltalk.mp3
    ├── 02_smalltalk.txt
    ├── kallim_arabic.apkg
    └── generate.log
```

Per-chunk audio is **content-addressed**: each side is cached in `audio/` as
`<content-hash>.mp3` (the hash of its text). A present file is therefore correct
by construction — editing a chunk's English or Arabic (or changing its register)
changes the hash, so the next run regenerates only the affected side and leaves
the old file behind; identical text across chunks shares one file. Use
`kallim generate --force` to regenerate regardless (the hash can't see voice-id
changes in `.env`).

Both removing a row and editing one leave orphaned files (the old hash is no
longer produced by any chunk). Run `kallim prune` to list them and
`kallim prune --apply` to delete. Note Anki cards are **not** removed this way —
genanki only adds/updates notes, so cards for deleted chunks must be removed by
hand in Anki.

## Data model

The source of truth is `chunks.csv` — one phrase pair per row:

```
id,arabic,english,register,tag,topic,priority
0dc7e80b,السلام عليكم,Hello / Peace be upon you,egyptian,general,greetings,normal
```

### Topic

**`topic`** — what the chunk is *about*. One slug, lowercase with underscores,
and it must be **registered** in `TOPICS` (`scripts/model.py`). Adding one costs
a line there.

It is checked rather than free because an unregistered value is far more often a
typo than a new dossier, and an unnoticed typo silently splits a section, drops
rows from `--section`, and opens a second Anki namespace. `kallim harvest` fails
loudly on one, naming the topic and saying what to do.

**What is *not* a column:** which topic you are currently studying. That is a
property of the syllabus, not of a chunk — `--section history` is how you drill
it, and when the focus moves nothing about a row changes.

Nor is "I need to learn this" a column. Per the rule in `DESIGN.md`, the CSV owns
**content** and Anki owns **learning state**; flagging a card is Anki's job and
must never be synced back. `priority=high` is a different claim — that a chunk is
structurally high-leverage for building an argument — which is true whether or
not you know it yet, so it belongs here.

`kallim lint` validates the whole bank. Per row: the register must be an enum
member and the topic must be registered. Across rows: no duplicate ids, and no
two rows whose Arabic folds to the same identity once diacritics are stripped —
that check lives here rather than in `ingest` because a row can reach the bank
by several routes and a check guarding only one of them guards nothing.

It does **not** judge whether the topic is *right* — that is `/review-chunks`.

### The two banks

| File | Rows | What it is |
|---|---|---|
| `chunks.csv` | 679 | MSA. The live bank: drilled, rendered, added to. |
| `egyptian.csv` | 391 | Egyptian, frozen. Kept for **reception** — songs, media, a future trip — not production. |

`generate`, `anki` and `lint` default to `chunks.csv`. Reach the frozen bank
explicitly with `--input egyptian.csv`.

`kallim prune` reads **both**, so freezing a bank never makes its audio look
orphaned. Pruning against `chunks.csv` alone would report all 780 Egyptian
files as deletable.

## Adding vocabulary

The vocab pipeline mines **authentic** Arabic — a teacher's own phrases or
entries you captured yourself — into `chunks.csv`. Nothing is synthesised.

1. **Source** — one of: a **cleaned** Notion lesson transcript (named speakers
   + English glosses, written back to Notion), the Notion *Arabic — Scratchpad*
   page, or a local text file.
2. **Extract** — run the `/extract-vocab <source>` skill. A Sonnet sub-agent
   pulls high-authority chunks (teacher-said or teacher-corrected), assigns a
   register and topic to each, and writes `scratch/vocab_pairs.csv`.
3. **Harvest** — `kallim harvest scratch/vocab_pairs.csv` dedups against
   `chunks.csv` (diacritics-insensitive), assigns ids, validates, appends the
   survivors and lints the result. No API calls, no invented text.
4. **Review** — the rows are in `chunks.csv` **uncommitted**, so `git diff` is
   the review surface. `/review-chunks --new` puts the judgement agent over
   them; `git checkout chunks.csv` throws a bad batch away.
5. **Commit** — when the diff reads right.
6. **Generate** — run `kallim generate` / `kallim anki` to produce audio and
   flashcards.

```bash
# From a review CSV onward
kallim harvest scratch/vocab_pairs.csv  # dedup + id + validate + append + lint
git diff chunks.csv                # the review surface; checkout to discard
kallim anki                        # generate Anki deck
```

## Anki workflow

The deck is a disposable render target — `chunks.csv` is the source of truth,
Anki owns scheduling state. You can re-export and re-import safely at any time.

### Adding new vocabulary

1. Add new rows to `chunks.csv` (give each a unique `id`).
2. Regenerate the deck:
   ```bash
   kallim anki
   ```
3. Open Anki desktop.
4. **File > Import** and select the `.apkg` from the latest run directory.
5. Anki will add the new cards. Existing cards keep their review history,
   intervals, and ease factors. No duplicates.

### Removing vocabulary

Deleting a row from `chunks.csv` is **not** self-contained — two things survive it:

- **The Anki card.** genanki and Anki only ever *add or update* notes by GUID;
  neither deletes. A removed chunk leaves its card alive in your collection, and
  it has to be deleted by hand — search the English or Arabic text, or the tag.
  There is no automation for this and there is unlikely to be: deleting cards
  from a collection Anki owns is not the CSV's business.
- **Its cached audio**, which `kallim prune --apply` clears.

### What happens on import

- **New cards** (IDs Anki hasn't seen) are added to the deck.
- **Existing cards** (IDs Anki already has) are left untouched — scheduling
  state is preserved. If you updated the English or Arabic text in the CSV,
  the card content will be updated.
- **No duplicates** — Anki deduplicates by note ID, which is deterministic.
- **Tags** are updated to match the current `topic` and `priority` values.

## Troubleshooting

### Duplicate or orphaned tags in AnkiDroid

If you see tags appearing both as a flat list and as a nested tree (e.g. `cafe`
and `topic::cafe`), stale tags from a previous import need clearing. From the
main menu (decks), tap the three-dot menu in the top right and select
**Check → Check database**. This removes orphaned tags that are no longer
attached to any notes.

## Configuration

API keys **and voice ids** live in `.env` (gitignored) — see `.env.example`:

```
ELEVENLABS_API_KEY=...

ELEVENLABS_VOICE_ENGLISH=...    # the four bank voices, one per register
ELEVENLABS_VOICE_EGYPTIAN=...
ELEVENLABS_VOICE_MSA=...
ELEVENLABS_VOICE_IRAQI=...

ELEVENLABS_VOICE_TEACHER=...    # the two script voices, one per speaker
ELEVENLABS_VOICE_DAVID=...
```

One convention, `ELEVENLABS_VOICE_<MEMBER>`, covers both axes: a `Register`
picks a bank voice, a `Speaker` picks a script voice. A missing one is reported
up front, naming the variable, rather than failing part-way through a paid run.

Run `kallim voices` to list the voice IDs available on your account.

## Claude Code skills

The project includes [Claude Code](https://claude.com/claude-code) skills in
`.claude/skills/` that automate common workflows:

| Skill | Invocation | What it does |
|-------|------------|--------------|
| **extract-vocab** | `/extract-vocab <source>` | Mines authentic Arabic chunks from a cleaned Notion transcript, the Scratchpad, or a text file (Sonnet sub-agent), then `kallim harvest` dedups, ids, validates and appends them to `chunks.csv`, uncommitted. |
| **review-chunks** | `/review-chunks --topic history` | Audits a slice of a bank for the judgement `kallim lint` can't reach — drifted topic, unearned priority, a gloss that doesn't match the Arabic, and reusable frames trapped inside topic-bound sentences. Dispatches the `chunk-review` agent, which proposes with reasons and never edits a bank. |
| **distil-lesson** | `/distil-lesson <recording>` | Turns one recorded lesson into a shadowable two-voice script page plus vocab candidates, in a single pass over the **raw** transcript. `kallim script` renders the page to audio; the candidates go through the same `harvest` → review-the-diff pipeline as extract-vocab. |
| **commit** | `/commit [message]` | Runs pyright type checks, stages files explicitly, shows the diff for approval, then commits. |
