"""Ingest extracted vocab candidates into review-ready chunks.

Reads a candidates CSV (arabic,english,register,concept_tag) written by the
``extract-vocab`` skill's first-pass agent and, deduping against chunks.csv:
assigns each new candidate an id, validates it against the taxonomy, and writes
``vocab_chunks_review.csv`` for human review. With ``--append`` it commits the
(human-edited) review CSV into ``chunks.csv``.

All language work — extraction, translation, register/tag classification —
happens in the skill and its sub-agent. This command is the deterministic,
tested tail: dedup, id assignment, validation, and the CSV write. Both the
build and append steps dedup against chunks.csv (diacritics-insensitive), so
``--append`` is idempotent and a hand-edited duplicate can't slip through.
"""

import argparse
import logging
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
    "run",
]

logger = logging.getLogger("kallim.ingest")


def load_vocab_pairs(path: Path) -> list[VocabEntry]:
    """Load vocab candidates from a CSV in ``VocabEntry.FIELDS`` order.

    Args:
        path: Path to a ``.csv`` with the vocab columns (the trailing
            ``priority`` may be omitted) and a header.

    Returns:
        One VocabEntry per row, with register/concept_tag as taxonomy members.

    Raises:
        ValueError: If ``path`` isn't a CSV (a bare word list has no register or
            concept_tag, so it can't become chunks), or a row is off-taxonomy.
    """
    if path.suffix != ".csv":
        raise ValueError(
            f"{path} is not a .csv; candidates need arabic,english,register,"
            "concept_tag columns (a plain word list carries no register/tag)"
        )
    return read_csv_rows(path, VocabEntry.from_row)


def build_review(candidates_path: Path, chunks_path: Path, review_path: Path) -> int:
    """Dedup candidates against chunks.csv, then id + validate into a review CSV.

    Dedups both against ``chunks.csv`` and within the batch, so two candidates
    that fold to the same Arabic (e.g. one vocalized, one bare) yield one chunk.

    Args:
        candidates_path: The agent-written candidates CSV.
        chunks_path: The chunks.csv to dedup against (diacritics-insensitive).
        review_path: Where to write the review CSV (Chunk.FIELDS columns, ids).

    Returns:
        The number of new chunks written.
    """
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
    """Build the review CSV, or (with --append) commit it into chunks.csv."""
    setup_logging()
    if args.append:
        if args.candidates:
            raise ValueError(
                "`--append` commits vocab_chunks_review.csv; don't also pass a "
                "candidates file (run `kallim ingest <file>` first, then --append)"
            )
        append_review(VOCAB_CHUNKS_REVIEW_CSV, CHUNKS_CSV)
        return
    candidates = Path(args.candidates) if args.candidates else VOCAB_PAIRS_CSV
    build_review(candidates, CHUNKS_CSV, VOCAB_CHUNKS_REVIEW_CSV)


def _normalized_existing(chunks_path: Path) -> set[str]:
    """Normalized Arabic already in chunks.csv (empty if it doesn't exist)."""
    try:
        return Chunks.load(chunks_path).arabic_keys()
    except FileNotFoundError:
        return set()


def _validated_chunks(review_path: Path) -> list[Chunk]:
    """Read the review CSV, validating each row via ``Chunk.from_row``."""
    return read_csv_rows(review_path, Chunk.from_row)
