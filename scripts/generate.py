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
from scripts.model import Section
from scripts.utils import make_run_dir, setup_logging
from scripts.store import load_chunks

logger = logging.getLogger("kallim")


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
        help="Regenerate audio even when cached (ignore the content manifest)",
    )
    args = parser.parse_args()

    if args.list_voices:
        list_voices(make_client())
        return

    chunks = load_chunks(Path(args.input))
    sections = Section.group(chunks)
    if args.section:
        sections = [s for s in sections if s.concept_tag == args.section]
        if not sections:
            sys.exit(f"Error: section '{args.section}' not found")

    run_dir = make_run_dir()
    setup_logging(run_dir)

    pause_ms = int(args.pause * 1000)

    with AudioGenerator.from_env(force=args.force) as audio:
        for idx, section in enumerate(sections, 1):
            logger.info(
                "Processing section: %s (%d chunks)",
                section.label, len(section.chunks),
            )

            # Always write transcript
            (run_dir / f"{section.prefix(idx)}.txt").write_text(
                section.transcript_text(), encoding="utf-8"
            )

            # Generate per-chunk audio (cached) and stitch into section
            section_audio = AudioSegment.empty()
            pause = AudioSegment.silent(duration=pause_ms)
            for chunk in section.chunks:
                logger.info(
                    "  Chunk %s: %s / %s",
                    chunk.id, chunk.english[:30], chunk.arabic[:30],
                )
                audio.generate(chunk)
                en_seg, ar_seg = chunk.segments(AUDIO_DIR, load_clip)
                section_audio += en_seg + pause + ar_seg + pause

            # Export section MP3
            mp3_path = run_dir / f"{section.prefix(idx)}.mp3"
            section_audio.export(str(mp3_path), format="mp3", bitrate="128k")
            logger.info("Exported: %s", mp3_path)

    logger.info("Done. %d section(s) processed.", len(sections))


if __name__ == "__main__":
    main()
