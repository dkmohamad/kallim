# TODO

In-flight work on the kallim chunk set and pipeline. **Open** is live,
**Backlog** is decided-but-not-needed, **Done** is kept only for the reasoning
that stops a rejected option being re-proposed.

Behaviour that is true of the tool rather than pending belongs in `README.md`
and `DESIGN.md`, not here — what a deleted row leaves behind, how the
content-addressed cache decides what to regenerate, and what `kallim prune`
removes are all in README under *Output* and *Anki workflow*.

## Open

- **Lazy-dispatch in `cli.py`.** `pydub` and `elevenlabs` are already fully
  deferred (`audio.py`, `cache.py`, `script.py` lazy-import them, `PLC0415`
  per-file-ignored for exactly that). What remains is `cli.py` importing every
  command module at the top, so any command transitively loads `genanki` via
  `generate_anki.py`: `kallim lint` ≈ 0.46 s against ≈ 0.03 s for the `lint`
  module alone. Moving each import into its dispatch branch wins ~0.35 s per
  invocation and costs a second per-file-ignore. Deferred to keep the
  lazy-import deviation list short.
- **Attach the source recording to an ingested batch**, so a chunk can be
  drilled *and* heard in the voice that said it. Per-chunk clips are the harder
  version and are not wanted yet: they need ASR plus forced alignment for
  chunk-level timestamps, Arabic forced alignment is fiddly, and ElevenLabs is
  TTS not STT — new infrastructure rather than a refactor. Revisit only if the
  whole-file approach proves insufficient.
- **Incremental output and Drive sync.** Every `kallim generate` writes a new
  timestamped `output/` directory even when one section changed, and getting it
  onto a phone is a manual full-folder copy. Wanted: rebuild only the sections
  whose chunks changed, and sync with `rsync`/rclone so only changed files move.

## Backlog

- **An `examples` field.** Ellipsis frames stay the drillable row, and the
  sentence a frame was lifted from rides along on the Anki card back. Settled
  during the 2026-09 history repointing and not built, so a frame and its parent
  sentence are currently two unrelated rows and the card gives the frame with no
  context. Needs a column on `Chunk`, a `lint` rule (an example must not itself
  be a row), and a card-template change.
- **`kallim export` / `apply-edits`.** Some rows were mined from
  corrected-ChatGPT MSA and read as stilted. Making them idiomatic is a
  qualitative judgement, better done interactively in claude.ai than by an agent
  here — so **do not build a "teacher review" skill**. The only friction worth
  tooling is the round-trip: `export --section <topic>` to a pasteable table,
  `apply-edits` to read back `id → new_arabic` and edit in place by id. Editing
  by id is safe because the Anki GUID is `genanki.guid_for(chunk.id)`, so a card
  updates rather than orphaning, and the cache regenerates only the changed side.
  Never Fuṣḥā-fy Egyptian. Build it only if the manual round-trip proves
  annoying, which is a thing to find out rather than assume.
- **An optional era tag.** All Arab/Islamic history sits under one `history`
  topic. Splitting it per era was built and removed as unnecessary: it made every
  row carry a syllabus judgement, and nothing needs to drill one era apart from
  another. If that changes, reach for an *optional* second label, empty for most
  rows — not a required column or a re-tag of the bank.
- **Hash the full synthesis parameter set into the cache key.** The key is
  `content_hash(voice + text)` and nothing else — not the model, not the output
  format, not any voice setting, and not even the voice *id* (it hashes the
  register or speaker *name*, so swapping `ELEVENLABS_VOICE_MSA` in `.env`
  changes nothing). Anything that alters the bytes but not the text therefore
  leaves every cached clip in place and silently wrong: you change a setting,
  nothing regenerates, and you conclude it had no effect. README currently warns
  about the voice-id case and `--force` is the only escape.

  The fix is to include everything that determines the audio — model id, output
  format, resolved voice id and any voice settings — in the hashed string.

  **Do it with a re-key migration, not a re-render.** A naive change invalidates
  all 2,454 cached clips and costs roughly **75,000 credits** to rebuild both
  banks. Instead compute each row's new key under the *current* parameters and
  rename the existing file to it: the bytes are already correct, only the name
  is wrong. That is exactly how the 83 teacher clips were re-keyed when the
  speaker key moved from a name to a role — 83 renames, zero credits.

  Worth doing before any synthesis parameter is added, not after. Adding `speed`
  first and the key second means paying for the rebuild twice.

## Done

- **Reclassified, re-tagged and thinned the chunk set.** `concept_tag` became
  `topic`; the two-value `tag` that briefly joined it was removed again.
  `DESIGN.md` has the live schema.
- **Removed the synthetic scene pipeline** rather than tuning it — the generated
  conversations sounded unnatural, and the answer was real lesson material, not
  better prompts.
- **Ingested the text half of authentic chunks** — 101 from three MSA lesson
  transcripts (`47f4316`), without per-chunk audio.
- **Content-addressed the audio cache and added `kallim prune`**, superseding
  the two options on the table: a file named by the hash of its own text is
  correct by construction, so neither a full fresh regen nor prune-orphans-only
  is needed. `prune` reads every bank, so freezing a register cannot make its
  audio look deletable. An `audio/manifest.json` design was written up here for
  months and never built.
