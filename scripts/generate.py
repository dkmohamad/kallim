#!/usr/bin/env python3
"""Kallim — Generate shadowing audio from chunks.csv."""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from scripts.audio import list_voices, make_synthesiser, stitch
from scripts.config import CHUNKS_CSV
from scripts.model import Chunk, PlayableAudio, Register
from scripts.store import AudioCache, load_chunks, make_codec
from scripts.utils import make_run_dir, setup_logging

logger = logging.getLogger("kallim")


def _sections(chunks: list[Chunk]) -> list[tuple[str, Register, list[Chunk]]]:
    """Group chunks by (concept_tag, Arabic register), preserving first-seen order."""
    groups: dict[tuple[str, Register], list[Chunk]] = {}
    for chunk in chunks:
        groups.setdefault((chunk.concept_tag, chunk.arabic.register), []).append(chunk)
    return [(tag, reg, cs) for (tag, reg), cs in groups.items()]


def _transcript(label: str, chunks: list[Chunk]) -> str:
    """A section transcript: a title then numbered english/arabic pairs."""
    title = label.replace("_", " ").title()
    lines = [f"=== {title} ===\n"]
    for idx, chunk in enumerate(chunks, 1):
        lines.append(f"{idx}. {chunk.english.text}")
        lines.append(f"   {chunk.arabic.text}\n")
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
        list_voices()
        return

    chunks = load_chunks(Path(args.input))
    if args.section:
        chunks = [c for c in chunks if c.concept_tag == args.section]
        if not chunks:
            sys.exit(f"Error: section '{args.section}' not found")

    run_dir = make_run_dir()
    setup_logging(run_dir)

    pause_ms = int(args.pause * 1000)
    make_synthesiser()  # wires Utterance.synthesiser
    cache = AudioCache()
    codec = make_codec()

    sections = _sections(chunks)
    for idx, (tag, register, group) in enumerate(sections, 1):
        label = f"{tag} ({register})"
        prefix = f"{idx:02d}_{tag}_{register}"
        logger.info("Processing section: %s (%d chunks)", label, len(group))

        # Always write the transcript
        (run_dir / f"{prefix}.txt").write_text(
            _transcript(label, group), encoding="utf-8"
        )

        # Synthesise/load each utterance's audio, then stitch the section
        clips: list[PlayableAudio] = []
        for chunk in group:
            logger.info("  %s", chunk)
            for utt in (chunk.english, chunk.arabic):
                if args.force or utt.key not in cache:
                    clip = utt.synthesise()
                    cache[utt.key] = clip
                else:
                    clip = cache[utt.key]
                clips.append(clip)

        mp3_path = run_dir / f"{prefix}.mp3"
        codec.encode(stitch(clips, pause_ms), mp3_path)
        logger.info("Exported: %s", mp3_path)

    logger.info("Done. %d section(s) processed.", len(sections))


if __name__ == "__main__":
    main()
