# Kallim

Bilingual TTS stitcher for Arabic language learning. Turns pre-translated English/Arabic phrase pairs into shadowing audio files.

Each MP3 plays: **English phrase → pause → Arabic phrase → longer pause** (time to shadow).

## Prerequisites

- Python 3.10+
- ffmpeg (`sudo apt install ffmpeg` or `brew install ffmpeg`)
- ElevenLabs API key + voice IDs

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API key and voice IDs
```

## Usage

```bash
# List available voices to find voice IDs
python generate.py --list-voices

# Generate audio for all sections
python generate.py --input phrases.txt

# Single section only
python generate.py --input phrases.txt --section survival_egyptian

# Custom output dir and pause durations
python generate.py --input phrases.txt --output ./my_audio --pause-after-english 2.0 --pause-after-arabic 4.0

# Slow down Arabic audio for easier shadowing (0.25-4.0, default 1.0)
python generate.py --input phrases.txt --arabic-speed 0.8
```

## Input Format

```
# section_name

1. English phrase here
   Arabic phrase here

2. Another English phrase
   Another Arabic phrase
```

## Anki Flashcard Deck

Generate an Anki `.apkg` file with audio on both sides of each card.

```bash
# Generate full deck with audio (uses ElevenLabs API)
python generate_anki.py

# Single section only
python generate_anki.py --section cafe_egyptian

# Text-only cards, no audio (free, good for testing)
python generate_anki.py --no-audio
```

Cards show English on the front (with English audio) and Arabic on the back (with Arabic audio, large RTL text). Each card is tagged by section for filtered study.

Audio files are cached in `anki_audio/` so re-runs don't re-call the API.

Import the generated `kallim_egyptian_arabic.apkg` into Anki.

## Output

For each section in `output/`:
- `01_section_name.mp3` — stitched audio
- `01_section_name.txt` — transcript
