---
name: distil-lesson
description: >-
  Turn one recorded Arabic lesson into a shadowable script — a readable
  Arabic-only dialogue page in Notion plus a two-voice MP3 — and harvest the
  repair points as vocab candidates in the same pass. Reads the RAW transcript
  from the Notion Recordings database, never the cleaned one.
user-invocable: true
argument-hint: "<recording title|date|url>"
allowed-tools:
  - Read
  - Write
  - Bash(.venv/bin/kallim *)
  - Bash(uv run kallim *)
  - mcp__claude_ai_Notion__notion-fetch
  - mcp__claude_ai_Notion__notion-search
  - mcp__claude_ai_Notion__notion-query-data-sources
  - mcp__claude_ai_Notion__notion-create-pages
  - mcp__claude_ai_Notion__notion-update-page
---

# Distil Lesson Skill

A recorded lesson is 50–80 minutes of hesitation, code-switching and repair.
Unlistenable as it stands — which is why 25 recordings sit unplayed. This turns
one into **8–15 minutes of clean Arabic you can shadow**, and harvests the
vocabulary in the same pass.

## The rule that shapes everything

**Read the RAW transcript. Never the cleaned one.**

Cleaning merges a learner's broken attempts into coherent sentences — and the
broken attempt *is* the signal. Once `تَكَشَّفْتُ` has been tidied into
`اِكْتَشَفْتُ`, there is no longer a correction to detect, just two people
talking fluently. Clean-then-extract silently discards the highest-value
chunks in the lesson.

So: one pass over the raw, three outputs. Not two passes.

A cleaned transcript is also **not a neutral copy** — it is a set of judgements
someone already made. In one lesson the cleaned version resolved a wobbling poem
attribution to a single poet; the raw shows the teacher naming a different one.
Distilling from the clean version inherits those calls invisibly.

## Steps

Follow these in order. Do NOT skip or reorder.

### 1. Find the recording

`$ARGUMENTS` names one lesson by title, date, or Notion URL. If empty, ask.

Query the Recordings data source
`collection://f409a1e9-2eb6-47df-be16-3e29ac2da44d` to find it, then fetch the
page with `include_transcript: true`.

The raw transcript is `SPEAKER S1:` / `SPEAKER S2:`, unvowelled, with ASR
errors. **Verify who is who from the content, not the labels** — diarisation
swaps them sometimes. The student is the one being corrected.

Expect junk: ASR bleed from unrelated recordings, mangled proper nouns
(`جزار قباني` for `نزار قبّاني`), and stray English. Ignore it.

### 2. Harvest the repair points — before you distil anything

Work through the raw and mark every moment the student was stuck. These are
the chunks; the script is the by-product.

| `signal` | What happened | Value |
|---|---|---|
| `correction` | Student produced something; teacher reformulated it | Highest — a thing he meant to say and couldn't |
| `elicitation` | Student asked how to say something; teacher demonstrated | Highest — a gap he noticed himself |
| `confirmation` | Student produced something; teacher affirmed it | Medium |
| `introduced` | Teacher brought in new material unprompted | Lower |

Also take the **connective layer**, which is not a repair and is easy to miss:
discourse operators (`يَعْنِي`, `أَيْضًا`, `إِذَنْ`, `مَثَلًا`, `فِي الوَاقِعِ`),
stance markers (`أَعْتَقِدُ أَنَّ`, `بِالنِّسْبَةِ لِي`), and repair phrases
(`كَيْفَ أَقُولُ …؟`, `مَا مَعْنَى …؟`). Take them even when they are one word
mid-turn. The bank is starved of these and full of content sentences.

Write candidates to `scratch/vocab_pairs.csv` in `VocabEntry.FIELDS` order.
Run `.venv/bin/kallim tags` first for the live topic registry — an unregistered
topic is rejected by ingest.

### 3. Distil the script

Now write the dialogue, to the page convention below.

**Strip:** lesson mechanics (screen-sharing, "did you prepare something",
scheduling), filler, repetition, and anything the transcript marks unclear.
Gaps never become dead air.

**Elevate the student's turns** into the Arabic he was reaching for. This is
most of the work, not a tidy-up — expect to compose rather than correct, and
expect that to dominate the effort.

