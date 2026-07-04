"""Kallim — Prune orphaned audio cache files.

Audio is content-addressed: each file is named ``audio/<key>.mp3``. A file is an
orphan when its key is no longer produced by any chunk in chunks.csv — the chunk
was removed, or its text was edited (which changes the key and leaves the old
file behind). This deletes those files.

Defaults to a dry run — pass --apply to actually delete.
"""

import argparse
from pathlib import Path

from .config import CHUNKS_CSV
from .store import AudioCache, load_chunks

__all__ = ["live_keys", "prune", "run"]


def live_keys(csv_path: Path) -> set[str]:
    """The content keys (English + Arabic) produced by every chunk."""
    chunks = load_chunks(csv_path)
    return {utt.key for c in chunks for utt in c.utterances}


def prune(cache: AudioCache, csv_path: Path, *, apply: bool) -> int:
    """Report (and with apply=True, delete) orphaned cache files.

    Returns the number of orphan files found.
    """
    orphans = sorted(set(cache) - live_keys(csv_path))

    if not orphans:
        print(f"OK: no orphans ({len(cache)} cached).")
        return 0

    print(f"{len(orphans)} orphan file(s):")
    for key in orphans[:10]:
        print(f"  {cache.path(key).name}")
    if len(orphans) > 10:
        print(f"  ... and {len(orphans) - 10} more")
    print()

    if not apply:
        print("Dry run — nothing deleted. Re-run with --apply to remove.")
        return len(orphans)

    for key in orphans:
        del cache[key]

    print(f"Deleted {len(orphans)} file(s).")
    print(
        "Note: Anki cards for removed chunks are not deleted automatically — "
        "remove them by hand in Anki (genanki only adds/updates)."
    )
    return len(orphans)


def run(args: argparse.Namespace) -> None:
    """Delete orphaned audio cache files (dry run unless ``--apply``)."""
    prune(AudioCache(), CHUNKS_CSV, apply=args.apply)
