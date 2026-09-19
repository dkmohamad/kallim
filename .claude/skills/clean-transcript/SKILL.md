---
name: clean-transcript
description: >-
  Turn a raw ASR lesson transcript in the Notion Recordings database into a
  cleaned, vocalised, bilingual transcript that can be read instead of
  relistened to — and write it back to the Notion page. This is what
  `extract-vocab` requires as input. It does not produce a shadowable script or
  audio; for that, and for vocab harvested from the repair points, use
  `distil-lesson`, which reads the raw transcript instead.
user-invocable: true
argument-hint: "<recording title|date|url>"
allowed-tools:
  - Write
  - mcp__claude_ai_Notion__notion-fetch
  - mcp__claude_ai_Notion__notion-query-data-sources
  - mcp__claude_ai_Notion__notion-update-page
---

# Clean Transcript Skill

A raw recording page carries machine ASR: unvowelled, unpunctuated, speakers
labelled `SPEAKER S1` / `SPEAKER S2`, and no English. Unreadable as a study
artefact. This turns one into a transcript worth reading — and `extract-vocab`
refuses to run on anything else.

## Which skill you want

| Want | Use |
|---|---|
| A readable bilingual record of a lesson | this one |
| Vocab from a cleaned transcript | `extract-vocab` |
| A shadowable Arabic dialogue + audio, and vocab from the repair points | `distil-lesson` (reads the **raw** transcript) |

Cleaning and distilling are different jobs on the same recording, and they read
different sources on purpose. Cleaning merges a learner's broken attempts into
coherent sentences, which is right for reading and wrong for harvesting — the
broken attempt is the signal `distil-lesson` exists to catch.

## Steps

### 1. Find the recording

`$ARGUMENTS` names one lesson by title, date or URL. Query the Recordings data
source `collection://f409a1e9-2eb6-47df-be16-3e29ac2da44d`, then fetch with
`include_transcript: true`.

The database holds coaching and debugging sessions too. If it is not an Arabic
lesson, stop and say so.

### 2. Establish who is speaking — from content, not labels

**Diarisation swaps the speakers.** It has happened on a real lesson, and every
downstream judgement inherits the error: the student's broken attempts get
attributed to the teacher and mined as authentic.

Verify from the content. The student is the one being corrected. Feminine
address forms directed at the teacher (`تفهمينني`) confirm which voice is hers.
Only then assign labels.

**Name the teacher by role, never by name** — `**المعلِّمة:**`. Her name must not
appear in the transcript, the filename, or anything written back to Notion.

### 3. Write the cleaned transcript

To this format:

```
# <Arabic title> — <English title>

- **التاريخ:** YYYY-MM-DD
- **المصدر:** <link to the recording page>
- **ملاحظات التحرير:** <what you changed, in one line>

<the original English Summary block, unchanged>

## Transcript

### <Arabic section heading>

**المعلِّمة:** <Arabic, full tashkīl>

*<English translation>*

**ديفيد:** <Arabic, full tashkīl>

*<English translation>*
```

- The speaker label leads **inline** on the first sentence of a turn.
- An italic English translation goes under **each sentence**, not each turn —
  split long turns to keep the pairing one-to-one.
- Full tashkīl on the Arabic.
- Strip English asides and filler; merge word-by-word corrections into coherent
  sentences. That is the point of cleaning.
- Mark anything unrecoverable `[غير واضح]`. **Never invent** to fill a gap.

**Dialect stays dialect.** In an Egyptian lesson keep `عايز`, `بكام`, `ما ينفعش`
verbatim with Egyptian vocalisation — the dialect *is* the learning target
there, not an error to correct into Fuṣḥā.

Write it to `transcripts/YYYY-MM-DD-slug.md`. **That directory is gitignored**:
the transcripts are private lesson content and this repo is public.

### 4. Write it back to Notion

**Do not use `replace_content` on a page that has audio.** The recording page
carries an embedded `<audio>` block whose `src` is an internal
`file://attachment:` reference. It does not round-trip, so a full-page replace
**deletes the recording**.

Use `notion-update-page` with `command: "update_content"` and `content_updates`
(old_str → new_str) to replace only the summary and transcript text, leaving the
audio block untouched.

- `old_str` must match the fetched markdown **exactly**. Re-fetch first rather
  than working from what you wrote; do not condense; watch stray tashkīl
  (`ساعة وربع` against `وربعاً`).
- Split a long transcript into per-section updates. One oversized call times
  out, and a single bad match rejects the whole edit — smaller updates isolate
  the failure.
- A page with no audio can use `replace_content` directly.

### 5. Report

- The section count and how many turns each speaker has
- **Whether the speaker labels were swapped**, and how you determined it
- Every passage you marked `[غير واضح]`
- What you merged or dropped, since that is the judgement a reader inherits

## Guardrails

- **Never name the teacher** in any output.
- **Never invent Arabic** to smooth a gap — mark it unclear.
- **Never Fuṣḥā-fy dialect** in a dialect lesson.
- **Never `replace_content` a page with an audio block.**
- **Never commit `transcripts/`.** The repo is public.
