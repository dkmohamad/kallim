#!/usr/bin/env python3
"""Kallim CLI — unified entrypoint for all commands.

Each subparser declares its own flags once and binds its command's ``run(args)``
via ``set_defaults(func=...)``; ``main`` parses and calls ``args.func(args)``.
"""

import argparse

from scripts import generate, generate_anki, ingest, lint, prune, script, tags
from scripts.config import CHUNKS_CSV

__all__ = ["main"]


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="kallim",
        description="Arabic language learning toolkit",
    )
    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="Generate shadowing audio from chunks.csv")
    gen.add_argument(
        "--input", "-i", default=str(CHUNKS_CSV), help="Path to chunks CSV file"
    )
    gen.add_argument("--section", "-s", help="Process only chunks with this topic")
    gen.add_argument(
        "--pause",
        type=float,
        default=2.0,
        help="Pause duration in seconds (between English/Arabic and between chunks)",
    )
    gen.add_argument(
        "--force",
        action="store_true",
        help="Regenerate audio even when the cached file exists",
    )
    gen.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be synthesised (and its credit cost) without doing it",
    )
    gen.set_defaults(func=generate.run)

    anki = sub.add_parser("anki", help="Generate Anki flashcard deck from chunks.csv")
    anki.add_argument(
        "--input", "-i", default=str(CHUNKS_CSV), help="Path to chunks CSV file"
    )
    anki.add_argument(
        "--output",
        "-o",
        help="Output .apkg path (default: <run_dir>/kallim_arabic.apkg)",
    )
    anki.add_argument("--section", "-s", help="Process only chunks with this topic")
    anki.add_argument(
        "--no-audio", action="store_true", help="Generate text-only cards (no TTS)"
    )
    anki.add_argument(
        "--force",
        action="store_true",
        help="Regenerate audio even when the cached file exists",
    )
    anki.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be synthesised (and its credit cost) without doing it",
    )
    anki.set_defaults(func=generate_anki.run)

    ing = sub.add_parser(
        "ingest",
        help="Dedup + id + validate extracted vocab candidates into a review CSV",
    )
    ing.add_argument(
        "candidates",
        nargs="?",
        help="Path to candidates CSV (arabic,english,register,topic and "
        "optionally priority). Defaults to vocab_pairs.csv.",
    )
    ing.add_argument(
        "--append",
        action="store_true",
        help="Commit the reviewed vocab_chunks_review.csv into chunks.csv",
    )
    ing.add_argument(
        "--force",
        action="store_true",
        help="Overwrite vocab_chunks_review.csv even when it still holds rows "
        "(discards them — commit with --append first to keep them)",
    )
    ing.set_defaults(func=ingest.run)

    scr = sub.add_parser(
        "script", help="Render a distilled lesson script into a two-voice MP3"
    )
    scr.add_argument("script", help="Path to the script page exported as markdown")
    scr.add_argument(
        "--render",
        action="store_true",
        help="Actually synthesise and stitch (default is a dry run with costs)",
    )
    scr.add_argument(
        "--force",
        action="store_true",
        help="Re-synthesise every turn even when the cached clip exists",
    )
    scr.set_defaults(func=script.run)

    voices = sub.add_parser("voices", help="List available ElevenLabs voices")
    voices.set_defaults(func=generate.list_installed_voices)

    tag = sub.add_parser(
        "tags", help="List the topic registry and each topic's description"
    )
    tag.set_defaults(func=tags.run)

    lnt = sub.add_parser(
        "lint", help="Validate a chunk bank: register, topic and priority"
    )
    lnt.add_argument(
        "input", nargs="?", help="Path to chunks CSV file. Defaults to chunks.csv."
    )
    lnt.set_defaults(func=lint.run)

    prn = sub.add_parser(
        "prune", help="Delete orphaned audio cache files (stale or removed)"
    )
    prn.add_argument(
        "--apply", action="store_true", help="Actually delete (default is a dry run)"
    )
    prn.set_defaults(func=prune.run)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        raise SystemExit(1)
    # Commands return the text to display (or None); the CLI is the one place
    # that prints — every other module returns strings (enforced by ruff T20).
    output = args.func(args)
    if output is not None:
        print(output)


if __name__ == "__main__":
    main()
