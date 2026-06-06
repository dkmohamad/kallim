#!/usr/bin/env python3
"""Kallim — Generate shadowing audio from chunks.csv."""

import argparse
import csv
import io
import json
import logging
import os
import sys
import time
from datetime import datetime
from enum import Enum
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


class Register(str, Enum):
    """Arabic register / voice role."""

    ENGLISH = "english"
    EGYPTIAN = "egyptian"
    MSA = "msa"
    IRAQI = "iraqi"
    SECONDARY = "secondary"  # second voice for dialogues


class Chunk(NamedTuple):
    """A single phrase pair from chunks.csv."""

    id: str
    arabic: str
    english: str
    register: str
    concept_tag: str


def make_run_dir() -> Path:
    """Create a timestamped run directory under output/."""
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
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


VOICES_JSON = PROJECT_ROOT / "voices.json"

# Registers required by the generate/anki pipelines.
_REQUIRED_VOICES = {Register.ENGLISH, Register.EGYPTIAN, Register.MSA, Register.IRAQI}


def load_voice_map(require: set[Register] | None = None) -> dict[str, str]:
    """Load register -> voice ID mapping from voices.json.

    Args:
        require: Set of registers that must be present.  Defaults to the
                 four TTS registers (english, egyptian, msa, iraqi).

    Returns:
        Mapping of register value string to ElevenLabs voice ID.

    Raises:
        SystemExit: If voices.json is missing or required keys are absent.
    """
    if not VOICES_JSON.exists():
        sys.exit(f"Error: {VOICES_JSON} not found. See voices.json.example.")

    with VOICES_JSON.open(encoding="utf-8") as f:
        voice_map: dict[str, str] = json.load(f)

    needed = {r.value for r in (require if require is not None else _REQUIRED_VOICES)}
    missing = needed - voice_map.keys()
    if missing:
        sys.exit(f"Error: missing voices in {VOICES_JSON}: {', '.join(sorted(missing))}")

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
) -> tuple[Path, Path] | None:
    """Return paths to separate English and Arabic audio files for a chunk.

    Caches as audio/{id}_en.mp3 and audio/{id}_ar.mp3.
    Returns (en_path, ar_path) or None on failure.
    """
    en_path = audio_dir / f"{chunk.id}_en.mp3"
    ar_path = audio_dir / f"{chunk.id}_ar.mp3"

    if en_path.exists() and ar_path.exists():
        logger.info("  Cached: %s", chunk.id)
        return en_path, ar_path

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

    en_seg.export(str(en_path), format="mp3", bitrate="128k")
    ar_seg.export(str(ar_path), format="mp3", bitrate="128k")
    logger.info("  Generated: %s", chunk.id)
    return en_path, ar_path


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

    # Group by (concept_tag, register) so different registers get separate MP3s
    sections: dict[tuple[str, str], list[Chunk]] = {}
    for chunk in chunks:
        sections.setdefault((chunk.concept_tag, chunk.register), []).append(chunk)

    if args.section:
        filtered = {
            k: v for k, v in sections.items() if k[0] == args.section
        }
        if not filtered:
            sys.exit(f"Error: section '{args.section}' not found")
        sections = filtered

    # Create directories
    AUDIO_DIR.mkdir(exist_ok=True)
    run_dir = make_run_dir()
    setup_logging(run_dir)

    pause_ms = int(args.pause * 1000)

    for idx, ((tag, register), tag_chunks) in enumerate(sections.items(), 1):
        prefix = f"{idx:02d}_{tag}_{register}"
        section_label = f"{tag} ({register})"
        logger.info(
            "Processing section: %s (%d chunks)", section_label, len(tag_chunks)
        )

        # Always write transcript
        write_transcript(
            run_dir / f"{prefix}.txt", section_label, tag_chunks
        )

        # Generate per-chunk audio (cached by id) and stitch into section
        section_audio = AudioSegment.empty()
        chunk_count = 0
        pause = AudioSegment.silent(duration=pause_ms)
        for chunk in tag_chunks:
            logger.info(
                "  Chunk %s: %s / %s",
                chunk.id, chunk.english[:30], chunk.arabic[:30],
            )
            result = get_or_generate_chunk_audio(
                client, chunk, voice_map, AUDIO_DIR
            )
            if result:
                en_path, ar_path = result
                en_seg = AudioSegment.from_file(str(en_path), format="mp3")
                ar_seg = AudioSegment.from_file(str(ar_path), format="mp3")
                section_audio += en_seg + pause + ar_seg + pause
                chunk_count += 1

        if not chunk_count:
            logger.warning(
                "No audio generated for section '%s', skipping MP3", section_label
            )
            continue

        # Export section MP3
        mp3_path = run_dir / f"{prefix}.mp3"
        section_audio.export(str(mp3_path), format="mp3", bitrate="128k")
        logger.info("Exported: %s", mp3_path)

    logger.info("Done. %d section(s) processed.", len(sections))


if __name__ == "__main__":
    main()
