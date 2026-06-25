#!/usr/bin/env python3
"""Kallim — Generate shadowing audio from chunks.csv."""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydub import AudioSegment

from scripts.audio import AudioGenerator, list_voices, load_clip, make_client
from scripts.config import AUDIO_DIR, CHUNKS_CSV
from scripts.model import Chunk
from scripts.store import load_chunks
from scripts.utils import make_run_dir, setup_logging

logger = logging.getLogger("kallim")


def _sections(chunks: list[Chunk]) -> list[tuple[str, str, list[Chunk]]]:
    """Group chunks by (concept_tag, register), preserving first-seen order."""
    groups: dict[tuple[str, str], list[Chunk]] = {}
    for chunk in chunks:
        groups.setdefault((chunk.concept_tag, chunk.register), []).append(chunk)
    return [(tag, reg, cs) for (tag, reg), cs in groups.items()]


def _transcript(label: str, chunks: list[Chunk]) -> str:
    """A section transcript: a title then numbered english/arabic pairs."""
    title = label.replace("_", " ").title()
    lines = [f"=== {title} ===\n"]
    for idx, chunk in enumerate(chunks, 1):
        lines.append(f"{idx}. {chunk.english}")
        lines.append(f"   {chunk.arabic}\n")
    return "\n".join(lines)


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
    parser.add_argument(
        "--force", action="store_true",
        help="Regenerate audio even when the cached file exists",
    )
    args = parser.parse_args()

    if args.list_voices:
        list_voices(make_client())
        return

    chunks = load_chunks(Path(args.input))
    if args.section:
        chunks = [c for c in chunks if c.concept_tag == args.section]
        if not chunks:
            sys.exit(f"Error: section '{args.section}' not found")

    run_dir = make_run_dir()
    setup_logging(run_dir)

    pause_ms = int(args.pause * 1000)
    pause = AudioSegment.silent(duration=pause_ms)
    audio = AudioGenerator.from_env(force=args.force)

    sections = _sections(chunks)
    for idx, (tag, register, group) in enumerate(sections, 1):
        label = f"{tag} ({register})"
        prefix = f"{idx:02d}_{tag}_{register}"
        logger.info("Processing section: %s (%d chunks)", label, len(group))

        # Always write the transcript
        (run_dir / f"{prefix}.txt").write_text(
            _transcript(label, group), encoding="utf-8"
        )

        # Generate per-chunk audio (content-addressed cache) and stitch
        section_audio = AudioSegment.empty()
        for chunk in group:
            logger.info(
                "  Chunk %s: %s / %s",
                chunk.id, chunk.english[:30], chunk.arabic[:30],
            )
            audio.generate(chunk)
            en_path, ar_path = chunk.audio_paths(AUDIO_DIR)
            section_audio += load_clip(en_path) + pause + load_clip(ar_path) + pause

        mp3_path = run_dir / f"{prefix}.mp3"
        section_audio.export(str(mp3_path), format="mp3", bitrate="128k")
        logger.info("Exported: %s", mp3_path)

    logger.info("Done. %d section(s) processed.", len(sections))


if __name__ == "__main__":
    main()
