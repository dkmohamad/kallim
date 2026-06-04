#!/usr/bin/env python3
"""Kallim scene — immersive audio scenes from vocab chunks.

Takes a section's chunks, uses Claude to arrange them into a dialogue script,
generates conversational audio via ElevenLabs Text to Dialogue API, adds
ambient background audio, and exports the final mixed MP3.
"""

import io
import json
import logging
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.types.dialogue_input import DialogueInput
from pydub import AudioSegment

from scripts.generate import (
    AUDIO_DIR,
    CHUNKS_CSV,
    Chunk,
    load_chunks,
    make_run_dir,
    normalize_audio,
    setup_logging,
)

logger = logging.getLogger("kallim")

SCENES_DIR = AUDIO_DIR / "scenes"

AMBIENT_PROMPTS: dict[str, str] = {
    "restaurant": "Busy restaurant ambience, soft chatter, clinking dishes",
    "cafe": "Cozy café background, espresso machine, quiet conversations",
    "market": "Bustling outdoor market, vendors calling, crowds",
    "street": "City street ambience, traffic, distant horns, footsteps",
    "airport": "Airport terminal, announcements, rolling luggage, distant chatter",
    "hotel": "Hotel lobby, soft music, quiet footsteps, reception bell",
    "beach": "Beach ambience, waves crashing, seagulls, distant voices",
    "home": "Quiet home interior, clock ticking, birds outside window",
}

# Maximum characters per text_to_dialogue request for reliable generation.
MAX_DIALOGUE_CHARS = 2000


