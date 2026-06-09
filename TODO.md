# TODO

Tracking in-flight work on the kallim chunk set and pipeline.
_Status: tools down for now — this file is the cold-start capture to resume from._

## ⚠️ Gotchas to remember (read before thinning chunks)

Deleting a row from `chunks.csv` is **not** self-contained. The CSV is the source
of truth for *generation*, not for *pruning what already exists*:

1. **Anki keeps orphaned cards.** genanki/Anki only *add or update* notes by GUID
   on import — they never delete. So a chunk removed from `chunks.csv` leaves its
   card alive in the Anki collection. Removing it means **manually deleting that
   card in Anki** (search by the English/Arabic text, or by tag).
2. **The audio cache keeps orphaned files.** Audio is cached per chunk as
   `audio/{id}_en.mp3` and `audio/{id}_ar.mp3`, keyed by `id`. Deleting a row
   leaves those files behind — dead weight that accumulates in `audio/`.
   - _Worth building:_ a small `kallim prune` (or a flag on `lint`) that deletes
     any `audio/{id}_*.mp3` whose `id` no longer appears in `chunks.csv`. Until
     then, orphaned audio just sits there (harmless but messy).

Net: the *deciding* is the work; the *deletion* has a tail (Anki + audio) that
won't clean itself up.

## 1. Reclassify, re-tag, and thin the chunk set  _(done)_

Goal: keep only chunks **I would actually say**, and make the `concept_tag`
taxonomy clear and well-documented.

- [x] **Thin `chunks.csv`** — reviewed and dropped chunks I wouldn't actually say
  (Anki + audio orphan gotchas above apply to any future removals).
- [x] **Re-tag** chunks to the right `concept_tag` — MSA/Egyptian passes completed,
  reviewed, and lint-validated.
- [x] **Document each tag with a description in `README.md`** — every tag now has a
  one-line description, split per register-scheme (Situational / Topical).
- [x] **Add missing tags** — added `family` and `daily_life` to the `ConceptTag`
  enum, tag-scheme sets, and README.
- [x] **Validate** — `kallim lint` reports 0 problems (655 chunks).

## 2a. Remove the synthetic scene pipeline  _(done)_

The generated scene conversations sounded a bit off / unnatural, so the synthetic
pipeline was removed outright. `generate` / `anki` / `lint` were untouched.

- [x] delete `scripts/scene.py`
- [x] remove the `scene` subcommand from `cli.py` (parser + dispatch)
- [x] strip scene references from `README.md` (feature bullet, usage examples,
  output-file listing, cache note, `secondary` voice note)
- [x] delete the `audio/scenes/` cache
- [x] remove the now-unused `secondary` voice from `voices.json` /
  `voices.json.example`, and `Register.SECONDARY` from `generate.py`
- [x] hoist `cli.py`'s lazy subcommand imports to module top-level (cleared a
  pre-existing `PLC0415` ruff failure) and dropped the now-needless per-file-ignore
  from `pyproject.toml`; the `PLC0415` rule now enforces top-level imports project-wide
- [x] reword the three descriptive "travel-phrasebook scenes" mentions
  (`generate.py`, `README.md`, `SKILL.md`) → "situations", since they describe the
  Egyptian situational register, not the deleted pipeline, and "scenes" is now ambiguous

## 2b. Authentic-chunk ingestion  _(design first — this is the hard part)_

Replace synthetic scenes with chunks derived from **real (truth-data) audio or
text**, so everything practiced is authentic. Practice the chunks + listen to the
authentic audio for deeper understanding.

**Effort/risk depends entirely on one decision — per-chunk audio clips or not:**

- **Text → chunks: moderate.** Segmenting real text into chunks is very doable;
  reuse the existing Claude-API path (`scripts/promote.py`, `scripts/extract_vocab.py`,
  and the "Adding vocabulary" flow in README).
- **Audio → per-chunk clips: hard.** Playing *this chunk's* authentic audio needs
  ASR (transcription) **plus forced alignment** for chunk-level timestamps — and
  Arabic forced alignment is genuinely fiddly. ElevenLabs is TTS, not STT, so this
  is new infrastructure (Whisper-class model + alignment), not a refactor.

- [ ] **Decide ambition level first** (this gates everything below).
- [ ] **Recommended MVP** — sidestep the hard half: chunk the **text** for practice
  and attach the **whole source-audio file** (not per-chunk clips). Still authentic
  chunks + authentic audio; defer ASR/alignment until per-chunk clips are actually
  wanted. Turns the "hard half" into "moderate."
- [ ] **Later (optional):** per-chunk audio via ASR + forced alignment, only if the
  whole-file approach proves insufficient.

## Loose ends right now

- Working tree clean as of down-tools. The hotel-card fix (أقام) is committed
  (`79c0ff1`); the first batch of MSA `concept_tag` re-tags is lint-validated and
  committed alongside this TODO. Resume from the checklists above.
