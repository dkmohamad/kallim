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
   - Current count: **126 orphans** (63 thinned chunks × 2 files) vs 655 live
     chunks × 2 = 1310 expected (1436 total in `audio/`).
3. **The audio cache is content-blind — edited chunks serve STALE audio.** The
   cache key is *only* the `id`; `generate` short-circuits when both
   `{id}_en.mp3`/`{id}_ar.mp3` exist (`generate.py:251`), never checking whether
   the text changed. IDs are random `uuid4`, not content-derived. So any chunk
   whose Arabic/English was **edited in place** (e.g. the أقام hotel fix, the
   female→first-person/male reframes, the third-person→first/second reframes —
   ~30+ live rows) keeps its **old** audio forever. Pruning orphans does **not**
   fix this. See §3.

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

## 3. Regeneration & output-sync workflow  _(flagged — not started, don't build yet)_

Two related pain points around regenerating and getting audio onto my phone.
Capturing now; **no work to be done on this yet.**

### 3a. Regenerate only what changed (cache correctness)

Right now there's no clean way to "regenerate the content" after editing chunks:

- **Stale-but-live cache** (gotcha #3 above): edited chunks keep old audio because
  the cache is keyed by `id` alone, content-blind. The reframed/أقام rows are
  currently serving stale audio.
- **Orphans** (gotcha #2): 126 dead files from thinned chunks.

Options considered (pick later):
- **Full fresh regen** — wipe `audio/` entirely, regenerate all from `chunks.csv`.
  Simplest, guarantees correctness, highest ElevenLabs cost (~655 × 2 TTS calls).
- **Content-aware cache + prune** — fold a hash of the chunk's text into the cache
  key (or a sidecar manifest) so edits auto-invalidate, then prune stale/orphan
  files and regenerate only what changed. Durable; less recurring cost; more code.
- **Prune orphans only** — frees space but leaves edited rows stale (insufficient
  for a true content refresh).

### 3b. Incremental output + Google Drive sync

Current friction: every `kallim generate` writes a **new timestamped `output/`
directory**, even when only one section changed. I then manually copy the whole
thing to Google Drive to access recordings/text from my phone.

Wanted (someday):
- Regenerate **only sections whose chunks changed** (and update the Anki deck only
  when needed), rather than a full rebuild into a fresh dir each time.
- **Sync to Google Drive via `rsync`** (or rclone for Drive) so only changed files
  transfer — no manual full-folder copy.

## Loose ends right now

- §1 (reclassify/re-tag/thin) and §2a (remove scene pipeline) are **done and
  committed** (`fa40600`). Working tree clean.
- Next up is §2b (authentic-chunk ingestion, design-first) and §3 (regen/sync —
  flagged only, do not start yet).
