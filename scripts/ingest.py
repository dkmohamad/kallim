"""Ingest extracted vocab candidates into review-ready chunks.

Reads a candidates CSV (arabic,english,register,topic) written by the
``extract-vocab`` skill's first-pass agent and, deduping against chunks.csv:
assigns each new candidate an id, validates it against the taxonomy, and writes
``vocab_chunks_review.csv`` for human review. With ``--append`` it commits the
(human-edited) review CSV into ``chunks.csv``.

The review CSV is the one file in the pipeline a human edits, and a build
overwrites it wholesale, so a build refuses to run while it still holds rows.

All language work — extraction, translation, register/tag classification —
happens in the skill and its sub-agent. This command is the deterministic,
tested tail: dedup, id assignment, validation, and the CSV write. Both the
build and append steps dedup against chunks.csv (diacritics-insensitive), so
``--append`` is idempotent and a hand-edited duplicate can't slip through.
"""

import argparse
import csv
import logging
import sys
from pathlib import Path

from .chunks import Chunks
from .config import CHUNKS_CSV, VOCAB_CHUNKS_REVIEW_CSV, VOCAB_PAIRS_CSV
from .model import Chunk, VocabEntry
from .utils import (
    append_csv_rows,
    generate_id,
    normalize_arabic,
    read_csv_rows,
    setup_logging,
    write_csv_rows,
)

__all__ = [
    "append_review",
    "build_review",
    "load_vocab_pairs",
    "pending_review_rows",
    "run",
]

logger = logging.getLogger(__name__)


def load_vocab_pairs(path: Path) -> list[VocabEntry]:
    """Load vocab candidates from a CSV in ``VocabEntry.FIELDS`` order.

    Args:
        path: Path to a ``.csv`` with the vocab columns (the trailing
            ``priority`` may be omitted) and a header.

    Returns:
        One VocabEntry per row, with register as an enum member.

    Raises:
        ValueError: If ``path`` isn't a CSV (a bare word list has no register
            or topic, so it can't become chunks), or a row is invalid.
    """
    if path.suffix != ".csv":
        raise ValueError(
            f"{path} is not a .csv; candidates need "
            + ", ".join(VocabEntry.FIELDS[:-1])
            + " columns (a plain word list carries no register or topic)"
        )
    return read_csv_rows(path, VocabEntry.from_row)


def pending_review_rows(review_path: Path) -> int:
    """How many rows the review CSV is currently holding, 0 if it has none.

    Counted structurally rather than by parsing each row: this is called to
    decide whether overwriting would destroy work, and a half-edited file that
    no longer validates is exactly the one most worth protecting.
    """
    try:
        with review_path.open(newline="", encoding="utf-8") as f:
            return max(sum(1 for _ in csv.reader(f)) - 1, 0)  # less the header
    except FileNotFoundError:
        return 0


