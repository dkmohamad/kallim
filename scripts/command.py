"""Shared scaffolding for the generate/anki commands.

Both commands start the same way — load the .env, read chunks.csv, narrow to
``--section`` (exiting on a bad tag), and short-circuit to the dry-run cost
report before any synthesis. Those steps are identical, so they live here rather
than being copied into each command's ``run``; the commands keep only their real
difference (stitching section MP3s vs. building the Anki deck).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from . import plan
from .audio import get_quota
from .cache import AudioCache
from .chunks import load_chunks, select_section
from .model import Chunk

__all__ = ["dry_run_report", "scoped_chunks"]


def scoped_chunks(args: argparse.Namespace) -> list[Chunk]:
    """Load the .env and chunks.csv, narrowed to ``--section``.

    Exits (via ``sys.exit``) with a message if ``--section`` names a tag no chunk
    carries — the CLI boundary for a user typo.
    """
    load_dotenv()
    chunks = load_chunks(Path(args.input))
    try:
        return select_section(chunks, args.section)
    except ValueError as exc:
        sys.exit(f"Error: {exc}")


def dry_run_report(
    command: str,
    args: argparse.Namespace,
    chunks: list[Chunk],
    *,
    audio_enabled: bool,
) -> None:
    """Print the dry-run cost report for a command — no synthesis, no run dir.

    Fetches live quota only when audio would actually be synthesised (skipped for
    ``anki --no-audio``, which makes no TTS calls).
    """
    plan.report(
        command=command,
        section=args.section,
        force=args.force,
        chunks=chunks,
        cache=AudioCache(),
        quota=get_quota() if audio_enabled else None,
        audio_enabled=audio_enabled,
    )
