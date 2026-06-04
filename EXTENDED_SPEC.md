# `kallim scene` — immersive audio scenes from vocab chunks

## Context

The generate pipeline works end-to-end (TTS per chunk → section MP3 + Anki deck). The next step is a richer output format: take a section's chunks and arrange them into a natural dialogue or monologue with ambient background audio, producing an immersive listening exercise.

## Approach

New command `kallim scene` that:
1. Uses Claude to arrange a section's chunks into a coherent dialogue script
2. Generates Arabic-only TTS per script line via ElevenLabs
3. Generates ambient background audio via ElevenLabs sound effects API
4. Mixes dialogue + ambient into a single MP3

## Implementation

### 1. `scripts/scene.py`

**Script generation (Claude API):**
- Load chunks for the section from `chunks.csv` (reuse `load_chunks` from `generate.py`)
- Send chunks to Claude with a prompt that arranges them into a dialogue (2 speakers) or monologue
- Claude must use chunk arabic text verbatim, may add short connectors (greetings, transitions)
- Output: JSON array of `{"speaker": "A"|"B", "arabic": "...", "english": "..."}`
- Save the script as JSON alongside the output for review/editing

**TTS generation:**
- Generate Arabic-only TTS per script line (reuse `generate_tts`, `normalize_audio` from `generate.py`)
- Speaker A → register voice (e.g. `ELEVENLABS_VOICE_MSA`)
- Speaker B → alternate voice via `--voice2` flag, or same voice if not provided
- Cache per-line audio in `audio/scenes/` keyed by hash of arabic text

**Ambient audio:**
- Use `client.text_to_sound_effects.convert()` (available in elevenlabs 2.46.0)
- Map settings to prompts: `"restaurant"` → `"Busy restaurant ambience, soft chatter, clinking dishes"`
- If setting isn't in the built-in map, use the string itself as the prompt
- Support `--ambient-file` to use a user-provided MP3 instead
- Cache ambient in `audio/scenes/ambient_{setting}.mp3`

**Mixing:**
- Stitch dialogue lines with ~1s pauses between turns
- Loop ambient to match dialogue duration
- Overlay ambient at -25 dB below dialogue (subtle background)
- Normalize final mix to -20 dBFS
- Export as MP3 128kbps

### 2. `scene` subcommand in `cli.py`

```
kallim scene --section food --setting restaurant [--monologue] [--voice2 ID] [--ambient-file path] [--pause 1.0]
```

Route to `scripts/scene.py:main()` using direct kwargs (like `promote` does), not the `_rebuild_argv` pattern.

### 3. Output structure

```
output/{timestamp}/
  scene_food_restaurant.mp3     # final mixed audio
  scene_food_restaurant.json    # generated script (reusable/editable)
  scene_food_restaurant.txt     # human-readable transcript
```

## Reused from `scripts/generate.py`

- `Chunk` (NamedTuple)
- `load_chunks(path)` → list of chunks
- `generate_tts(client, text, voice_id)` → bytes
- `normalize_audio(segment, target_dbfs)` → AudioSegment
- `load_voice_map()` → dict
- `setup_logging()`, `PROJECT_ROOT`, `AUDIO_DIR`, `OUTPUT_DIR`, `CHUNKS_CSV` constants
