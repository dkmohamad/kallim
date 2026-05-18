# Arabic Audio Learning Tool — Spec

## Purpose

Generate bilingual shadowing audio files for Arabic language learning. Each file plays an English phrase, a pause, then the Arabic equivalent, allowing the learner to listen and shadow. Output is organised by topic into separate MP3 files with matching transcripts.

---

## Overview

A CLI tool that:
1. Reads a structured input file containing English phrases grouped by topic
2. Calls the Anthropic API to generate Arabic translations (MSA or Egyptian dialect, configurable per section)
3. Calls the ElevenLabs API to generate audio for each phrase (English + Arabic)
4. Stitches audio into one MP3 per section with configurable silence gaps
5. Outputs MP3 files + plain text transcripts

---

## Input Format

YAML file. Each section has a name, a dialect/register setting, and a list of English phrases.

```yaml
sections:
  - name: survival_egyptian
    dialect: egyptian  # or: msa
    phrases:
      - How much does this cost?
      - Where is the bathroom?
      - I would like a taxi please.
      - Do you speak English?
      - Can I have the bill please?

  - name: restaurant_egyptian
    dialect: egyptian
    phrases:
      - A table for two please.
      - What do you recommend?
      - I don't eat meat.
      - This is delicious.
      - Can I have some water?

  - name: everyday_msa
    dialect: msa
    phrases:
      - I work in technology.
      - I live in London.
      - I am learning Arabic.
```

---

## Output

For each section, two files are written to an `output/` directory:

- `01_survival_egyptian.mp3`
- `01_survival_egyptian.txt`
- `02_restaurant_egyptian.mp3`
- `02_restaurant_egyptian.txt`
- etc.

Files are prefixed with a zero-padded index matching their order in the YAML.

### Audio Structure Per Phrase

```
[English TTS] → [pause_after_english] → [Arabic TTS] → [pause_after_arabic]
```

Configurable silence durations (see Config below).

### Transcript Format

```
=== Survival Egyptian ===

1. How much does this cost?
   بِكَام ده؟

2. Where is the bathroom?
   فين الحمام؟

...
```

---

## Arabic Generation

- Anthropic API (`claude-sonnet-4-20250514`)
- System prompt instructs the model to return only the Arabic phrase — no transliteration, no explanation, no diacritics for Egyptian dialect (natural written form), full diacritics (تشكيل) for MSA
- Dialect is passed per section
- One API call per phrase (simple, debuggable) or batched — implementer's choice

### System Prompt (Egyptian)

```
You are an Egyptian Arabic dialect expert. The user will give you an English phrase. 
Return only the Egyptian colloquial Arabic equivalent — natural spoken form as a native 
Egyptian would say it. No transliteration. No explanation. No punctuation beyond the phrase itself.
```

### System Prompt (MSA)

```
You are a Modern Standard Arabic expert. The user will give you an English phrase.
Return only the MSA Arabic equivalent with full diacritics (تشكيل). 
No transliteration. No explanation. No punctuation beyond the phrase itself.
```

---

## ElevenLabs TTS

Two voices required — one English, one Arabic. Both configured via environment variables.

| Variable | Description |
|---|---|
| `ELEVENLABS_API_KEY` | ElevenLabs API key |
| `ELEVENLABS_ENGLISH_VOICE_ID` | Voice ID for English phrases |
| `ELEVENLABS_ARABIC_VOICE_ID` | Voice ID for Arabic phrases (Egyptian or MSA accent) |
| `ANTHROPIC_API_KEY` | Anthropic API key |

ElevenLabs model: `eleven_multilingual_v2` (supports Arabic).

---

## Configuration

Top-level config block in the YAML (optional, all have defaults):

```yaml
config:
  pause_after_english: 1.5      # seconds
  pause_after_arabic: 3.0       # seconds (longer — time to shadow)
  output_dir: ./output
  audio_format: mp3
```

---

## CLI Interface

```bash
python generate.py --input phrases.yaml
python generate.py --input phrases.yaml --output ./my_output
python generate.py --input phrases.yaml --section survival_egyptian  # single section only
python generate.py --list-voices  # list available ElevenLabs voices and exit
```

---

## Dependencies

```
anthropic
elevenlabs
pydub
pyyaml
python-dotenv
```

`ffmpeg` must be installed on the system (required by pydub for MP3 encoding).

`.env` file for API keys:
```
ANTHROPIC_API_KEY=...
ELEVENLABS_API_KEY=...
ELEVENLABS_ENGLISH_VOICE_ID=...
ELEVENLABS_ARABIC_VOICE_ID=...
```

---

## Error Handling

- If Anthropic API call fails for a phrase: log the error, skip the phrase, continue
- If ElevenLabs call fails: retry once, then skip and log
- If a section has zero successful phrases: skip MP3 generation, log warning
- All errors written to `generate.log`

---

## Project Structure

```
arabic-audio/
├── generate.py          # main entry point
├── phrases.yaml         # input phrases
├── .env                 # API keys (gitignored)
├── requirements.txt
├── output/              # generated MP3s and transcripts
└── README.md
```

---

## Notes for Implementer

- Test ElevenLabs Arabic voice quality before committing to a voice ID — run `--list-voices` and sample a few
- Egyptian dialect: the Arabic text will not have diacritics — this is intentional
- Silence gaps are generated as raw PCM silence via pydub, not a separate TTS call
- MP3 bitrate: 128kbps is sufficient for speech
- The transcript is the source of truth — generate it even if audio generation fails
