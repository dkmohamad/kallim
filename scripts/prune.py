#!/usr/bin/env python3
"""Kallim — Prune orphaned audio cache files.

The audio cache (audio/{id}_en.mp3, audio/{id}_ar.mp3) is never cleaned when a
row is removed from chunks.csv, so thinning the chunk set leaves dead files
behind. This deletes any cached file whose id no longer appears in chunks.csv,
and drops the matching entries from the manifest.

Defaults to a dry run — pass --apply to actually delete. Stale-but-live files
(an edited chunk's old audio) are left alone: they share a live id and get
overwritten by the next `generate`/`anki` run via the content manifest.
"""

import argparse
import csv
from pathlib import Path

from scripts.config import AUDIO_DIR, CHUNKS_CSV
from scripts.model import Chunk
from scripts.store import Manifest


def live_ids(csv_path: Path) -> set[str]:
    """Return the set of chunk ids currently in chunks.csv."""
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        return {row[0] for row in reader if row}


def find_orphans(audio_dir: Path, ids: set[str]) -> list[Path]:
    """Return audio files whose id is not among the live chunk ids.

    Files that aren't per-chunk cache files are left alone (not ours to prune).
    """
    orphans: list[Path] = []
    for path in sorted(audio_dir.glob("*.mp3")):
        try:
            cid = Chunk.id_from_audio_filename(path.name)
        except ValueError:
            continue
        if cid not in ids:
            orphans.append(path)
    return orphans


def prune(audio_dir: Path, csv_path: Path, *, apply: bool) -> int:
    """Report (and with apply=True, delete) orphaned cache files.

    Returns the number of orphan files found.
    """
    if not audio_dir.exists():
        print(f"No audio dir at {audio_dir}; nothing to prune.")
        return 0

    ids = live_ids(csv_path)
    orphans = find_orphans(audio_dir, ids)
    dead_ids = {Chunk.id_from_audio_filename(p.name) for p in orphans}

    if not orphans:
        print(f"OK: no orphans ({len(ids)} live chunks).")
        return 0

    print(f"{len(orphans)} orphan file(s) across {len(dead_ids)} dead id(s):")
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

    manifest = Manifest.load(audio_dir)
    removed = [cid for cid in manifest if cid not in ids]
    for cid in removed:
        del manifest[cid]
    if removed:
        manifest.save(audio_dir)

    print(
        f"Deleted {len(orphans)} file(s); "
        f"dropped {len(removed)} {Manifest.FILENAME} entr(y/ies)."
    )
    print(
        "Note: Anki cards for removed chunks are not deleted automatically — "
        "remove them by hand in Anki (genanki only adds/updates)."
    )
    return len(orphans)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="prune",
        description="Delete orphaned audio cache files (ids gone from chunks.csv)",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually delete (default is a dry run)",
    )
    args = parser.parse_args()
    prune(AUDIO_DIR, CHUNKS_CSV, apply=args.apply)


if __name__ == "__main__":
    main()