def generate_script(
    chunks: list[Chunk],
    monologue: bool,
    section: str,
    setting: str,
) -> list[dict[str, str]]:
    """Use Claude to arrange chunks into a dialogue or monologue script."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        sys.exit("Error: ANTHROPIC_API_KEY not set. Check your .env file.")

    chunk_lines = []
    for c in chunks:
        chunk_lines.append(f"- Arabic: {c.arabic}\n  English: {c.english}")
    chunk_text = "\n".join(chunk_lines)

    style = "monologue (single speaker A)" if monologue else "dialogue (two speakers A and B)"

    prompt = (
        f"You are arranging Arabic vocabulary chunks into a natural {style} "
        f"set in a {setting}.\n\n"
        f"Here are the chunks to use:\n{chunk_text}\n\n"
        "Rules:\n"
        "1. Use EVERY chunk's Arabic text VERBATIM — do not modify the Arabic from the chunks.\n"
        "2. You may add short Arabic connectors between chunks (greetings, transitions, "
        "filler phrases) to make the conversation flow naturally. Keep connectors brief.\n"
        "3. Write full tashkeel (vowel diacritics) on any Arabic text you add.\n"
        "4. Provide an English translation for every line including connectors.\n"
        f"5. Output a JSON array of objects: "
        '{"speaker": "A"|"B", "arabic": "...", "english": "..."}\n'
        "6. Output ONLY the JSON array, no other text.\n"
    )
    if monologue:
        prompt += '7. Use only speaker "A" for all lines.\n'

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = response.content[0].text  # type: ignore[union-attr]

    # Parse JSON from response (handle markdown code fences)
    text = response_text.strip()
    if text.startswith("```"):
        # Remove opening fence (with optional language tag) and closing fence
        lines = text.split("\n")
        lines = lines[1:]  # drop opening ```json or ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    script: list[dict[str, str]] = json.loads(text)

    # Validate structure
    for line in script:
        if "speaker" not in line or "arabic" not in line or "english" not in line:
            sys.exit(f"Error: invalid script line from Claude: {line}")
        if line["speaker"] not in ("A", "B"):
            sys.exit(f"Error: invalid speaker '{line['speaker']}' in script")

    logger.info("Generated script with %d lines", len(script))
    return script


def generate_dialogue_audio(
    client: ElevenLabs,
    script_lines: list[dict[str, str]],
    voice_a: str,
    voice_b: str,
) -> bytes:
    """Generate conversational audio via ElevenLabs Text to Dialogue API.

    Splits into multiple requests if the script exceeds the character limit.
    """
    # Build DialogueInput list
    all_inputs = [
        DialogueInput(
            text=line["arabic"],
            voice_id=voice_a if line["speaker"] == "A" else voice_b,
        )
        for line in script_lines
    ]

    # Split into batches that fit within the character limit
    batches: list[list[DialogueInput]] = []
    current_batch: list[DialogueInput] = []
    current_chars = 0

    for inp in all_inputs:
        line_chars = len(inp.text)
        if current_batch and current_chars + line_chars > MAX_DIALOGUE_CHARS:
            batches.append(current_batch)
            current_batch = []
            current_chars = 0
        current_batch.append(inp)
        current_chars += line_chars

    if current_batch:
        batches.append(current_batch)

    logger.info(
        "Generating dialogue audio (%d lines, %d batch(es))",
        len(all_inputs),
        len(batches),
    )

    # Generate audio for each batch
    audio_segments: list[AudioSegment] = []
    for i, batch in enumerate(batches):
        logger.info("  Batch %d/%d (%d lines)", i + 1, len(batches), len(batch))
        audio_iter = client.text_to_dialogue.convert(
            inputs=batch,
            output_format="mp3_44100_128",
        )
        batch_bytes = b"".join(audio_iter)
        segment = AudioSegment.from_file(io.BytesIO(batch_bytes), format="mp3")
        audio_segments.append(segment)

    # Stitch batches with a short pause between them
    if len(audio_segments) == 1:
        combined = audio_segments[0]
    else:
        pause = AudioSegment.silent(duration=500)
        combined = audio_segments[0]
        for seg in audio_segments[1:]:
            combined = combined + pause + seg

    # Export combined audio to bytes
    buf = io.BytesIO()
    combined.export(buf, format="mp3", bitrate="128k")
    return buf.getvalue()


def generate_ambient(
    client: ElevenLabs,
    setting: str,
    ambient_file: str | None,
) -> Path:
    """Generate or load ambient background audio."""
    SCENES_DIR.mkdir(parents=True, exist_ok=True)

    if ambient_file:
        return Path(ambient_file)

    cached = SCENES_DIR / f"ambient_{setting}.mp3"
    if cached.exists():
        logger.info("Using cached ambient: %s", cached)
        return cached

    prompt = AMBIENT_PROMPTS.get(setting, setting)
    logger.info("Generating ambient audio: %s", prompt)

    try:
        audio_iter = client.text_to_sound_effects.convert(
            text=prompt,
            duration_seconds=30,
        )
        audio_bytes = b"".join(audio_iter)
    except Exception as e:
        sys.exit(
            f"Error: sound effects generation failed: {e}\n"
            "You can provide your own ambient file with --ambient-file instead."
        )

    cached.write_bytes(audio_bytes)
    logger.info("Cached ambient: %s", cached)
    return cached


def mix_scene(dialogue_bytes: bytes, ambient_path: Path) -> AudioSegment:
    """Overlay ambient audio onto dialogue at -25 dB."""
    dialogue = AudioSegment.from_file(io.BytesIO(dialogue_bytes), format="mp3")
    ambient = AudioSegment.from_file(str(ambient_path), format="mp3")

    # Loop ambient to match dialogue duration
    if len(ambient) < len(dialogue):
        repeats = (len(dialogue) // len(ambient)) + 1
        ambient = ambient * repeats
    ambient = ambient[: len(dialogue)]

    # Lower ambient volume relative to dialogue
    ambient = ambient - 25

    mixed = dialogue.overlay(ambient)
    return normalize_audio(mixed, target_dbfs=-20.0)


def write_scene_transcript(
    path: Path,
    script_lines: list[dict[str, str]],
    section: str,
    setting: str,
) -> None:
    """Write a human-readable transcript of the scene."""
    title = f"Scene: {section} ({setting})"
    lines = [f"=== {title} ===\n"]
    for idx, line in enumerate(script_lines, 1):
        speaker = f"Speaker {line['speaker']}"
        lines.append(f"{idx}. [{speaker}] {line['arabic']}")
        lines.append(f"   {line['english']}\n")
    path.write_text("\n".join(lines), encoding="utf-8")


def main(
    section: str,
    setting: str,
    monologue: bool = False,
    ambient_file: str | None = None,
) -> None:
    load_dotenv()

    # Set up output directory and logging
    run_dir = make_run_dir()
    setup_logging(run_dir)

    # Load and filter chunks
    chunks = load_chunks(CHUNKS_CSV)
    section_chunks = [c for c in chunks if c.concept_tag == section]
    if not section_chunks:
        sys.exit(f"Error: section '{section}' not found in chunks.csv")

    logger.info(
        "Scene: section=%s, setting=%s, %d chunks, monologue=%s",
        section,
        setting,
        len(section_chunks),
        monologue,
    )

    # Step 1: Generate script via Claude
    script_lines = generate_script(section_chunks, monologue, section, setting)

    base_name = f"scene_{section}_{setting}"
    script_path = run_dir / f"{base_name}.json"
    script_path.write_text(
        json.dumps(script_lines, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Saved script: %s", script_path)

    # Step 2: Generate dialogue audio via ElevenLabs
    el_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not el_key:
        sys.exit("Error: ELEVENLABS_API_KEY not set. Check your .env file.")
    el_client = ElevenLabs(api_key=el_key)

    voice_a = os.environ.get("ELEVENLABS_VOICE_MSA", "")
    if not voice_a:
        sys.exit("Error: ELEVENLABS_VOICE_MSA not set. Check your .env file.")

    voice_b = os.environ.get("ELEVENLABS_VOICE_B", "")
    if not voice_b:
        sys.exit("Error: ELEVENLABS_VOICE_B not set. Check your .env file.")

    dialogue_bytes = generate_dialogue_audio(el_client, script_lines, voice_a, voice_b)

    # Step 3: Generate ambient audio
    ambient_path = generate_ambient(el_client, setting, ambient_file)

    # Step 4: Mix dialogue + ambient
    final_audio = mix_scene(dialogue_bytes, ambient_path)

    # Export
    mp3_path = run_dir / f"{base_name}.mp3"
    final_audio.export(str(mp3_path), format="mp3", bitrate="128k")
    logger.info("Exported: %s", mp3_path)

    # Write transcript
    txt_path = run_dir / f"{base_name}.txt"
    write_scene_transcript(txt_path, script_lines, section, setting)
    logger.info("Transcript: %s", txt_path)

    logger.info("Done. Output in %s", run_dir)


if __name__ == "__main__":
    # Minimal CLI for direct invocation
    import argparse

    parser = argparse.ArgumentParser(description="Generate immersive audio scene")
    parser.add_argument("--section", required=True)
    parser.add_argument("--setting", required=True)
    parser.add_argument("--monologue", action="store_true")
    parser.add_argument("--ambient-file")
    args = parser.parse_args()
    main(
        section=args.section,
        setting=args.setting,
        monologue=args.monologue,
        ambient_file=args.ambient_file,
    )
