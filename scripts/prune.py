"""Kallim — Prune orphaned audio cache files.

Audio is content-addressed: each file is named ``audio/<key>.mp3``. A file is an
orphan when its key is no longer produced by any chunk in chunks.csv — the chunk
was removed, or its text was edited (which changes the key and leaves the old
file behind). This deletes those files.

Defaults to a dry run — pass --apply to actually delete.
"""

import argparse
from pathlib import Path

from .cache import AudioCache
from .chunks import Chunks
from .config import CHUNKS_CSV

__all__ = ["live_keys", "prune", "run"]


def live_keys(csv_path: Path) -> set[str]:
    """The content keys (English + Arabic) produced by every chunk."""
    return Chunks.load(csv_path).audio_keys()


def prune(cache: AudioCache, csv_path: Path, *, apply: bool) -> str:
    """Report orphaned cache files (and with apply=True, delete them).

    Returns the report text; the caller (the CLI) prints it.
    """
    orphans = sorted(set(cache) - live_keys(csv_path))

    if not orphans:
        return f"OK: no orphans ({len(cache)} cached)."

    lines = [f"{len(orphans)} orphan file(s):"]
    lines += [f"  {cache.path(key).name}" for key in orphans[:10]]
    if len(orphans) > 10:
        lines.append(f"  ... and {len(orphans) - 10} more")
    lines.append("")

    if not apply:
        lines.append("Dry run — nothing deleted. Re-run with --apply to remove.")
        return "\n".join(lines)

    for key in orphans:
        del cache[key]

    lines.append(f"Deleted {len(orphans)} file(s).")
    lines.append(
        "Note: Anki cards for removed chunks are not deleted automatically — "
        "remove them by hand in Anki (genanki only adds/updates)."
    )
    return "\n".join(lines)


def run(args: argparse.Namespace) -> str:
    """Delete orphaned audio cache files (dry run unless ``--apply``)."""
    return prune(AudioCache(), CHUNKS_CSV, apply=args.apply)
