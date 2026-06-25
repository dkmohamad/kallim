#!/usr/bin/env python3
"""Kallim — Generate Anki flashcard deck with audio from chunks.csv."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import genanki
from dotenv import load_dotenv

from scripts.audio import AudioGenerator
from scripts.config import AUDIO_DIR, CHUNKS_CSV
from scripts.utils import make_run_dir, setup_logging
from scripts.store import load_chunks

logger = logging.getLogger("kallim.anki")

# Fixed IDs so re-runs update existing cards rather than creating duplicates.
DECK_ID = 2059400110
MODEL_ID = 1607392320


def build_model() -> genanki.Model:
    """Build the Anki card model with bidirectional templates."""
    return genanki.Model(
        MODEL_ID,
        "Kallim Arabic",
        fields=[
            {"name": "English"},
            {"name": "Arabic"},
            {"name": "EnglishAudio"},
            {"name": "ArabicAudio"},
            {"name": "Register"},
        ],
        templates=[
            {
                "name": "English → Arabic",
                "qfmt": (
                    '<div class="english">{{English}}</div>'
                    "<div>{{EnglishAudio}}</div>"
                ),
                "afmt": (
                    '<div class="english">{{English}}</div>'
                    '<hr id="answer">'
                    '<div class="arabic">{{Arabic}}</div>'
                    "<div>{{ArabicAudio}}</div>"
                ),
            },
            {
                "name": "Arabic → English",
                "qfmt": (
                    '<div class="arabic">{{Arabic}}</div>'
                    "<div>{{ArabicAudio}}</div>"
                ),
                "afmt": (
                    '<div class="arabic">{{Arabic}}</div>'
                    '<hr id="answer">'
                    '<div class="english">{{English}}</div>'
                    "<div>{{EnglishAudio}}</div>"
                ),
            },
        ],
        css=(
            ".card { font-family: sans-serif; text-align: center;"
            " padding: 20px; }\n"
            ".english { font-size: 24px; margin-bottom: 15px; }\n"
            ".arabic { font-size: 36px; direction: rtl;"
            " font-family: 'Noto Sans Arabic', 'Arial', sans-serif;"
            " margin-top: 15px; line-height: 1.6; }\n"
        ),
    )


def main() -> None:
    load_dotenv()

    run_dir = make_run_dir()
    setup_logging(run_dir)

    parser = argparse.ArgumentParser(
        description="Kallim — Anki deck generator from chunks.csv"
    )
    parser.add_argument(
        "--input", "-i", default=str(CHUNKS_CSV),
        help="Path to chunks CSV file",
    )
    parser.add_argument(
        "--output", "-o",
        default=str(run_dir / "kallim_arabic.apkg"),
        help="Output .apkg path",
    )
    parser.add_argument(
        "--section", "-s",
        help="Process only chunks with this concept_tag",
    )
    parser.add_argument(
        "--no-audio", action="store_true",
        help="Generate text-only cards (no TTS)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Regenerate audio even when cached (ignore the content manifest)",
    )
    args = parser.parse_args()

    chunks = load_chunks(Path(args.input))

    if args.section:
        chunks = [c for c in chunks if c.concept_tag == args.section]
        if not chunks:
            sys.exit(f"Error: section '{args.section}' not found")

    # Set up the audio generator if generating audio
    generator: AudioGenerator | None = None
    if not args.no_audio:
        generator = AudioGenerator.from_env(force=args.force)

    model = build_model()
    deck = genanki.Deck(DECK_ID, "Kallim Arabic")
    media_files: list[str] = []

    total_cards = 0
    for chunk in chunks:
        en_sound = ""
        ar_sound = ""

        if generator:
            logger.info(
                "  Chunk %s: %s / %s",
                chunk.id, chunk.english[:30], chunk.arabic[:30],
            )
            generator.generate(chunk)
            en_path, ar_path = chunk.audio_paths(AUDIO_DIR)
            en_sound = f"[sound:{en_path.name}]"
            ar_sound = f"[sound:{ar_path.name}]"
            media_files.append(str(en_path))
            media_files.append(str(ar_path))

        note = genanki.Note(
            model=model,
            fields=[chunk.english, chunk.arabic, en_sound, ar_sound, chunk.register],
            tags=[f"topic::{chunk.concept_tag}", f"register::{chunk.register}"],
            guid=genanki.guid_for(chunk.id),
        )
        deck.add_note(note)
        total_cards += 1

    if generator:
        generator.save()

    package = genanki.Package(deck)
    package.media_files = media_files
    package.write_to_file(args.output)

    logger.info(
        "Done. %d cards across %d section(s) → %s",
        total_cards,
        len({c.concept_tag for c in chunks}),
        args.output,
    )


if __name__ == "__main__":
    main()
