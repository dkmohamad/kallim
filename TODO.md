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
`generate_anki.py`) whether needed or not. (The old `anthropic` load via
`promote.py` is gone — `promote` was retired and its LLM work moved into the
`/extract-vocab` skill.) Measured historically: `kallim lint` ≈ **0.46 s** vs
≈ **0.03 s** for importing the `lint` module alone.

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
   *utterance*, content-addressed as `audio/<hash>.mp3`. Removing or editing a row
   leaves its old file behind. `kallim prune` lists orphans (dry run) and
   `--apply` deletes them, counting a key live if **any** bank still produces it.
3. **Stale-but-live audio — handled by content-addressing.** The cache is keyed
   by a hash of the utterance's text, so a present file is correct by construction:
   editing a chunk changes its key and the next run synthesises the new side. There
   is no manifest and no staleness to clear. (Earlier revisions of this file
   described an `audio/manifest.json` and a one-time seed regen of ~756×2 calls —
   neither exists. `audio/` holds 2063 content-hash mp3s covering every current
   chunk bar one, plausibly the `ContentBlockedError` case in `3a92dd2`.)

## 1. Reclassify, re-tag, and thin the chunk set  _(done; schema since replaced)_

Goal: keep only chunks **I would actually say**, and make the tag taxonomy
clear and well-documented.

> Historical. The `concept_tag` column described below was renamed to `topic`
> and a two-value `tag` (`history`/`general`) added; `ConceptTag` and its two
> schemes are gone. Left as the record of what was done at the time — see
> README and DESIGN.md for the live schema.

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
  use the `/extract-vocab` skill (a Sonnet sub-agent extracts + tags authentic
  chunks in-Claude, then `kallim harvest` dedups/ids/validates/appends) and the "Adding
  vocabulary" flow in README.
- **Audio → per-chunk clips: hard.** Playing *this chunk's* authentic audio needs
  ASR (transcription) **plus forced alignment** for chunk-level timestamps — and
  Arabic forced alignment is genuinely fiddly. ElevenLabs is TTS, not STT, so this
  is new infrastructure (Whisper-class model + alignment), not a refactor.

- [x] **Decide ambition level** — went with the text-first MVP (no per-chunk audio).
- [x] **Text → chunks** — done ad hoc: **101 authentic chunks** ingested from three
  MSA lesson transcripts via the extract → ingest path (commit `47f4316`).
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

- [x] **Content-addressed cache** — each utterance's audio is stored at
  `audio/<hash of register + text>.mp3`, so a present file is correct by
  construction: editing a chunk changes its key and only the changed side is
  synthesised next run. `--force` re-synthesises regardless. _(An intermediate
  design using `audio/manifest.json` was described here; it was superseded by
  content-addressing and no manifest exists.)_
- [x] **`kallim prune`** — new subcommand (`scripts/prune.py`): dry-run by default,
  `--apply` deletes any `audio/<key>.mp3` no bank still produces. Cleared the
  126 orphans. Reads **every** bank (`chunks.csv` + `egyptian.csv`), so freezing
  a register can't make its audio look deletable.

The chosen design (content-addressed cache + prune) supersedes the "full fresh
regen" and "prune orphans only" options that were on the table. The seed regen
this section once warned about has long since run: `audio/` holds 2063 clips
covering every current chunk bar one.

### 3b. Incremental output + Google Drive sync

Current friction: every `kallim generate` writes a **new timestamped `output/`
directory**, even when only one section changed. I then manually copy the whole
thing to Google Drive to access recordings/text from my phone.

Wanted (someday):
- Regenerate **only sections whose chunks changed** (and update the Anki deck only
  when needed), rather than a full rebuild into a fresh dir each time.
- **Sync to Google Drive via `rsync`** (or rclone for Drive) so only changed files
  transfer — no manual full-folder copy.

## Backlog: an optional era tag  _(not needed yet)_

All Arab/Islamic history sits under one `history` topic. Splitting it per era —
`andalus`, `ottoman`, `golden_age` — was built and then removed as unnecessary:
it made every row carry a judgement that belongs to the syllabus, and nothing
currently needs to drill one era apart from another.

If that changes, the shape to reach for is an **optional** second label, empty
for most rows, rather than a required column or a re-tag of the bank. Worth
having only when there is a real reason to slice `history` — not before.

## Loose ends right now

- §1 (re-tag/thin), §2a (remove scene pipeline) **done** (`fa40600`); §2b text→chunks
  MVP **done** ad hoc (`47f4316`, 101 authentic chunks); §3a (cache correctness)
  **done** (content-aware cache + `kallim prune`).
- **Still open:** §2b "attach whole source-audio file" half, and §3b (incremental
  output + Google Drive `rsync`/rclone sync — still flagged, not started).
