# Kallim

Arabic learning toolkit. Turns authentic material — lesson recordings, notes,
YouTube and podcast transcripts — into audio to listen to and shadow, Anki
cards to drill, and a structured chunk bank (`chunks.csv`) behind them.

## What do you want to do?

| I want to… | Do | Get |
|---|---|---|
| Shadow something I'm reading (YouTube, podcast, a text) | `/shadow <notion url \| file \| pasted text>` | An English → pause → Arabic MP3, and its transcript as a Notion page |
| Shadow a topic from my chunk library | `/shadow --topic <topic>` | The same, from the bank's rows on that topic |
| Listen to a lesson as a clean conversation | `/distil-lesson <recording>`, or `/distil-due` to pick the newest | An Arabic-only two-voice MP3 and a Notion page, plus vocab candidates from the lesson's corrections |
| Read a lesson instead of relistening to it | `/clean-transcript <recording>` | A cleaned bilingual transcript, written back to Notion |
| Grow or check the chunk bank | `/extract-vocab <source>`, `/review-chunks` | New rows in `chunks.csv`, uncommitted, for you to review |
| Drill cards | `uv run kallim anki` | An Anki deck (`.apkg`) to import |

Two words mean one thing each here:

- **Shadowing** is English, a pause, then Arabic, line by line. You say the
  Arabic in the pause, then hear it confirmed.
- **A lesson conversation** is Arabic only, in two voices, at conversation
  pace. It's for listening.