**Keep the teacher's turns close to what she said**, regularised to Fuṣḥā only
where she slipped. Her Arabic is the evidence; do not improve it.

**Keep instructive exchanges as dialogue.** A correction the student needed
(`كَبِير فِي السِّنّ` → `عَرِيقَة`) is worth hearing in the script, not just in
the harvest.

**Never name the teacher.** She is `المعلِّمة` in the speaker label and
`يَا أُسْتَاذَة` in address. Never her real name, anywhere, in any output.

**Flag what the lesson did not settle.** A disputed etymology, a wobbling
attribution, a fact that sounded uncertain: leave it out of the script and note
it at the foot of the page. Do not resolve it by picking one. Also note every
uncorrected slip you fixed — those are your edits, not hers.

### 4. The page convention

```
# <Arabic title> — سِيَنَارْيُو الدَّرْس (YYYY-MM-DD)

- **التاريخ:** YYYY-MM-DD
- **المصدر:** <link to the recording page>
- **الوضع:** dialogue
- **الحالة:** draft
- **المتحدّثون:** ديفيد · المعلِّمة

## <section heading>

### **المعلِّمة:** <Arabic, full tashkīl>

*<English gloss>*
```

- One `H3` per turn. The `**Name:**` prefix is **load-bearing** — it selects the
  voice. Only `المعلِّمة` and `ديفيد` are known; any other label is a parse error.
- The italic gloss beneath is **required**. `kallim script` refuses a turn
  without one rather than dropping it silently, because a missing gloss is
  almost always a half-written block.
- `H2` is a section marker: a longer gap, no speech.
- A turn containing `[...]` is written for the reader and never voiced.
- Page order is audio order. No reordering — that is what "follow along" means.

Write it to `scratch/<slug>.md` **and** create the Notion page under the Arabic
hub (`374d9af2-a639-81ea-b3cc-f9a9656cb3f0`) with the same content.

### 5. Voice it

Local only — this step needs the repo and an ElevenLabs key.

```bash
uv run kallim script scratch/<slug>.md            # what it costs, nothing spent
uv run kallim script scratch/<slug>.md --render   # synthesise and stitch
```

The dry run is the spend gate: it reports turns per speaker, how many are
already cached, and the exact credit cost of the rest. **Report that before
spending.** Expect 6–8k characters for a 50-minute lesson, and 10–15 minutes of
audio. Editing one turn on the page re-bills only that turn.

The two voices are `ELEVENLABS_VOICE_TEACHER` and `ELEVENLABS_VOICE_DAVID` in
`.env`; the clips cache in `audio-scripts/`, which `prune` never walks.

Then upload to Drive (`Arabic/kallim/scripts`, named `YYYY-MM-DD-<slug>.mp3`)
and put the link on the page as `**الصوت:**`. The Drive tool only reads from
the records root, so stage a copy there and delete it afterwards.

### 6. Report

- Blocks and sections, and how many turns each speaker has
- Characters and credits spent
- **The repair points found**, by signal
- **Every content edit you made** and every fact you declined to assert

## What this skill must never do

- **Distil from a cleaned transcript.** See the top of this file.
- **Name the teacher** in any output: page, script, audio, candidates, notes.
- **Assert a fact the lesson left open**, or silently resolve a contradiction.
- **Harvest chunks from the finished script.** The script is a listening
  artefact; chunks come from the repair points in the raw. Same recording, two
  outputs, two provenance rules.
- **Append to `chunks.csv`.** Candidates go through `kallim ingest` and wait for
  review, same as any other batch.

## Known costs

Two lessons distilled by hand before this skill existed:

| | Raw turns | Blocks | Characters | Audio |
|---|---|---|---|---|
| Golden Age, 82 min | 115 | 54 | 4,185 | 7m45 |
| Damascus, 54 min | 121 | 86 | 7,532 | 13m59 |

The second was longer from a shorter lesson — block count tracks how much of the
lesson was substantive Arabic, not its duration. Do not estimate from minutes.

Both were distilled by hand before this skill existed, and the rendering half is
now `kallim script` (`scripts/script.py`, with tests). Rendering Damascus through
the promoted command reproduced the hand-built track exactly, 13m59, so the
figures above are a live baseline rather than a record of something that changed.
