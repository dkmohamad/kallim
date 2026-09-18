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
| `topic`        | string   | What the chunk is *about*: one registered slug. `TOPICS` (`scripts/model.py`) maps each to a description and is rendered by `kallim tags`; a value outside it is rejected on construction. Adding one costs a line there. Which topic is under current study is **not** a column — that is a syllabus question, answered by `--section`. |

### Example

```csv
id,arabic,english,register,topic,priority
0dc7e80b,السلام عليكم,Hello / Peace be upon you,egyptian,greetings,normal
2b8c6e03,ممكن أشوف المنيو الأول؟,Can I see the menu first?,egyptian,dining,normal
8c1b3a5e,أَنَا أَتَعَلَّمُ اللُّغَةَ الْعَرَبِيَّةَ,I am learning Arabic,msa,language,normal
f3a6ec53,قَاتَلَ أَبْنَاؤُهُ مَعَهُ فِي المَعْرَكَةِ,His sons fought alongside him in battle,msa,history,normal
```

### The two banks

`chunks.csv` holds the live MSA bank — drilled, rendered, added to. `egyptian.csv`
holds the Egyptian rows, frozen: its job is **reception** (songs, media, a future
trip), not production, so it is out of the default scope and reached with
`--input egyptian.csv`.

`kallim prune` reads **both**, and a missing bank is an error rather than an empty
contribution — otherwise every key only that bank produces would look orphaned and
`prune --apply` would delete audio that is still wanted.

### Why CSV

- The data is a flat table — CSV *is* a flat table.
- Version-controlled in git (diffs are readable row-by-row).
- Editable in any spreadsheet app or text editor.
- Python stdlib `csv` module — no extra dependency.
- Trivial to export to/from Google Sheets if that's ever wanted.

### Migration from phrases.txt

The existing `phrases.txt` (300+ phrases across 12 sections) will be migrated
to `chunks.csv`. The section names become the basis for `topic` or can be
embedded in the `id` prefix. Speaker labels (YOU:, STAFF:, etc.) are stripped
during migration.

---

## Single source of truth

The CSV owns **content**. Anki owns **scheduling state** ("do I know it") — and
that includes flagging a card as one you need to work on, which is why no flag is
ever synced back into the CSV. Never
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

Three of these consume the chunk bank; the fourth, lesson scripts, comes from a
different source and is listed here because it shares the audio machinery.

### 1. Shadowing audio

Long-form MP3s grouped by section. Turn-taking, recall-then-confirm — active
production. Correctly i+0 by design.

- Generated from `chunks.csv` rows filtered by register/topic.
- Output: `output/{section}.mp3` + `output/{section}.txt` transcript.

### 2. Anki cards with audio

Active recall / testing. Also i+0 by design.

- **Card template:** Front = English + English audio. Back = Arabic (RTL, large)
  + Arabic audio.
- **Incremental adds only.** Never delete-and-regenerate. Use AnkiConnect
  `addNote` to push single cards. Update by note ID.
- Anki keeps scheduling state; CSV keeps content.
- AnkiConnect requires desktop Anki running; AnkiWeb sync carries adds to mobile.

### 3. Lesson scripts (`kallim script`)

A recorded lesson distilled into a clean two-voice dialogue: shadowable Arabic
at conversation length, rather than isolated chunks. **Its source is a lesson
recording, not `chunks.csv`** — the same distillation pass also harvests chunks,
but the two outputs are independent and are not derived from each other.

- Input: a script page written to the convention in
  `.claude/skills/distil-lesson`, exported to markdown.
- Two voices in one dialect, so the voice is selected by `Speaker`, not
  `Register`. That is the reason the synthesiser depends on the `Speech` port
  rather than on `Utterance`.
- Arabic only. The English gloss is on the page for reading and is never voiced,
  so a script's credit cost is its Arabic character count.
- Cached in `audio-scripts/`, deliberately apart from `audio/`: `prune` deletes
  anything in `audio/` that no chunk produces, which would be every script clip.
- Output: `output/<run>/<name>.mp3` + a numbered transcript 1:1 with the page.

### 4. Podcast-style CI (future)

Passive listening — comprehensible input with scaffolding. The bank is a
to-learn pile, so the podcast generates *around* the chunks with settled
connective material, not just restitching them. Deferred until shadowing and
Anki are battle-tested.

---

## Pipeline

```
Scrappy inbox (recordings, notes, docs)
    ↓
    ├─────────────────────────────────────────┐
    ↓                                         ↓
chunks.csv (single source of truth)     lesson script page
    ↓                                         ↓
┌───────────────────┬──────────────────┐  ┌──────────────────┐
│ Shadowing audio   │ Anki cards       │  │ Script MP3       │
│ (active production)│ (active recall) │  │ (shadowing)      │
└───────────────────┴──────────────────┘  └──────────────────┘
```

One recorded lesson feeds both arms — chunks from its repair points, a script
from its substance — but each is distilled from the raw transcript directly.
Deriving the chunks from the finished script instead would lose every correction
the distillation smoothed away, which is the material worth keeping.

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

# List the registry of known topics and their descriptions
kallim tags

# Render a distilled lesson script into a two-voice MP3 (dry run by default)
kallim script scratch/damascus.md
kallim script scratch/damascus.md --render

# Delete orphaned audio (dry run; --apply to delete). Reads every bank.
kallim prune

# Validate chunks.csv (register is an enum, topic is a registered slug)
kallim lint

# List ElevenLabs voices
kallim voices

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
├── DESIGN.md              # this file
├── CLAUDE.md            # project instructions for Claude
├── README.md            # user-facing docs
├── chunks.csv           # THE source of truth (MSA)
├── egyptian.csv         # the frozen Egyptian bank
├── .env                 # API keys + ElevenLabs voice ids (gitignored)
├── .env.example         # template
├── scripts/             # all Python modules
│   ├── model.py         # domain types: Utterance, Chunk, Speaker, Speech
│   ├── chunks.py        # the chunks.csv loader and the Chunks collection
│   ├── cache.py         # content-addressed audio cache + mp3 codec
│   ├── audio.py         # ElevenLabs adapter, quota, stitching
│   ├── generate.py      # shadowing audio generation
│   ├── generate_anki.py # Anki deck generation
│   ├── script.py        # lesson script -> two-voice dialogue MP3
│   ├── ingest.py        # vocab candidates -> review-ready chunks
│   ├── lint.py          # bank validation
│   ├── plan.py          # dry-run cost reporting
│   ├── prune.py         # orphaned-audio deletion
│   └── tags.py          # the topic registry, rendered
├── audio/               # cached bank MP3s (content-addressed; prune walks this)
├── audio-scripts/       # cached script MP3s (prune never walks this)
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

1. Write `DESIGN.md` (this file).
2. Write `migrate.py` — convert `phrases.txt` → `chunks.csv`.
3. Refactor `generate.py` to read from `chunks.csv` and use single voice.
4. Refactor `generate_anki.py` to read from `chunks.csv`, use single voice,
   and resolve audio from `audio/` cache by row ID.
5. Update `.env.example` to reflect single voice config.
6. Put ten real chunks through end-to-end and verify the workflow.
7. Clean up legacy files.
