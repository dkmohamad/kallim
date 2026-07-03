"""Kallim — Generate Anki flashcard deck with audio from chunks.csv."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import genanki
from dotenv import load_dotenv

from .audio import make_synthesiser
from .store import AudioCache, ensure_cached, load_chunks, select_section
from .utils import make_run_dir, setup_logging

__all__ = ["make_model", "run"]

logger = logging.getLogger("kallim.anki")

# Fixed IDs so re-runs update existing cards rather than creating duplicates.
DECK_ID = 2059400110
MODEL_ID = 1607392320


def make_model() -> genanki.Model:
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
                    '<div class="english">{{English}}</div><div>{{EnglishAudio}}</div>'
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
                    '<div class="arabic">{{Arabic}}</div><div>{{ArabicAudio}}</div>'
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


def run(args: argparse.Namespace) -> None:
    """Build an Anki .apkg deck (optionally with TTS audio) from chunks.csv."""
    load_dotenv()

    run_dir = make_run_dir()
    setup_logging(run_dir)

    chunks = load_chunks(Path(args.input))
    try:
        chunks = select_section(chunks, args.section)
    except ValueError as exc:
        sys.exit(f"Error: {exc}")

    output = Path(args.output) if args.output else run_dir / "kallim_arabic.apkg"
    synth = None if args.no_audio else make_synthesiser()
    cache = AudioCache()

    model = make_model()
    deck = genanki.Deck(DECK_ID, "Kallim Arabic")
    media_files: list[str] = []

    total_cards = 0
    for chunk in chunks:
        en_sound = ""
        ar_sound = ""

        if synth is not None:
            logger.info("  %s", chunk)
            ensure_cached(chunk, synth, cache, force=args.force)
            media_files.extend(
                str(cache.path(utt.key)) for utt in (chunk.english, chunk.arabic)
            )
            en_sound = f"[sound:{cache.path(chunk.english.key).name}]"
            ar_sound = f"[sound:{cache.path(chunk.arabic.key).name}]"

        note = genanki.Note(
            model=model,
            fields=[
                chunk.english.text,
                chunk.arabic.text,
                en_sound,
                ar_sound,
                chunk.arabic.register,
            ],
            tags=[
                f"topic::{chunk.concept_tag}",
                f"register::{chunk.arabic.register}",
            ],
            guid=genanki.guid_for(chunk.id),
        )
        deck.add_note(note)
        total_cards += 1

    package = genanki.Package(deck)
    package.media_files = media_files
    package.write_to_file(str(output))

    logger.info(
        "Done. %d cards across %d section(s) → %s",
        total_cards,
        len({c.concept_tag for c in chunks}),
        output,
    )
