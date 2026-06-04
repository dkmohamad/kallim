#!/usr/bin/env python3
"""Kallim CLI — unified entrypoint for all commands."""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="kallim",
        description="Arabic language learning toolkit",
    )
    sub = parser.add_subparsers(dest="command")

    # --- generate ---
    gen = sub.add_parser(
        "generate", help="Generate shadowing audio from chunks.csv"
    )
    gen.add_argument(
        "--input", "-i", help="Path to chunks CSV file",
    )
    gen.add_argument(
        "--output", "-o", help="Output directory for section MP3s",
    )
    gen.add_argument(
        "--section", "-s",
        help="Process only chunks with this concept_tag",
    )
    gen.add_argument(
        "--list-voices", action="store_true",
        help="List ElevenLabs voices and exit",
    )
    gen.add_argument(
        "--pause", type=float, default=2.0,
        help="Pause duration in seconds (between English/Arabic and between chunks)",
    )

    # --- anki ---
    anki = sub.add_parser(
        "anki", help="Generate Anki flashcard deck from chunks.csv"
    )
    anki.add_argument(
        "--input", "-i", help="Path to chunks CSV file",
    )
    anki.add_argument(
        "--output", "-o", help="Output .apkg path",
    )
    anki.add_argument(
        "--section", "-s",
        help="Process only chunks with this concept_tag",
    )
    anki.add_argument(
        "--no-audio", action="store_true",
        help="Generate text-only cards (no TTS)",
    )

    # --- migrate ---
    sub.add_parser(
        "migrate", help="One-time migration: phrases.txt -> chunks.csv"
    )

    # --- promote ---
    promote = sub.add_parser(
        "promote", help="Promote vocab words into chunks with example sentences"
    )
    promote.add_argument(
        "input_file", nargs="?",
        help="Path to vocab file (CSV or plain text). Defaults to vocab_pairs.csv.",
    )

    # --- voices ---
    sub.add_parser(
        "voices", help="List available ElevenLabs voices"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "generate":
        from scripts.generate import main as generate_main
        # Rebuild sys.argv for the subcommand
        sys.argv = _rebuild_argv("generate", args, [
            "input", "output", "section", "list_voices", "pause",
        ])
        generate_main()

    elif args.command == "anki":
        from scripts.generate_anki import main as anki_main
        sys.argv = _rebuild_argv("anki", args, [
            "input", "output", "section", "no_audio",
        ])
        anki_main()

    elif args.command == "migrate":
        from scripts.migrate import main as migrate_main
        migrate_main()

    elif args.command == "promote":
        from scripts.promote import main as promote_main
        promote_main(getattr(args, "input_file", None))

    elif args.command == "voices":
        from scripts.generate import main as generate_main
        sys.argv = ["voices", "--list-voices"]
        generate_main()


def _rebuild_argv(
    command: str,
    args: argparse.Namespace,
    fields: list[str],
) -> list[str]:
    """Rebuild sys.argv from parsed args for sub-script compatibility."""
    argv = [command]
    for field in fields:
        value = getattr(args, field, None)
        if value is None or value is False:
            continue
        flag = f"--{field.replace('_', '-')}"
        if isinstance(value, bool):
            argv.append(flag)
        else:
            argv.extend([flag, str(value)])
    return argv


if __name__ == "__main__":
    main()
