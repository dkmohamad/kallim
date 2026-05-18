# Kallim

Bilingual TTS stitcher for Arabic language learning. Turns pre-translated English/Arabic phrase pairs into shadowing audio files.

Each MP3 plays: **English phrase → pause → Arabic phrase → longer pause** (time to shadow).

## Prerequisites

- Python 3.10+
- ffmpeg (`sudo apt install ffmpeg` or `brew install ffmpeg`)
- ElevenLabs API key + voice IDs

## Setup

```bash
pip install -r requirements.txt
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

## Output

For each section in `output/`:
- `01_section_name.mp3` — stitched audio
- `01_section_name.txt` — transcript
