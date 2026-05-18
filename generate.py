#!/usr/bin/env python3
"""Kallim — Bilingual TTS stitcher for Arabic language learning."""

import argparse
import io
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from pydub import AudioSegment

logger = logging.getLogger("kallim")


@dataclass
class Section:
    name: str
    phrases: list[tuple[str, str]] = field(default_factory=list)  # (english, arabic)


def setup_logging():
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    fh = logging.FileHandler("generate.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    logger.addHandler(sh)


def parse_input(path: str) -> list[Section]:
    text = Path(path).read_text(encoding="utf-8")
    sections: list[Section] = []
    current: Section | None = None

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]

        # Section header: # section_name
        if re.match(r"^#\s+", line):
            name = re.sub(r"^#\s+", "", line).strip()
            current = Section(name=name)
            sections.append(current)
            i += 1
            continue

        # Numbered English line: 1. phrase text
        m = re.match(r"^\d+\.\s+(.+)", line)
        if m and current is not None:
            english = m.group(1).strip()
            # Next non-blank line should be the Arabic (indented)
            i += 1
            while i < len(lines) and lines[i].strip() == "":
                i += 1
            if i < len(lines):
                arabic = lines[i].strip()
                current.phrases.append((english, arabic))
                i += 1
                continue
            else:
                logger.warning("Missing Arabic for phrase: %s", english)
                i += 1
                continue

        i += 1

    for s in sections:
        if not s.phrases:
            logger.warning("Section '%s' has no phrases", s.name)

    return sections


def generate_tts(client: ElevenLabs, text: str, voice_id: str) -> bytes | None:
    for attempt in range(2):
        try:
            audio_iter = client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
            )
            return b"".join(audio_iter)
        except Exception as e:
            if attempt == 0:
                logger.warning("TTS failed for '%s', retrying: %s", text[:40], e)
                time.sleep(2)
            else:
                logger.error("TTS failed for '%s' after retry: %s", text[:40], e)
    return None


def slow_down(segment: AudioSegment, speed: float) -> AudioSegment:
    """Slow down audio using ffmpeg atempo filter (preserves pitch)."""
    if speed == 1.0:
        return segment
    import subprocess
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as src, \
         tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as dst:
        src_path, dst_path = src.name, dst.name
    segment.export(src_path, format="mp3")
    # atempo only accepts 0.5-2.0, so chain filters for values below 0.5
    filters = []
    remaining = speed
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    filters.append(f"atempo={remaining}")
    subprocess.run(
        ["ffmpeg", "-y", "-i", src_path, "-filter:a", ",".join(filters), dst_path],
        capture_output=True, check=True,
    )
    result = AudioSegment.from_file(dst_path, format="mp3")
    os.unlink(src_path)
    os.unlink(dst_path)
    return result


def normalize_audio(segment: AudioSegment, target_dBFS: float = -20.0) -> AudioSegment:
    """Normalize audio segment to a target loudness level."""
    change_in_dBFS = target_dBFS - segment.dBFS
    return segment.apply_gain(change_in_dBFS)


def stitch_section(
    phrase_audio: list[tuple[bytes, bytes]],
    pause_en_ms: int,
    pause_ar_ms: int,
    arabic_speed: float = 1.0,
) -> AudioSegment:
    combined = AudioSegment.empty()
    silence_en = AudioSegment.silent(duration=pause_en_ms)
    silence_ar = AudioSegment.silent(duration=pause_ar_ms)

    for en_bytes, ar_bytes in phrase_audio:
        en_seg = AudioSegment.from_file(io.BytesIO(en_bytes), format="mp3")
        ar_seg = AudioSegment.from_file(io.BytesIO(ar_bytes), format="mp3")
        en_seg = normalize_audio(en_seg)
        ar_seg = normalize_audio(ar_seg)
        ar_seg = slow_down(ar_seg, arabic_speed)
        combined += en_seg + silence_en + ar_seg + silence_ar

    return combined


def write_transcript(path: Path, section_name: str, pairs: list[tuple[str, str]]):
    title = section_name.replace("_", " ").title()
    lines = [f"=== {title} ===\n"]
    for idx, (en, ar) in enumerate(pairs, 1):
        lines.append(f"{idx}. {en}")
        lines.append(f"   {ar}\n")
    path.write_text("\n".join(lines), encoding="utf-8")


