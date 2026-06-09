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

## 1. Reclassify, re-tag, and thin the chunk set  _(in progress)_

Goal: keep only chunks **I would actually say**, and make the `concept_tag`
taxonomy clear and well-documented.

**Effort/risk:** mostly trivial code, but heavy on *human review* — that's the real
cost. Lint gates correctness; the gotchas above are the only real traps.

- [ ] **Thin `chunks.csv`** — review every chunk, drop ones I wouldn't actually
  say. **This is hours of content review, not an engineering task** — judgment per
  phrase, ~667 rows. Deletion is one line; deciding is the job. Mind both gotchas
  above (Anki + audio orphans) for every row removed.
- [ ] **Re-tag** chunks to the right `concept_tag` — easy mechanically (one CSV
  cell), tedious by hand (judgment per row). First batch of MSA rows retagged,
  reviewed, lint-validated, and committed; more passes to come as thinning proceeds.
- [ ] **Document each tag with a description in `README.md`** — _trivial, ~30 min._
  The "Concept tags" section (README.md:97–112) currently lists tags as bare
  comma-separated names. Rework so every tag has a one-line description, kept per
  register-scheme (Situational / Topical).
- [ ] **Add missing tags** — _easy._ Candidates: `about_me`, `daily_life` (review
  for other gaps). Only real decision is which scheme/register each belongs to.
  Adding a tag means updating the **source of truth**, then mirroring to README:
  - `ConceptTag` enum in `scripts/generate.py` (~line 39)
  - `SITUATIONAL_TAGS` / `TOPICAL_TAGS` + `ALLOWED_TAGS_BY_REGISTER` (~line 69)
  - the README tag list + description
- [ ] **Validate** — run `kallim lint` (`.venv/bin/python cli.py lint`) after any
  taxonomy/CSV change; must report 0 problems.

## 2a. Remove the synthetic scene pipeline  _(do now — safe, self-contained)_

The generated scene conversations sound a bit off / unnatural. Safest move is to
remove the synthetic pipeline outright.

**Effort/risk:** **low, ~30–60 min.** `scene.py` is self-contained — nothing
imports it except a lazy `from scripts.scene import main` in `cli.py`.
`generate` / `anki` / `lint` are untouched by its removal.

- [ ] delete `scripts/scene.py` (347 lines — the whole generator)
- [ ] remove the `scene` subcommand from `cli.py` (parser ~71–87, dispatch ~135–137)
- [ ] strip scene references from `README.md` — feature bullet (line 13), usage
  examples (49–56), output-file listing (77–79), cache note (line 85), the
  `secondary` voice note (line 201)
- [ ] delete the `audio/scenes/` cache (~3.7M)
- [ ] if `secondary` voice is then unused, remove it from `voices.json`
- [ ] sweep `pyproject.toml` and `.claude/skills/extract-vocab/SKILL.md` for stray
  scene references

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
