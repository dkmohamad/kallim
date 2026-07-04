# TODO

Tracking in-flight work on the kallim chunk set and pipeline.

## Startup performance — lazy-dispatch in cli.py  _(recommended, not done)_

`pydub` and `elevenlabs` are already fully deferred: `audio.py` (synth, `stitch`)
and `store.py` (the `AudioCache` `Codec`) lazy-import pydub inside the methods
that use it, and `audio.py` lazy-imports elevenlabs in `make_synthesiser` /
`list_voices` (`PLC0415` per-file-ignored in both — the one sanctioned deviation
so far). `generate.py` is pydub-free: it composes `PlayableAudio` via
`audio.stitch` and writes via the store `Codec` (`make_codec`). So no command
loads them on startup.

The remaining cost is `cli.py`: it imports all six command `main`s at module
top, so running *any* command transitively loads **`genanki`** (via
`generate_anki.py`) and **`anthropic`** (via `promote.py`) whether needed or not.
Measured: `kallim lint` ≈ **0.46 s** vs ≈ **0.03 s** for importing the `lint`
module alone — almost all of the gap is anthropic + genanki.

**Next stage:** lazy-dispatch — move each `from scripts.<cmd> import main` into
its `if args.command == …` branch in `cli.py`, so e.g. `lint`/`prune`/`voices`/
`migrate` import only what they use (≈ 0.1 s; a ~0.35 s win per invocation). Cost:
a second `PLC0415` per-file-ignore (`"cli.py"`). Deferred deliberately to keep
the lazy-import deviation list short.

## ⚠️ Gotchas to remember (read before thinning chunks)

Deleting a row from `chunks.csv` is **not** fully self-contained. The CSV is the
source of truth for *generation*; the tail has mostly been automated, but one
manual step remains:

1. **Anki keeps orphaned cards.** genanki/Anki only *add or update* notes by GUID
   on import — they never delete. So a chunk removed from `chunks.csv` leaves its
   card alive in the Anki collection. Removing it means **manually deleting that
   card in Anki** (search by the English/Arabic text, or by tag). _Still manual —
   no automation for this._
2. **Orphaned audio files — now handled by `kallim prune`.** Audio is cached per
   chunk as `audio/{id}_en.mp3` / `{id}_ar.mp3`. Deleting a row leaves those files
   behind. `kallim prune` lists them (dry run) and `kallim prune --apply` deletes
   any `audio/{id}_*.mp3` whose `id` is gone from `chunks.csv`, and drops the dead
   `manifest.json` entries.
3. **Stale-but-live audio — now handled by the content-aware cache.** The cache
   used to short-circuit on `id` alone (content-blind), so a chunk edited in place
   (the أقام hotel fix, the female→first-person/male reframes, the
   third-person→first/second reframes) kept serving its **old** audio forever.
   `generate`/`anki` now record a text hash per side in `audio/manifest.json`, so
   an edited chunk regenerates only the changed side on the next run. `--force`
   overrides the cache (e.g. after a `voices.json` change the hash can't see).
   - **One-time cost:** the manifest starts empty, so the *next* full
     `generate`/`anki` run regenerates everything once (~756×2 TTS calls) to seed
     it and clear all current staleness; every run after that is incremental.
     Scope with `--section` to spread the cost.

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
- [x] **Validate** — `kallim lint` reports 0 problems (756 chunks as of the
  authentic-chunk additions; was 655 at the time of the thin/re-tag pass).

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
  reuse the existing Claude-API path (`scripts/promote.py`, the `/extract-vocab`
  skill, and the "Adding vocabulary" flow in README).
- **Audio → per-chunk clips: hard.** Playing *this chunk's* authentic audio needs
  ASR (transcription) **plus forced alignment** for chunk-level timestamps — and
  Arabic forced alignment is genuinely fiddly. ElevenLabs is TTS, not STT, so this
  is new infrastructure (Whisper-class model + alignment), not a refactor.

- [x] **Decide ambition level** — went with the text-first MVP (no per-chunk audio).
- [x] **Text → chunks** — done ad hoc: **101 authentic chunks** ingested from three
  MSA lesson transcripts via the existing extract/promote path (commit `47f4316`).
  These are now live in `chunks.csv` and lint-clean.
  - ⚠️ Those 101 chunks have **no generated audio yet** — they need a
    `generate`/`anki` run (folds into the one-time regen noted in gotcha #3).
- [ ] **Attach whole source-audio file** — the still-open half of the MVP: pair each
  ingested batch with its (whole) source recording so you can practice the chunks
  *and* listen back to the authentic audio. Not built.
- [ ] **Later (optional):** per-chunk audio via ASR + forced alignment, only if the
  whole-file approach proves insufficient.

## 3. Regeneration & output-sync workflow

Two related pain points around regenerating and getting audio onto my phone.
**3a (cache correctness) is now done; 3b (output sync) is still flagged.**

### 3a. Regenerate only what changed (cache correctness)  _(done)_

Both pain points are resolved by the content-aware cache + `prune`:

- [x] **Content-aware cache** — `get_or_generate_chunk_audio` now records a text
  hash per side in `audio/manifest.json` (`{id: {en, ar}}`); the `ar` key folds in
  the register. An edited chunk regenerates only the changed side; unedited chunks
  stay cached. `generate --force` / `anki --force` overrides the cache. Both
  commands share the one function, so both paths are covered.
- [x] **`kallim prune`** — new subcommand (`scripts/prune.py`): dry-run by default,
  `--apply` deletes orphan `audio/{id}_*.mp3` files and dead manifest entries.
  Cleared the 126 orphans.

The chosen design (content-aware cache + prune) supersedes the "full fresh regen"
and "prune orphans only" options that were on the table. The one residual cost is
the seed regen noted in gotcha #3 — a single full run after which everything is
incremental.

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

- §1 (re-tag/thin), §2a (remove scene pipeline) **done** (`fa40600`); §2b text→chunks
  MVP **done** ad hoc (`47f4316`, 101 authentic chunks); §3a (cache correctness)
  **done** (content-aware cache + `kallim prune`).
- **Operational, not yet run:** the one-time seed regen — `kallim generate` /
  `kallim anki` to (a) clear current stale audio and (b) give the 101 new authentic
  chunks their audio. Costs ElevenLabs credits; scope with `--section` to spread it.
- **Still open:** §2b "attach whole source-audio file" half, and §3b (incremental
  output + Google Drive `rsync`/rclone sync — still flagged, not started).
