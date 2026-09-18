"""Kallim — Prune orphaned audio cache files.

Audio is content-addressed: each file is named ``audio/<key>.mp3``. A file is an
orphan when its key is no longer produced by any chunk in *any* bank — the chunk
was removed, or its text was edited (which changes the key and leaves the old
file behind). This deletes those files.

Every bank counts, not just chunks.csv: the Egyptian bank is frozen out of the
default scope but its audio is still wanted, so pruning against chunks.csv alone
would report all of it as orphaned.

Defaults to a dry run — pass --apply to actually delete.
"""

import argparse
from collections.abc import Iterable
from pathlib import Path

from .cache import AudioCache
from .chunks import Chunks
from .config import BANK_CSVS

__all__ = ["live_keys", "prune", "run"]


def live_keys(csv_paths: Iterable[Path]) -> set[str]:
    """The content keys (English + Arabic) produced by any chunk in any bank.

    A missing bank is an error, not an empty contribution. Skipping it would
    make every key that only that bank produces look orphaned, and
    ``prune --apply`` would then delete audio that is still wanted — the exact
    failure ``test_load_raises_when_the_csv_is_absent`` exists to prevent, one
    layer up.

    Raises:
        FileNotFoundError: If a bank is missing, naming which one.
    """
    keys: set[str] = set()
    for path in csv_paths:
        try:
            keys |= Chunks.load(path).audio_keys()
        except FileNotFoundError:
            raise FileNotFoundError(f"bank not found: {path}") from None
    return keys


def prune(cache: AudioCache, csv_paths: Iterable[Path], *, apply: bool) -> str:
    """Report orphaned cache files (and with apply=True, delete them).

    Returns the report text; the caller (the CLI) prints it.
    """
    orphans = sorted(set(cache) - live_keys(csv_paths))

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
    return prune(AudioCache(), BANK_CSVS, apply=args.apply)
