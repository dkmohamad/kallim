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

# Validate chunks.csv against the concept_tag taxonomy
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
changes in `voices.json`).

Both removing a row and editing one leave orphaned files (the old hash is no
longer produced by any chunk). Run `kallim prune` to list them and
`kallim prune --apply` to delete. Note Anki cards are **not** removed this way —
genanki only adds/updates notes, so cards for deleted chunks must be removed by
hand in Anki.

## Data model

The source of truth is `chunks.csv` — one phrase pair per row:

```
id,arabic,english,register,concept_tag
0dc7e80b,السلام عليكم,Hello / Peace be upon you,egyptian,greetings
```

### Concept tags

`concept_tag` is drawn from the `ConceptTag` taxonomy (`scripts/generate.py`),
split into two register-scoped schemes. `greetings` is shared; otherwise a
tag belongs to one scheme only.

Run `kallim lint` to check every row against the taxonomy; it fails on an
unknown register/tag or a tag used outside its register's scheme.

#### Situational (`egyptian` — travel-phrasebook situations)

| Tag | Description |
|---|---|
| `greetings` | Hellos, goodbyes, and first-contact phrases |
| `smalltalk` | Light conversation: origins, impressions, compliments |
| `dining` | Ordering food and drinks, asking about dishes, paying the bill |
| `hotel` | Check-in/out, room requests, facilities |
| `taxis` | Hailing, negotiating fares, giving directions to a driver |
| `directions` | Asking for and giving directions on foot |
| `sightseeing` | Visiting attractions, booking trips, asking about places |
| `beach_and_vendors` | Beach vendors, hiring equipment, water safety |
| `shopping` | Market bargaining, asking about stock, sizes, and prices |
| `money` | Prices, change, payment |

#### Topical (`msa` / `iraqi` — conversation topics)

| Tag | Description |
|---|---|
| `greetings` | Hellos, goodbyes, and first-contact phrases (shared with Situational) |
| `food` | Specific dishes, ingredients, cooking, eating preferences |
| `travel` | Trips, transport, navigation, accommodation |
| `people` | Describing or talking about other people; social interactions |
| `family` | Immediate and extended family; family relationships and gatherings |
| `emotions` | Feelings, reactions, opinions, agreement and disagreement |
| `leisure` | Hobbies, sports, nature, free time, weather as backdrop |
| `daily_life` | Everyday routines: waking, meals, commuting, habits |
| `culture` | Religion, traditions, language learning, cultural observations |
| `work` | Jobs, meetings, projects, professional life |
| `health` | Fitness, diet, illness, medical appointments |

## Adding vocabulary

The vocab pipeline mines **authentic** Arabic — a teacher's own phrases or
entries you captured yourself — into `chunks.csv`. Nothing is synthesised.

1. **Source** — one of: a **cleaned** Notion lesson transcript (named speakers
   + English glosses, written back to Notion), the Notion *Arabic — Scratchpad*
   page, or a local text file.
2. **Extract** — run the `/extract-vocab <source>` skill. A Sonnet sub-agent
   pulls high-authority chunks (teacher-said or teacher-corrected), tags each by
   register + concept, and writes `vocab_pairs.csv`.
3. **Ingest** — `kallim ingest vocab_pairs.csv` dedups against `chunks.csv`
   (diacritics-insensitive), assigns ids, validates the taxonomy, and writes
   `vocab_chunks_review.csv`. No API calls, no invented text.
4. **Review** — open `vocab_chunks_review.csv` and edit/delete as needed.
5. **Append + validate** — `kallim ingest --append` commits the reviewed rows
   into `chunks.csv`, then `kallim lint` checks the taxonomy.
6. **Generate** — run `kallim generate` / `kallim anki` to produce audio and
   flashcards.

```bash
# From a review CSV onward
kallim ingest vocab_pairs.csv      # dedup + id + validate -> review CSV
# ... review vocab_chunks_review.csv ...
kallim ingest --append             # commit reviewed rows into chunks.csv
kallim lint                        # validate concept_tags
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

## Troubleshooting

### Duplicate or orphaned tags in AnkiDroid

If you see tags appearing both as a flat list and as a nested tree (e.g. `cafe`
and `topic::cafe`), stale tags from a previous import need clearing. From the
main menu (decks), tap the three-dot menu in the top right and select
**Check → Check database**. This removes orphaned tags that are no longer
attached to any notes.

## Configuration

API keys live in `.env` (gitignored):

```
ELEVENLABS_API_KEY=...
```

Voice IDs live in `voices.json` (committed):

```json
{
  "english": "...",
  "egyptian": "...",
  "msa": "...",
  "iraqi": "..."
}
```

- `english`, `egyptian`, `msa`, `iraqi` — per-register TTS voices for
  shadowing audio and Anki decks.

Run `kallim voices` to list available ElevenLabs voice IDs.

## Claude Code skills

The project includes [Claude Code](https://claude.com/claude-code) skills in
`.claude/skills/` that automate common workflows:

| Skill | Invocation | What it does |
|-------|------------|--------------|
| **extract-vocab** | `/extract-vocab <source>` | Mines authentic Arabic chunks from a cleaned Notion transcript, the Scratchpad, or a text file (Sonnet sub-agent), then `kallim ingest` dedups, ids, and validates them into `vocab_chunks_review.csv`. |
| **commit** | `/commit [message]` | Runs pyright type checks, stages files explicitly, shows the diff for approval, then commits. |
