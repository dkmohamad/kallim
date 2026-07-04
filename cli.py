#!/usr/bin/env python3
"""Kallim CLI — unified entrypoint for all commands.

Each subparser declares its own flags once and binds its command's ``run(args)``
via ``set_defaults(func=...)``; ``main`` parses and calls ``args.func(args)``.
"""

import argparse

from scripts import generate, generate_anki, lint, migrate, promote, prune
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
    gen.add_argument(
        "--section", "-s", help="Process only chunks with this concept_tag"
    )
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
    anki.add_argument(
        "--section", "-s", help="Process only chunks with this concept_tag"
    )
    anki.add_argument(
        "--no-audio", action="store_true", help="Generate text-only cards (no TTS)"
    )
    anki.add_argument(
        "--force",
        action="store_true",
        help="Regenerate audio even when the cached file exists",
    )
    anki.set_defaults(func=generate_anki.run)

    mig = sub.add_parser(
        "migrate", help="One-time migration: phrases.txt -> chunks.csv"
    )
    mig.set_defaults(func=migrate.run)

    prom = sub.add_parser(
        "promote", help="Promote vocab words into chunks with example sentences"
    )
    prom.add_argument(
        "input_file",
        nargs="?",
        help="Path to vocab CSV (arabic,english,register,concept_tag). "
        "Defaults to vocab_pairs.csv.",
    )
    prom.set_defaults(func=promote.run)

    voices = sub.add_parser("voices", help="List available ElevenLabs voices")
    voices.set_defaults(func=generate.list_installed_voices)

    lnt = sub.add_parser(
        "lint", help="Validate chunks.csv against the canonical taxonomy"
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
    args.func(args)


if __name__ == "__main__":
    main()
