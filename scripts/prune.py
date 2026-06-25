#!/usr/bin/env python3
"""Kallim — Prune orphaned audio cache files.

Audio is content-addressed: each file is named ``audio/<content-hash>.mp3``. A
file is an orphan when its hash is no longer produced by any chunk in chunks.csv
— the chunk was removed, or its text was edited (which changes the hash and
leaves the old file behind). This deletes those files.

Defaults to a dry run — pass --apply to actually delete.
"""

import argparse
from pathlib import Path

from scripts.config import AUDIO_DIR, CHUNKS_CSV
from scripts.store import load_chunks


def live_hashes(csv_path: Path) -> set[str]:
    """The content hashes (English + Arabic) produced by every chunk."""
    chunks = load_chunks(csv_path)
    return {c.en_cache_key for c in chunks} | {c.ar_cache_key for c in chunks}


def find_orphans(audio_dir: Path, hashes: set[str]) -> list[Path]:
    """Audio files whose content hash is no longer produced by any chunk."""
    return [p for p in sorted(audio_dir.glob("*.mp3")) if p.stem not in hashes]


def prune(audio_dir: Path, csv_path: Path, *, apply: bool) -> int:
    """Report (and with apply=True, delete) orphaned cache files.

    Returns the number of orphan files found.
    """
    if not audio_dir.exists():
        print(f"No audio dir at {audio_dir}; nothing to prune.")
        return 0

    hashes = live_hashes(csv_path)
    orphans = find_orphans(audio_dir, hashes)

    if not orphans:
        print(f"OK: no orphans ({len(hashes)} live audio hashes).")
        return 0

    print(f"{len(orphans)} orphan file(s):")
    for path in orphans[:10]:
        print(f"  {path.name}")
    if len(orphans) > 10:
        print(f"  ... and {len(orphans) - 10} more")
    print()

    if not apply:
        print("Dry run — nothing deleted. Re-run with --apply to remove.")
        return len(orphans)

    for path in orphans:
        path.unlink()

    print(f"Deleted {len(orphans)} file(s).")
    print(
        "Note: Anki cards for removed chunks are not deleted automatically — "
        "remove them by hand in Anki (genanki only adds/updates)."
    )
    return len(orphans)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="prune",
        description="Delete orphaned (stale or removed) audio cache files",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually delete (default is a dry run)",
    )
    args = parser.parse_args()
    prune(AUDIO_DIR, CHUNKS_CSV, apply=args.apply)


if __name__ == "__main__":
    main()
