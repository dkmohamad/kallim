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
from .chunks import Chunks
from .model import ConceptTag

__all__ = ["dry_run_report", "scoped_chunks"]


def scoped_chunks(args: argparse.Namespace) -> Chunks:
    """Load the .env and chunks.csv, narrowed to ``--section``.

    Parses ``--section`` into a ``ConceptTag`` at this CLI boundary, so a value
    off the taxonomy is rejected as such (not as a silent "section not found").
    Exits (via ``sys.exit``) with a message on either error.
    """
    load_dotenv()
    chunks = Chunks.load(Path(args.input))
    try:
        tag = None if args.section is None else ConceptTag(args.section)
        return chunks.section(tag)
    except ValueError as exc:
        sys.exit(f"Error: {exc}")


def dry_run_report(
    command: str,
    args: argparse.Namespace,
    chunks: Chunks,
    *,
    audio_enabled: bool,
) -> str:
    """Build the dry-run cost report for a command — no synthesis, no run dir.

    Returns the report text for the CLI to print. Fetches live quota only when
    audio would actually be synthesised (skipped for ``anki --no-audio``, which
    makes no TTS calls).
    """
    return plan.render(
        command=command,
        section=args.section,
        force=args.force,
        chunks=chunks,
        cache=AudioCache(),
        quota=get_quota() if audio_enabled else None,
        audio_enabled=audio_enabled,
    )
