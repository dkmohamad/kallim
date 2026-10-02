---
name: shadow-text
description: >-
  Turn a piece of Arabic reading material into a bilingual shadowing MP3. The
  material can be a Notion page, a video script or pasted text, usually with
  literal translation notes. Each line plays English, a pause, then Arabic. It
  first writes a short-line transcript to `scratch/` for review, and spends
  nothing on ElevenLabs until that transcript is approved. Use it when asked for
  English-then-Arabic audio to shadow from a text. For a recorded lesson, use
  `distil-lesson`, which makes an Arabic-only dialogue track. For vocab cards,
  use `extract-vocab`.
user-invocable: true
argument-hint: "<notion url | file path>"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(uv run kallim *)
  - Bash(mv *)
  - mcp__claude_ai_Notion__notion-fetch
---

# Shadow Text Skill

This takes Arabic text and makes one MP3 that plays English, a pause, Arabic and
another pause, line by line, using `kallim generate` on a CSV of pairs.
Everything it writes goes to `scratch/` and `output/`. A recorded lesson goes to
[distil-lesson](../distil-lesson/SKILL.md) instead, and vocab cards to
[extract-vocab](../extract-vocab/SKILL.md).

## Steps

Follow these in order. Step 2 ends in a hard stop.

### 1. Fetch the source

`$ARGUMENTS` is a Notion URL or a file path. If it is empty, ask. Fetch the page
with `notion-fetch`, or `Read` the file.

### 2. Write the transcript, then stop

Write `scratch/<slug>-transcript.md`. It holds numbered pairs under short `##`
section headings, and nothing else:

```
# <Title>

## <Section>

1. Al-Mansur chose its site with care
   اِخْتَارَ الْمَنْصُورُ مَوْقِعَهَا بِعِنَايَةٍ
2. on the banks of the river Tigris.
   عَلَى ضِفَافِ نَهْرِ دِجْلَةَ.
```

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
- **Write numbers in words, never digits.** The rule is in
  [extract-vocab](../extract-vocab/SKILL.md).

Then **stop**. Report the line count, every line you split, and every change
you made to the Arabic. Wait for approval. The user may edit the file directly,
so re-read it before going on.

### 3. Build the CSV from the approved transcript

Convert the transcript mechanically into `scratch/<slug>.csv`, one row per
numbered line. Use a CSV writer, because the English contains commas.

- **Header:** the columns of `Chunk.FIELDS` in
  [model.py](../../../scripts/model.py), which is
  the `chunks.csv` format that `generate --input` reads.
- **id:** a short prefix plus the line number (e.g. `bgd001`).
- **register:** `msa`.
- **topic:** one slug from `uv run kallim tags`.
- **priority:** `normal`.

The CSV is a render input only (see Boundaries).

### 4. Dry run, then ask

```bash
uv run kallim generate --input scratch/<slug>.csv --pause 2.5 --dry-run
```

**What `--pause` does:** it sets one gap that follows both the English and the
Arabic. The default here is 2.5 s, which suits lines of about six words; the
user may ask for longer. **Report** the clip count, the characters and
the credits, then ask before rendering.

### 5. Render

```bash
uv run kallim generate --input scratch/<slug>.csv --pause 2.5
```

- **Rename the output.** `generate` names the run's `.mp3` and `.txt` after the
  section, not the source, so rename both to `<slug>`.
- **Check `generate.log` for refused text.** A content-policy refusal skips a
  clip rather than failing the run, so the log is the only place it shows up.
- **Report:** the path, the duration, the credits spent, and any clip that was
  skipped.

## Fixing a line afterwards

Make the same edit to the transcript and the CSV, then render again. Clips are
cached by voice and text, so only the changed lines are billed. Run the dry run
first to confirm that. Keep the clips cached until then (see Boundaries).

## Boundaries

- **Never write or change code for this.** `kallim generate` already renders
  the layout. If something seems to need code, ask first.
- **Never edit the source** page or file. The user's notes there are theirs.
- **Never call ElevenLabs before the transcript is approved** and the dry-run
  cost has been reported.
- **Never run `kallim harvest` on the CSV.** These are reading-material lines,
  not authentic chunks, and they do not belong in the bank.
- **Never use `--force`.** It re-bills every line to fix one.
- **Never run `kallim prune --apply` while these clips are wanted.** They are
  cached in `audio/`, but their rows are not in any bank, so prune deletes them
  as orphans and the next render re-bills every line.
- **Never name the teacher** in any output. The repo is public and the lessons
  are private, so she appears only as "the teacher".
