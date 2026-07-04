# Kallim — Design Spec

Versioned spec for the personal Arabic learning tool. Derived from the
[Notion design doc](https://app.notion.com/p/371d9af2a63981f3b43ff3ee1cf014ba).

---

## Guiding principle

The learning happens in the ear, the hand, and the mouth — not in the storage
layer. This tool reduces friction and consolidates scattered sources of truth.
Build the minimum that removes the "stuff everywhere" pain, then stop and use it.

---

## The problem it solves

Vocabulary gaps captured all over the place — daily-life gaps, lesson gaps,
notes in Drive/Docs/GitHub, recordings. No single source of truth. This is a
**capture and consolidation** problem, not a learning-algorithm problem.

---

## The split

| Layer       | Role                                    | Where                              |
|-------------|-----------------------------------------|------------------------------------|
| **Capture** | Scrappy inbox. Frictionless dumping.     | Notion page, Doc, voice note, etc. |
| **Store**   | Structured single source of truth.      | `chunks.csv` (version-controlled)  |
| **Study**   | Downstream render targets. Disposable.  | Anki deck, MP3 audio, podcast CI   |

Trying to make one system do all three is what felt unwieldy.

---

## The primitive: chunks, not words

A row is a **chunk** — a phrase with context, not an isolated word. You speak in
collocations, correctly inflected, with grammatical environment attached. Chunks
are mined from **authentic** sources — a teacher's own phrases (or ones she
corrected) and notes you captured yourself — never synthesised from bare word
lists.

---

## Data model

Flat CSV (`chunks.csv`). One chunk per row. Columns:

| Column         | Type     | Description                                                  |
|----------------|----------|--------------------------------------------------------------|
| `id`           | string   | Stable ID per row (short hex, e.g. `7f3a1b2c`). Is the audio key — `audio/{id}.mp3`. |
| `arabic`       | string   | The chunk, full tashkeel for MSA, natural form for dialect.   |
| `english`      | string   | Gloss / translation.                                         |
| `register`     | enum     | `msa` / `egyptian` / `iraqi`                                 |
| `concept_tag`  | enum     | Thematic grouping from the `ConceptTag` taxonomy (`scripts/generate.py`). Two schemes: Egyptian uses *situational* tags (`dining`, `hotel`, `taxis`, `sightseeing`, `money`, …), MSA/Iraqi use *topical* tags (`food`, `travel`, `people`, `emotions`, …); `greetings` is shared. Run `kallim lint` to validate. |

### Example

```csv
id,arabic,english,register,concept_tag
7f3a1b2c,السلام عليكم,Peace be upon you,egyptian,greetings
a9e4d8f1,وعليكم السلام,And upon you peace,egyptian,greetings
2b8c6e03,ممكن أشوف المنيو الأول؟,Can I see the menu first?,egyptian,cafe
8c1b3a5e,أَنَا أَتَعَلَّمُ اللُّغَةَ الْعَرَبِيَّةَ,I am learning Arabic,msa,learning
```

### Why CSV

- The data is a flat table — CSV *is* a flat table.
- Version-controlled in git (diffs are readable row-by-row).
- Editable in any spreadsheet app or text editor.
- Python stdlib `csv` module — no extra dependency.
- Trivial to export to/from Google Sheets if that's ever wanted.

### Migration from phrases.txt

The existing `phrases.txt` (300+ phrases across 12 sections) will be migrated
to `chunks.csv`. The section names become the basis for `concept_tag` or can be
embedded in the `id` prefix. Speaker labels (YOU:, STAFF:, etc.) are stripped
during migration.

---

## Single source of truth

The CSV owns **content**. Anki owns **scheduling state** ("do I know it"). Never
store a learning score in the CSV — that recreates the original drift problem
inside the solution.

---

## ElevenLabs TTS

### Voice mapping

Each register maps to its own voice. English gets a separate voice. This is
configured via environment variables — the CSV stays pure content, voice
selection is config.

| Variable                      | Description                        |
|-------------------------------|------------------------------------|
| `ELEVENLABS_API_KEY`          | ElevenLabs API key                 |
| `ELEVENLABS_VOICE_ENGLISH`    | Voice ID for English phrases       |
| `ELEVENLABS_VOICE_EGYPTIAN`   | Voice ID for Egyptian Arabic       |
| `ELEVENLABS_VOICE_MSA`        | Voice ID for MSA Arabic            |
| `ELEVENLABS_VOICE_IRAQI`      | Voice ID for Iraqi Arabic          |

The scripts resolve `register` → voice ID at runtime. Adding a new register
means adding one env variable.

### Model

`eleven_multilingual_v2` — supports Arabic (both MSA and Egyptian dialect).

### Output format

`mp3_44100_128` (44.1 kHz, 128 kbps). Sufficient for speech.

---

## Audio

### Format

English → pause (you produce) → Arabic (confirms). Recall-then-confirm; overlay
your voice onto the Arabic as a chunk is internalised.

### Storage

