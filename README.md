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
python3 -m venv .venv
.venv/bin/pip install -e .
cp .env.example .env
# Edit .env with your API key and voice IDs
```

## Usage

```bash
# Generate shadowing audio for all sections
kallim generate

# Single section only
kallim generate --section cafe

# Custom pause duration (seconds, applied uniformly)
kallim generate --pause 3.0

# Generate Anki deck with audio
kallim anki

# Text-only Anki cards (no API calls)
kallim anki --no-audio

# List available ElevenLabs voices
kallim voices
```

## Output

Each run creates a timestamped directory under `output/` containing everything
from that run, flat:

```
output/
└── 20260603_141523/
    ├── 01_greetings.mp3
    ├── 01_greetings.txt
    ├── 02_smalltalk.mp3
    ├── 02_smalltalk.txt
    ├── kallim_arabic.apkg
    └── generate.log
```

Per-chunk audio is cached separately in `audio/` (keyed by chunk ID). If a
cache file is missing it gets regenerated on the next run.

## Data model

The source of truth is `chunks.csv` — one phrase pair per row:

```
id,arabic,english,register,concept_tag
0dc7e80b,السلام عليكم,Hello / Peace be upon you,egyptian,greetings
```

## Adding vocabulary

The vocab pipeline turns raw input (teacher chats, lesson notes) into
structured phrase pairs in `chunks.csv`:

0. **Transcribe** — if working from lesson recordings, transcribe first:
   ```bash
   ~/dev/scripts/transcribe/transcribe.sh --babel ~/recordings/lesson-dir/
   ```
   Uses the multilingual whisper model with auto language detection, handling
   mixed Arabic/English audio. The output `.txt` file can be fed into step 1.
1. **Extract** — read raw input and write `vocab_pairs.csv` (Arabic + English
   columns). Use the `/extract-vocab` skill or prepare the CSV manually.
2. **Promote** — `kallim promote` generates example sentences for single words
   (< 3 Arabic words) via the Claude API, writing `vocab_chunks_review.csv`.
   Phrase-length entries pass through unchanged.
3. **Review** — open `vocab_chunks_review.csv` and edit/delete as needed.
4. **Append** — copy approved rows into `chunks.csv`.
5. **Generate** — run `kallim generate` / `kallim anki` to produce audio and
   flashcards.

```bash
# Full pipeline example
kallim promote                     # writes vocab_chunks_review.csv
# ... review the file, then append to chunks.csv ...
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

### What happens on import

- **New cards** (IDs Anki hasn't seen) are added to the deck.
- **Existing cards** (IDs Anki already has) are left untouched — scheduling
  state is preserved. If you updated the English or Arabic text in the CSV,
  the card content will be updated.
- **No duplicates** — Anki deduplicates by note ID, which is deterministic.
- **Tags** are updated to match the current `concept_tag` values.

## Configuration

`.env` file:

```
ANTHROPIC_API_KEY=...
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ENGLISH=...
ELEVENLABS_VOICE_EGYPTIAN=...
ELEVENLABS_VOICE_MSA=...
ELEVENLABS_VOICE_IRAQI=...
```

## Claude Code skills

The project includes [Claude Code](https://claude.com/claude-code) skills in
`.claude/skills/` that automate common workflows:

| Skill | Invocation | What it does |
|-------|------------|--------------|
| **extract-vocab** | `/extract-vocab <file>` | Reads raw input (teacher chats, lesson notes, transcripts), extracts Arabic vocabulary, deduplicates against `chunks.csv`, writes `vocab_pairs.csv`, then runs `kallim promote` to generate example sentences. |
| **commit** | `/commit [message]` | Runs pyright type checks, stages files explicitly, shows the diff for approval, then commits. |