def process_section(
    index: int,
    section: Section,
    output_dir: Path,
    pause_en_ms: int,
    pause_ar_ms: int,
    client: ElevenLabs,
    en_voice: str,
    ar_voice: str,
    arabic_speed: float = 1.0,
):
    prefix = f"{index:02d}_{section.name}"
    logger.info("Processing section: %s (%d phrases)", section.name, len(section.phrases))

    # Always write transcript
    write_transcript(output_dir / f"{prefix}.txt", section.name, section.phrases)

    # Generate TTS for each phrase pair
    audio_pairs: list[tuple[bytes, bytes]] = []
    for en_text, ar_text in section.phrases:
        logger.info("  TTS: %s / %s", en_text[:30], ar_text[:30])
        en_audio = generate_tts(client, en_text, en_voice)
        ar_audio = generate_tts(client, ar_text, ar_voice)
        if en_audio and ar_audio:
            audio_pairs.append((en_audio, ar_audio))
        else:
            logger.warning("  Skipping phrase (TTS failed): %s", en_text[:40])

    if not audio_pairs:
        logger.warning("No audio generated for section '%s', skipping MP3", section.name)
        return

    # Stitch and export
    combined = stitch_section(audio_pairs, pause_en_ms, pause_ar_ms, arabic_speed)
    mp3_path = output_dir / f"{prefix}.mp3"
    combined.export(str(mp3_path), format="mp3", bitrate="128k")
    logger.info("Exported: %s", mp3_path)


def list_voices(client: ElevenLabs):
    response = client.voices.get_all()
    for voice in response.voices:
        labels = ", ".join(f"{k}={v}" for k, v in (voice.labels or {}).items())
        print(f"{voice.voice_id}  {voice.name}  [{labels}]")


def main():
    load_dotenv()
    setup_logging()

    parser = argparse.ArgumentParser(description="Kallim — bilingual TTS stitcher")
    parser.add_argument("--input", "-i", help="Path to phrases text file")
    parser.add_argument("--output", "-o", default="./output", help="Output directory")
    parser.add_argument("--section", "-s", help="Process only this section")
    parser.add_argument("--list-voices", action="store_true", help="List ElevenLabs voices and exit")
    parser.add_argument("--pause-after-english", type=float, default=1.5, help="Pause after English (seconds)")
    parser.add_argument("--pause-after-arabic", type=float, default=3.0, help="Pause after Arabic (seconds)")
    parser.add_argument("--arabic-speed", type=float, default=1.0, help="Arabic speech speed (0.25-4.0, default 1.0; try 0.8 for slower)")
    args = parser.parse_args()

    # Validate env vars
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    en_voice = os.environ.get("ELEVENLABS_ENGLISH_VOICE_ID")
    ar_voice = os.environ.get("ELEVENLABS_ARABIC_VOICE_ID")

    if not api_key:
        sys.exit("Error: ELEVENLABS_API_KEY not set. Check your .env file.")

    client = ElevenLabs(api_key=api_key)

    if args.list_voices:
        list_voices(client)
        return

    if not args.input:
        sys.exit("Error: --input is required (unless using --list-voices)")

    if not en_voice:
        sys.exit("Error: ELEVENLABS_ENGLISH_VOICE_ID not set. Check your .env file.")
    if not ar_voice:
        sys.exit("Error: ELEVENLABS_ARABIC_VOICE_ID not set. Check your .env file.")

    # Parse input
    sections = parse_input(args.input)
    if not sections:
        sys.exit("Error: no sections found in input file")

    # Filter to single section if requested
    if args.section:
        sections = [s for s in sections if s.name == args.section]
        if not sections:
            sys.exit(f"Error: section '{args.section}' not found")

    # Create output dir
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    pause_en_ms = int(args.pause_after_english * 1000)
    pause_ar_ms = int(args.pause_after_arabic * 1000)

    # Process each section
    for idx, section in enumerate(sections, 1):
        try:
            process_section(idx, section, output_dir, pause_en_ms, pause_ar_ms, client, en_voice, ar_voice, args.arabic_speed)
        except Exception as e:
            logger.error("Failed to process section '%s': %s", section.name, e)

    logger.info("Done. %d section(s) processed.", len(sections))


if __name__ == "__main__":
    main()