Audio is a **derived artefact**, not stored in the CSV. Each chunk's `id` is
its audio key. The MP3 lives at `audio/{id}.mp3` — nothing else in the filename.
If the file doesn't exist, regenerate it with the same key. Both consumers —
long-form playlist and Anki — resolve the same `id` to the same file.

```
audio/
├── 7f3a1b2c.mp3      # chunk id = 7f3a1b2c
├── a9e4d8f1.mp3      # chunk id = a9e4d8f1
├── 2b8c6e03.mp3      # chunk id = 2b8c6e03
└── ...
```

### Audio processing

- Normalize to -20 dBFS (loudness equalisation).
- Silence gaps: configurable via `--pause` (default 2.0s), applied uniformly.

---

## Render targets

Same chunks, one source, three downstream consumers:

### 1. Shadowing audio

Long-form MP3s grouped by section/tag. Turn-taking, recall-then-confirm — active
production. Correctly i+0 by design.

- Generated from `chunks.csv` rows filtered by register/tag.
- Output: `output/{section}.mp3` + `output/{section}.txt` transcript.

### 2. Anki cards with audio

Active recall / testing. Also i+0 by design.

- **Card template:** Front = English + English audio. Back = Arabic (RTL, large)
  + Arabic audio.
- **Incremental adds only.** Never delete-and-regenerate. Use AnkiConnect
  `addNote` to push single cards. Update by note ID.
- Anki keeps scheduling state; CSV keeps content.
- AnkiConnect requires desktop Anki running; AnkiWeb sync carries adds to mobile.

### 3. Podcast-style CI (future)

Passive listening — comprehensible input with scaffolding. The bank is a
to-learn pile, so the podcast generates *around* the chunks with settled
connective material, not just restitching them. Deferred until shadowing and
Anki are battle-tested.

---

## Pipeline

```
Scrappy inbox (recordings, notes, docs)
    ↓
chunks.csv (structured store — single source of truth)
    ↓
┌───────────────────┬──────────────────┬──────────────────┐
│ Shadowing audio   │ Anki cards       │ Podcast CI       │
│ (active production)│ (active recall) │ (passive listen) │
└───────────────────┴──────────────────┴──────────────────┘
```

---

## CLI interface

Unified entrypoint: `kallim` (installed via `pip install -e .`).

```bash
# Generate shadowing audio
kallim generate
kallim generate --section dining
kallim generate --pause 3.0

# Generate Anki deck
kallim anki
kallim anki --no-audio
kallim anki --section dining

# Ingest extracted vocab candidates into review-ready chunks (dedup + id + validate)
kallim ingest scratch/vocab_pairs.csv
kallim ingest --append   # commit scratch/vocab_chunks_review.csv into chunks.csv

# Validate chunks.csv against the concept_tag taxonomy
kallim lint

# List ElevenLabs voices
kallim voices

# One-time migration from phrases.txt
kallim migrate
```

---

## Dependencies

```
elevenlabs>=1.0.0       # TTS API client
genanki>=0.13.0         # Anki deck generation
pydub>=0.25.1           # Audio manipulation
python-dotenv>=1.0.0    # Environment variable loading
```

System: `ffmpeg` (required by pydub for MP3 encoding).

---

## Configuration

`.env` file:

```
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ENGLISH=...
ELEVENLABS_VOICE_EGYPTIAN=...
ELEVENLABS_VOICE_MSA=...
ELEVENLABS_VOICE_IRAQI=...
```

---

## Error handling

- TTS failure: retry once (2s backoff), then skip and log.
- Section with zero successful phrases: skip MP3 generation, log warning.
- All errors written to `generate.log` inside the run directory.

---

## Project structure

```
kallim/
├── cli.py               # unified CLI entrypoint (kallim command)
├── pyproject.toml       # package config + console_scripts
├── pyrightconfig.json   # pyright strict type checking
├── SPEC.md              # this file
├── CLAUDE.md            # project instructions for Claude
├── README.md            # user-facing docs
├── chunks.csv           # THE source of truth
├── .env                 # API keys (gitignored)
├── .env.example         # template
├── scripts/             # all Python modules
│   ├── generate.py      # shadowing audio generation
│   ├── generate_anki.py # Anki deck generation
│   └── migrate.py       # one-time phrases.txt → chunks.csv migration
├── audio/               # cached per-chunk MP3s (keyed by row id)
├── output/              # all generated artefacts
│   └── YYYYMMDD_HHMMSS/ # one flat dir per run (MP3s, transcripts, .apkg, log)
└── .venv/               # virtual environment
```

---

## Scope discipline

Six columns, two export scripts, stop. A seventh feature before a month of daily
use = the avoidance trap. The product idea stays parked until it works for Dave.

---

## Build order

1. Write `SPEC.md` (this file).
2. Write `migrate.py` — convert `phrases.txt` → `chunks.csv`.
3. Refactor `generate.py` to read from `chunks.csv` and use single voice.
4. Refactor `generate_anki.py` to read from `chunks.csv`, use single voice,
   and resolve audio from `audio/` cache by row ID.
5. Update `.env.example` to reflect single voice config.
6. Put ten real chunks through end-to-end and verify the workflow.
7. Clean up legacy files.
