---
name: shadow
description: >-
  Make an English-then-Arabic shadowing MP3 and publish its transcript to
  Notion. The source is either reading material (a YouTube or podcast
  transcript, a Notion page, a file, or pasted text), one topic from the
  chunk library (`--topic <slug>`), or the bank cards being learned in Anki
  (`--anki`). Each line plays English, a pause, then
  Arabic. Reading material is first written as a short-line transcript in
  `scratch/` for review, and nothing is spent on ElevenLabs until it is
  approved. Use it whenever English-then-Arabic audio to shadow is wanted. A
  recorded lesson becomes an Arabic-only conversation through `distil-lesson`
  instead, and new vocab goes into the bank through `extract-vocab`.
user-invocable: true
argument-hint: "<notion url | file path | pasted text> | --topic <slug> | --anki"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(uv run kallim *)
  - Bash(cp *)
  - Bash(rm *)
  - mcp__claude_ai_Notion__notion-fetch
  - mcp__claude_ai_Notion__notion-create-pages
  - mcp__personal__personal_drive_upload
  - mcp__personal__personal_drive_replace
  - mcp__personal__personal_drive_search
  - mcp__claude_ai_Notion__notion-update-page
---

# Shadow Skill

Shadowing in kallim always means one layout: English, a pause, Arabic, a pause,
line by line, rendered by `kallim shadow`. This skill makes that track from
any of three sources and ends the same way for all: one MP3 on Drive and one
transcript page in Notion that you read while you listen.

| Source | Argument | Where the lines come from |
|---|---|---|
| Reading material | a Notion URL, a file path, or pasted text | written by this skill and approved by you (steps 1–2) |
| The chunk library | `--topic <slug>` | rows of `chunks.csv` with that topic, already reviewed |
| What is being learned in Anki | `--anki` | rows whose Kallim cards are in learning or a review under 21 days (`--max-ivl`), one section per topic and register |

The rules every piece of voiced Arabic follows (numbers in words, never naming
the teacher, the dry-run gate, never `--force`) are in
[DESIGN.md](../../../DESIGN.md#rules-for-arabic-content). They apply here and
are not repeated.

## Steps

Follow these in order. Step 2 ends in a hard stop for reading material.

### 1. Get the source

- **`--topic <slug>`:** check the slug against `uv run kallim tags`, and go
  straight to step 3. The chunks are already in the bank and already reviewed.
- **`--anki`:** ask the user to open desktop Anki and let it sync from AnkiWeb
  first. Reviews happen on the phone, and the command reads the desktop
  collection, so without a sync it reads stale progress. Then go to step 3.
- **Otherwise** the argument is a Notion URL, a file path or the pasted text
  itself. Fetch a page with `notion-fetch`, or `Read` a file. If it is empty,
  ask. A YouTube or podcast transcript is reading material like any other.
- **The Arabic must already be right.** Step 2 copies it unchanged, so raw
  auto-captions (unvowelled, misheard, unpunctuated) would be voiced with their
  errors. If the Arabic isn't usable as it stands, stop and say so: it needs
  cleaning first (for a lesson, `/clean-transcript`).

### 2. Write the transcript, then stop

Write `scratch/<slug>-transcript.md` in the one transcript layout, which is the
layout the Notion page uses too:

```
# <Title>

## <Section>

1. Al-Mansur chose its site with care
   اِخْتَارَ الْمَنْصُورُ مَوْقِعَهَا بِعِنَايَةٍ
2. on the banks of the river Tigris.
   عَلَى ضِفَافِ نَهْرِ دِجْلَةَ.
```

Numbered pairs, English first and the Arabic beneath it, under short `##`
sections, and nothing else.

**What to leave out:**

- questions written for the teacher;
- literal word-order glosses;
- grammar notes and context notes;
- anything that repeats an earlier line, including target sentences that
  restate one.

What remains is what you will hear.

**The English is a spoken equivalent, as close to the Arabic as natural English
allows.** It is not the source's literal gloss. So:

- no `[brackets]` and no hyphenated word-by-word forms;
- keep the Arabic's order where English can bear it;
- write names so a voice can say them: Jaafar and al-Mamun, not Jaʿfar and
  al-Maʾmun.

**The Arabic is copied from the source unchanged, with two exceptions:**

- **Split long lines.** Cut anything over about six words at a phrase break, so
  each piece can be shadowed in one breath, and give each piece its own English.
  Keep the words a fragment needs for its grammar. `عَلَى يَدِ` stays with the
  caliph's name, because without it the genitive `أَبِي` has nothing governing
  it.
- **Numbers in words**, per the shared rules.

Write the `#` title and the `##` headings in English. Then **stop**. Report the line count, every line you split, and every change
you made to the Arabic. Wait for approval. The user may edit the file directly,
so re-read it before going on.

### 3. Dry run, then ask

```bash
uv run kallim shadow scratch/<slug>-transcript.md   # reading material
uv run kallim shadow --topic <slug>                 # a chunk topic
uv run kallim shadow --anki                         # what Anki is teaching
```

Without `--render` it spends nothing. It parses the transcript strictly and
refuses, naming the line, anything it can't voice correctly: a line outside the
layout, English and Arabic the wrong way round, a numbered line with no Arabic
beneath it, a digit in the Arabic. Fix the transcript and run it again.

**Report** the line count, the clips already cached, the characters and the
credits, then ask before rendering. A topic or the Anki track is usually cached
already, so it often costs nothing.

`--pause` (default 2.5 s) is the gap after each English and each Arabic clip,
which suits lines of about six words; the user may ask for longer.

### 4. Render

Run the same command with `--render`. It writes `output/<run>/<slug>.mp3` and
`output/<run>/<slug>.md`, the transcript in the same layout, numbered on across
sections. A line the voice provider refuses is left out whole and listed in the
command's output; report any.

### 5. Publish

- **Audio:** upload the MP3 to Drive (`Arabic/kallim/shadowing`) as
  `YYYY-MM-DD-<slug>.mp3`, staging it the way
  [distil-lesson](../distil-lesson/SKILL.md) step 5 describes.
- **Transcript:** create a Notion page under the Arabic hub
  (`374d9af2-a639-81ea-b3cc-f9a9656cb3f0`) titled `Shadowing — <Title>`. Its
  first line is `**Audio:** <link>`, then the rendered `<slug>.md` without its
  `#` title line (the title is the page's). Copy the rest unchanged: the tab
  before each Arabic line is what nests it under its English in Notion.
- **`--anki` is one rolling track, refreshed in place.** Search
  `Arabic/kallim/shadowing` for `learning.mp3`. If it exists, overwrite it with
  the Drive replace tool, so the link on the phone stays the same; upload it
  under that name only the first time. Likewise update the existing
  `Shadowing — <Title>` page (`notion-update-page`) rather than creating
  another. The name and title are fixed in `scripts/shadow.py`
  (`ANKI_TRACK_NAME`, `ANKI_TRACK_TITLE`), so they match on every run.
- **Report:** the page link, the duration, the credits spent, and any line
  that was left out.

## Fixing a line afterwards

Edit the transcript and render again. Clips are cached by voice and text, so
only the changed lines are billed; the dry run confirms it. A wrong chunk is
fixed in `chunks.csv` itself, not here.

## Boundaries

- **Never write or change code for this.** `kallim shadow` renders the layout.
  If something seems to need code, ask first.
- **Never edit the source** page or file. The user's notes there are theirs.
- **Never render before the transcript is approved** and the dry-run cost has
  been reported.
- **Never put reading-material lines into a bank.** They are not authentic
  chunks; `extract-vocab` is the way into the bank.
