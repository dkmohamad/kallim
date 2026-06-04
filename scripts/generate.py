#!/usr/bin/env python3
"""Kallim — Generate shadowing audio from chunks.csv."""

import argparse
import csv
import io
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from pydub import AudioSegment

logger = logging.getLogger("kallim")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = PROJECT_ROOT / "audio"
OUTPUT_DIR = PROJECT_ROOT / "output"
CHUNKS_CSV = PROJECT_ROOT / "chunks.csv"


class Chunk(NamedTuple):
    """A single phrase pair from chunks.csv."""

    id: str
    arabic: str
    english: str
    register: str
    concept_tag: str


def make_run_dir() -> Path:
    """Create a timestamped run directory under output/."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def setup_logging(run_dir: Path) -> None:
    """Configure logging to write to run_dir/generate.log and stderr."""
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    fh = logging.FileHandler(run_dir / "generate.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    logger.addHandler(sh)


def load_chunks(path: Path) -> list[Chunk]:
    """Load all chunks from the CSV file."""
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        return [Chunk(*row) for row in reader]


def load_voice_map() -> dict[str, str]:
    """Build register -> voice ID mapping from environment variables.

    Returns:
        Mapping of register name to ElevenLabs voice ID.

    Raises:
        SystemExit: If any required voice variables are missing.
    """
    voice_map: dict[str, str] = {}
    missing: list[str] = []

    for register in ("english", "egyptian", "msa", "iraqi"):
        var = f"ELEVENLABS_VOICE_{register.upper()}"
        value = os.environ.get(var, "")
        if value:
            voice_map[register] = value
        else:
            missing.append(var)

    if missing:
        sys.exit(f"Error: missing voice env vars: {', '.join(missing)}")

    return voice_map


def generate_tts(client: ElevenLabs, text: str, voice_id: str) -> bytes | None:
    """Generate TTS audio bytes via ElevenLabs API with one retry."""
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


def normalize_audio(
    segment: AudioSegment, target_dbfs: float = -20.0
) -> AudioSegment:
    """Normalize audio segment to a target loudness level."""
    change = target_dbfs - segment.dBFS
    return segment.apply_gain(change)


def get_or_generate_chunk_audio(
    client: ElevenLabs,
    chunk: Chunk,
    voice_map: dict[str, str],
    audio_dir: Path,
    pause_ms: int = 2000,
) -> Path | None:
    """Return path to a chunk's stitched audio file, generating if missing.

    Audio format: English -> pause -> Arabic (recall-then-confirm).
    """
    audio_path = audio_dir / f"{chunk.id}.mp3"
    if audio_path.exists():
        logger.info("  Cached: %s", chunk.id)
        return audio_path

    en_bytes = generate_tts(client, chunk.english, voice_map["english"])
    ar_bytes = generate_tts(client, chunk.arabic, voice_map[chunk.register])

    if not en_bytes or not ar_bytes:
        logger.warning("  Skipping chunk %s (TTS failed)", chunk.id)
        return None

    en_seg = normalize_audio(
        AudioSegment.from_file(io.BytesIO(en_bytes), format="mp3")
    )
    ar_seg = normalize_audio(
        AudioSegment.from_file(io.BytesIO(ar_bytes), format="mp3")
    )

    combined = en_seg + AudioSegment.silent(duration=pause_ms) + ar_seg
    combined.export(str(audio_path), format="mp3", bitrate="128k")
    logger.info("  Generated: %s", chunk.id)
    return audio_path


def stitch_section(
    audio_paths: list[Path],
    pause_after_ms: int,
) -> AudioSegment:
    """Concatenate per-chunk audio files into a section MP3."""
    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=pause_after_ms)

    for path in audio_paths:
        seg = AudioSegment.from_file(str(path), format="mp3")
        combined += seg + silence

    return combined


def write_transcript(
    path: Path, section_name: str, chunks: list[Chunk]
) -> None:
    """Write a human-readable transcript for a section."""
    title = section_name.replace("_", " ").title()
    lines = [f"=== {title} ===\n"]
    for idx, chunk in enumerate(chunks, 1):
        lines.append(f"{idx}. {chunk.english}")
        lines.append(f"   {chunk.arabic}\n")
    path.write_text("\n".join(lines), encoding="utf-8")


def list_voices(client: ElevenLabs) -> None:
    """Print all available ElevenLabs voices."""
    response = client.voices.get_all()
    for voice in response.voices:
        labels = ", ".join(
            f"{k}={v}" for k, v in (voice.labels or {}).items()
        )
        print(f"{voice.voice_id}  {voice.name}  [{labels}]")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Kallim — generate shadowing audio from chunks.csv"
    )
    parser.add_argument(
        "--input", "-i", default=str(CHUNKS_CSV),
        help="Path to chunks CSV file",
    )
    parser.add_argument(
        "--section", "-s",
        help="Process only chunks with this concept_tag",
    )
    parser.add_argument(
        "--list-voices", action="store_true",
        help="List ElevenLabs voices and exit",
    )
    parser.add_argument(
        "--pause", type=float, default=2.0,
        help="Pause duration in seconds (between English/Arabic and between chunks)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        if args.list_voices:
            sys.exit("Error: ELEVENLABS_API_KEY not set.")
        sys.exit("Error: ELEVENLABS_API_KEY not set. Check your .env file.")

    client = ElevenLabs(api_key=api_key)

    if args.list_voices:
        list_voices(client)
        return

    voice_map = load_voice_map()

    # Load and filter chunks
    chunks = load_chunks(Path(args.input))
    if not chunks:
        sys.exit("Error: no chunks found in CSV")

    # Group by concept_tag
    sections: dict[str, list[Chunk]] = {}
    for chunk in chunks:
        sections.setdefault(chunk.concept_tag, []).append(chunk)

    if args.section:
        if args.section not in sections:
            sys.exit(f"Error: section '{args.section}' not found")
        sections = {args.section: sections[args.section]}

    # Create directories
    AUDIO_DIR.mkdir(exist_ok=True)
    run_dir = make_run_dir()
    setup_logging(run_dir)

    pause_ms = int(args.pause * 1000)

    for idx, (tag, tag_chunks) in enumerate(sections.items(), 1):
        prefix = f"{idx:02d}_{tag}"
        logger.info(
            "Processing section: %s (%d chunks)", tag, len(tag_chunks)
        )

        # Always write transcript
        write_transcript(
            run_dir / f"{prefix}.txt", tag, tag_chunks
        )

        # Generate per-chunk audio (cached by id)
        audio_paths: list[Path] = []
        for chunk in tag_chunks:
            logger.info(
                "  Chunk %s: %s / %s",
                chunk.id, chunk.english[:30], chunk.arabic[:30],
            )
            path = get_or_generate_chunk_audio(
                client, chunk, voice_map, AUDIO_DIR, pause_ms
            )
            if path:
                audio_paths.append(path)

        if not audio_paths:
            logger.warning(
                "No audio generated for section '%s', skipping MP3", tag
            )
            continue

        # Stitch into section MP3
        combined = stitch_section(audio_paths, pause_ms)
        mp3_path = run_dir / f"{prefix}.mp3"
        combined.export(str(mp3_path), format="mp3", bitrate="128k")
        logger.info("Exported: %s", mp3_path)

    logger.info("Done. %d section(s) processed.", len(sections))


if __name__ == "__main__":
    main()