Every audio output has its transcript in Notion, so you read along while you
listen. The rules all of this Arabic follows are in
[DESIGN.md](DESIGN.md#rules-for-arabic-content).

## Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- ffmpeg (`sudo apt install ffmpeg` or `brew install ffmpeg`)
- An ElevenLabs API key and voice ids (see [Configuration](#configuration))

## Setup

```bash
uv sync
cp .env.example .env   # then add your API key and voice ids
npm install            # once per clone: the commit-message and pre-push hooks
```

What those hooks run, and why uv stays the toolchain, is in
[CLAUDE.md](CLAUDE.md#commits).

## Commands

```bash
# Shadowing audio, English → pause → Arabic (dry run unless --render)
uv run kallim shadow scratch/baghdad-transcript.md   # an approved transcript
uv run kallim shadow --topic dining --render         # one bank topic, for real

# Every topic at once, one MP3 each (for a long listen)
uv run kallim generate                        # every topic in chunks.csv
uv run kallim generate --input egyptian.csv   # the other bank
uv run kallim generate --pause 3.0            # gap after each side, in seconds
uv run kallim generate --dry-run              # what it would cost; nothing spent

# Anki deck (same --input, --section and --dry-run)
uv run kallim anki
uv run kallim anki --no-audio                 # text-only cards, no API calls

# A distilled lesson page → two-voice Arabic MP3 (dry run unless --render)
uv run kallim script scratch/damascus.md
uv run kallim script scratch/damascus.md --render

# The chunk bank
uv run kallim harvest scratch/vocab_pairs.csv # dedup, id, validate, append, lint
uv run kallim lint                            # or: uv run kallim lint egyptian.csv
uv run kallim tags                            # the registered topics

# Housekeeping
uv run kallim prune                           # orphaned audio; --apply deletes
uv run kallim voices                          # voice ids on your account
```

`--force` (on `generate`, `anki` and `script`) re-synthesises everything and
bills it all again. It's almost never what you want: see
[Output](#output) for when the cache is wrong.

## Output

Each run creates one timestamped directory under `output/`, flat:

```text
output/
└── 20260603_141523/
    ├── 01_greetings_msa.mp3     # shadowing audio: <nn>_<topic>_<register>
    ├── 01_greetings_msa.md      # its transcript, English then Arabic
    ├── 02_smalltalk_msa.mp3
    ├── 02_smalltalk_msa.md
    ├── kallim_arabic.apkg
    └── generate.log
```

A `shadow` run writes `<slug>.mp3` and `<slug>.md`, named after its source; a
`script` run writes `<page-name>.mp3` and a numbered `.txt`. Every shadowing
transcript has one layout: numbered pairs, English then Arabic, under `##`
sections.

Clip audio is **content-addressed**: each side of a chunk is cached in `audio/`
as `<content-hash>.mp3`, the hash of its voice and text. A present file is
therefore correct by construction. Editing a chunk's English or Arabic changes
the hash, so the next run synthesises only the changed side and leaves the old
file behind; identical text shares one file. The hash doesn't cover the voice
id in `.env`, the model, or any voice setting, so changing one of those needs
`--force`. [DESIGN.md](DESIGN.md#speech-rate) has the detail. It
also covers speech rate, which nothing in this repo sets.

Bracketed notes in a row's text that are for the reader, such as `(lit. …)`
or `(n.)`, are shown but not said; cues such as `(female)` are said.
[DESIGN.md](DESIGN.md#what-the-voice-says) has the rule.

Removing or editing a row leaves orphaned clips. `uv run kallim prune` lists
them and `--apply` deletes them. Anki cards for deleted rows are **not** removed
this way; see [Removing vocabulary](#removing-vocabulary).

## Data model

The source of truth is `chunks.csv`, one chunk per row:

```csv
id,arabic,english,register,topic,priority
0dc7e80b,السلام عليكم,Hello / Peace be upon you,egyptian,greetings,normal
```

### Topic

**`topic`** is what the chunk is *about*: one slug, lowercase with underscores,
**registered** in `TOPICS` (`scripts/model.py`). Adding one costs a line there.

It's checked rather than free because an unregistered value is far more often a
typo than a new dossier, and an unnoticed typo silently splits a section, drops
rows from `--section`, and opens a second Anki namespace. `kallim harvest` fails
loudly on one, naming the topic and saying what to do.

**What is *not* a column:** which topic you are currently studying. That is a
property of the syllabus, not of a chunk: `--section history` is how you drill
it, and when the focus moves nothing about a row changes.

Nor is "I need to learn this" a column. The CSV owns **content** and Anki owns
**scheduling state** ([DESIGN.md](DESIGN.md#single-source-of-truth)); flagging a
card is Anki's job and is never synced back. `priority` is a different kind of
claim, true of the chunk whether or not you know it yet, so it belongs here; the
[chunk-review rubric](.claude/agents/chunk-review.md#4-priority) defines it.

`kallim lint` validates a whole bank. Per row: the register and priority must be
enum members and the topic must be registered. Across rows: no duplicate ids, and no
two rows whose Arabic folds to the same identity once diacritics are stripped.
That check lives in lint rather than in harvest because a row can reach the bank
by several routes, and a check guarding only one of them guards nothing.

It doesn't judge whether the topic is *right*; that's
[`/review-chunks`](#claude-code-skills).

### The two banks

| File | What it is |
|---|---|
| `chunks.csv` | MSA. The live bank: drilled, rendered, added to. |
| `egyptian.csv` | Egyptian, frozen. Kept for **reception** (songs, media, a future trip), not production. |

`generate`, `anki` and `lint` default to `chunks.csv`; reach the frozen bank
with `--input egyptian.csv` (or as `lint`'s argument).

`kallim prune` reads **both**, so freezing a bank never makes its audio look
orphaned. Reading-material shadowing clips are in neither bank, so they are
cached apart in `audio-shadow/`, which prune never walks.

## Adding vocabulary

Chunks come from **authentic** Arabic only: a teacher's own phrases or entries
you captured yourself. Nothing is synthesised, and there's one way in:

1. **Source:** a **cleaned** Notion lesson transcript, the Notion *Arabic —
   Scratchpad* page, or a local text file.
2. **Extract:** [`/extract-vocab <source>`](#claude-code-skills). A Sonnet sub-agent pulls the
   teacher-said and teacher-corrected chunks, assigns each a register and topic,
   and writes `scratch/vocab_pairs.csv`.
3. **Harvest:** `uv run kallim harvest` dedups against `chunks.csv` (ignoring
   diacritics), assigns ids, validates, appends the survivors and lints the
   result. No API calls, no invented text.
4. **Review:** the rows are in `chunks.csv` **uncommitted**, so `git diff` is the
   review surface. `/review-chunks --new` puts the judgement agent over them;
   `git checkout chunks.csv` throws a bad batch away.
5. **Commit** when the diff reads right, then `generate` or `anki` as needed.

[`/distil-lesson`](#claude-code-skills) feeds the same harvest from a recording's
corrections.

## Anki workflow

The deck is a disposable render target: `chunks.csv` is the source of truth and
Anki owns scheduling state. You can re-export and re-import at any time.

### Importing

1. `uv run kallim anki`.
2. In Anki desktop, **File > Import** the `.apkg` from the latest run directory.

- **New cards** (ids Anki hasn't seen) are added.
- **Existing cards** keep their review history, intervals and ease. If you
  changed a row's English or Arabic, the card's content updates.
- **No duplicates:** each note's id is derived from the chunk's `id`.
- **Tags** follow the current `topic` and `priority`.

### Removing vocabulary

Deleting a row from `chunks.csv` leaves two things behind:

- **The Anki card.** genanki and Anki only ever *add or update* notes, so a
  removed chunk's card stays in your collection until you delete it by hand
  (search its English, Arabic or tag). That is unlikely to be automated:
  deleting cards from a collection Anki owns isn't the CSV's business.
- **Its cached audio**, which `kallim prune --apply` clears.

### Troubleshooting: duplicate or orphaned tags in AnkiDroid

If tags appear both as a flat list and as a nested tree (e.g. `cafe` and
`topic::cafe`), stale tags from an earlier import need clearing. From the deck
list, open the three-dot menu at the top right and choose **Check → Check
database**. That removes tags no longer attached to any note.

## Configuration

API keys **and voice ids** live in `.env` (gitignored); see `.env.example`:

```ini
ELEVENLABS_API_KEY=...

ELEVENLABS_VOICE_ENGLISH=...    # the bank voices: English, and one per register
ELEVENLABS_VOICE_EGYPTIAN=...
ELEVENLABS_VOICE_MSA=...
ELEVENLABS_VOICE_IRAQI=...

ELEVENLABS_VOICE_TEACHER=...    # the two lesson-conversation voices
ELEVENLABS_VOICE_DAVID=...
```

One convention, `ELEVENLABS_VOICE_<MEMBER>`, covers both: a `Register` picks a
bank voice and a `Speaker` picks a conversation voice. A missing one is reported
up front, naming the variable, rather than failing part-way through a paid run.
`uv run kallim voices` lists the voice ids on your account.

## Claude Code skills

The skills live in `.claude/skills/`. Which one to reach for is the table at
[the top](#what-do-you-want-to-do); this is what each does.

| Skill | Invocation | What it does |
|-------|------------|--------------|
| **shadow** | `/shadow <source>` or `/shadow --topic <topic>` | Makes English → pause → Arabic shadowing audio from reading material or a bank topic, and publishes its transcript to Notion. Reading material stops for your approval of a short-line transcript before anything is spent. |
| **distil-lesson** | `/distil-lesson <recording>` | Turns one recorded lesson into an Arabic-only two-voice conversation page and MP3, and harvests vocab candidates from its corrections, in one pass over the **raw** transcript. |
| **distil-due** | `/distil-due` | Checks whether a recorded lesson is waiting and hands the newest to `distil-lesson`. Answers in one line when there is nothing new; a session-start hook nudges after a few days. |
| **clean-transcript** | `/clean-transcript <recording>` | Turns a raw lesson transcript into a cleaned, vocalised, bilingual one and writes it back to Notion. `extract-vocab` reads these. |
| **extract-vocab** | `/extract-vocab <source>` | Mines authentic chunks from a cleaned transcript, the Scratchpad or a text file, then `kallim harvest` appends them to `chunks.csv`, uncommitted. |
| **review-chunks** | `/review-chunks --topic history` | Audits a slice of a bank for what `kallim lint` can't judge: drifted topic, unearned priority, a gloss that doesn't match, frames trapped in sentences, cards too long to drill. Proposes with reasons; never edits a bank. |

Commits go through the `casomoltd:commit` plugin skill, not a skill in this
repo.
