"""Kallim — Generate Anki flashcard deck with audio from chunks.csv."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import genanki

from .audio import make_synthesiser
from .cache import AudioCache, ensure_cached
from .command import dry_run_report, scoped_chunks
from .model import Chunk, Utterance
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


def run(args: argparse.Namespace) -> str | None:
    """Build an Anki .apkg deck (optionally with TTS audio) from chunks.csv.

    Returns the dry-run report to print in ``--dry-run`` mode; otherwise writes
    the .apkg and returns None (progress goes through the logger).
    """
    chunks = scoped_chunks(args)

    if args.dry_run:
        return dry_run_report("anki", args, chunks, audio_enabled=not args.no_audio)

    run_dir = make_run_dir()
    setup_logging(run_dir)

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
            media_files.extend(str(cache.path(utt.key)) for utt in chunk.utterances)
            en_sound = _sound_ref(cache, chunk.english)
            ar_sound = _sound_ref(cache, chunk.arabic)

        deck.add_note(_note(chunk, model, en_sound, ar_sound))
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


def _sound_ref(cache: AudioCache, utt: Utterance) -> str:
    """The Anki ``[sound:…]`` reference for an utterance's cached audio file."""
    return f"[sound:{cache.path(utt.key).name}]"


def _note(
    chunk: Chunk, model: genanki.Model, en_sound: str, ar_sound: str
) -> genanki.Note:
    """Build the bidirectional Anki note for a chunk (audio refs already resolved)."""
    return genanki.Note(
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