def build_review(
    candidates_path: Path,
    chunks_path: Path,
    review_path: Path,
    *,
    force: bool = False,
) -> int:
    """Dedup candidates against chunks.csv, then id + validate into a review CSV.

    Dedups both against ``chunks.csv`` and within the batch, so two candidates
    that fold to the same Arabic (e.g. one vocalized, one bare) yield one chunk.

    **The review CSV is overwritten wholesale, and it is where human edits
    live** — so a build refuses to run while it still holds rows. Those rows are
    either unreviewed or hand-corrected, and in both cases they are work that
    exists nowhere else: the candidates file they came from has already been
    consumed, so there is nothing to rebuild them from. Commit them with
    ``--append`` first, or pass ``force`` to discard them deliberately.

    Args:
        candidates_path: The agent-written candidates CSV.
        chunks_path: The chunks.csv to dedup against (diacritics-insensitive).
        review_path: Where to write the review CSV (Chunk.FIELDS columns, ids).
        force: Overwrite the review CSV even when it still holds rows.

    Returns:
        The number of new chunks written.

    Raises:
        FileExistsError: If the review CSV holds rows and ``force`` is not set.
    """
    if not force and (pending := pending_review_rows(review_path)):
        raise FileExistsError(
            f"{review_path} still holds {pending} row(s) awaiting review, and a "
            "build overwrites it wholesale — any edits to them would be lost. "
            "Commit them first with `kallim ingest --append`, or re-run with "
            "--force to discard them."
        )
    candidates = load_vocab_pairs(candidates_path)
    seen = _normalized_existing(chunks_path)
    fresh: list[VocabEntry] = []
    for entry in candidates:
        key = normalize_arabic(entry.arabic)
        if key in seen:
            continue
        seen.add(key)
        fresh.append(entry)

    chunks = [entry.to_chunk(generate_id()) for entry in fresh]
    review_path.parent.mkdir(parents=True, exist_ok=True)  # scratch/ may not exist
    write_csv_rows(review_path, Chunk.FIELDS, (chunk.to_row() for chunk in chunks))

    logger.info("Candidates: %d", len(candidates))
    logger.info("  Duplicates skipped: %d", len(candidates) - len(chunks))
    logger.info("Wrote %d new chunks to %s", len(chunks), review_path)
    logger.info("Review this file, then run `kallim ingest --append`.")
    return len(chunks)


def append_review(review_path: Path, chunks_path: Path) -> int:
    """Append the reviewed chunks to chunks.csv, skipping any already present.

    Each reviewed row is round-tripped through ``Chunk.from_row`` so an
    off-taxonomy edit fails loudly, then deduped against ``chunks.csv`` — so a
    hand-added duplicate is dropped and re-running ``--append`` is a no-op.

    Args:
        review_path: The (human-edited) review CSV to commit.
        chunks_path: The chunks.csv to append to (and dedup against).

    Returns:
        The number of chunks actually appended.
    """
    existing = _normalized_existing(chunks_path)
    reviewed = _validated_chunks(review_path)
    fresh = [c for c in reviewed if normalize_arabic(c.arabic.text) not in existing]
    append_csv_rows(chunks_path, (chunk.to_row() for chunk in fresh))

    logger.info("Appended %d chunks to %s", len(fresh), chunks_path)
    if skipped := len(reviewed) - len(fresh):
        logger.info("  Skipped %d already in chunks.csv", skipped)
    logger.info("Run `kallim lint` to validate the taxonomy.")
    return len(fresh)


def run(args: argparse.Namespace) -> None:
    """Build the review CSV, or (with --append) commit it into chunks.csv.

    Misuse and the overwrite guard are expected outcomes, not crashes, so they
    exit with the message alone. A traceback here would bury the one line that
    says what to do next under a stack the user can do nothing with.
    """
    setup_logging()
    try:
        if args.append:
            if args.candidates:
                raise ValueError(
                    "`--append` commits vocab_chunks_review.csv; don't also pass "
                    "a candidates file (run `kallim ingest <file>` first, then "
                    "--append)"
                )
            append_review(VOCAB_CHUNKS_REVIEW_CSV, CHUNKS_CSV)
            return
        candidates = Path(args.candidates) if args.candidates else VOCAB_PAIRS_CSV
        build_review(candidates, CHUNKS_CSV, VOCAB_CHUNKS_REVIEW_CSV, force=args.force)
    except (FileExistsError, ValueError) as exc:
        sys.exit(f"Error: {exc}")


def _normalized_existing(chunks_path: Path) -> set[str]:
    """Normalized Arabic already in chunks.csv (empty if it doesn't exist)."""
    try:
        return Chunks.load(chunks_path).arabic_keys()
    except FileNotFoundError:
        return set()


def _validated_chunks(review_path: Path) -> list[Chunk]:
    """Read the review CSV, validating each row via ``Chunk.from_row``."""
    return read_csv_rows(review_path, Chunk.from_row)
