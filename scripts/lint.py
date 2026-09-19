"""Kallim — Validate a chunk bank.

Two checks. Per row: build a Chunk from it, so malformed rows, an unknown
register and an unregistered topic are reported with their line number (the
rules live on Chunk in scripts.model). Across rows: duplicate ids, and two rows
whose Arabic folds to the same identity once diacritics are stripped.

The duplicate check lives **here** rather than in the harvest because a row
can reach the bank by more than one route — an agent editing the file, a hand
edit, a paste — and a check that only guards one of them guards nothing. Lint
sees the finished file, so it catches a duplicate however it arrived.

Exits non-zero if anything is wrong, so it can gate a commit.
"""

import argparse
import csv
import sys
from pathlib import Path

from .config import CHUNKS_CSV
from .model import Chunk
from .utils import normalize_arabic

__all__ = ["lint_chunks", "run"]


def lint_chunks(path: Path) -> tuple[str, int]:
    """Validate every row; return ``(report, problem_count)``.

    The report lists each problem with its line number, then a FAIL/OK summary.
    """
    errors: list[str] = []
    total = 0
    ids: dict[str, int] = {}
    arabic: dict[str, tuple[int, str]] = {}

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for lineno, row in enumerate(reader, start=2):
            total += 1
            try:
                chunk = Chunk.from_row(row)
            except ValueError as exc:
                rid = row[0] if row else "?"
                errors.append(f"  line {lineno} ({rid}): {exc}")
                continue

            if (first := ids.get(chunk.id)) is not None:
                errors.append(
                    f"  line {lineno} ({chunk.id}): duplicate id, already used on "
                    f"line {first}"
                )
            else:
                ids[chunk.id] = lineno

            # Diacritics-insensitive, so a vocalized row and a bare re-entry of
            # the same phrase collide — which is the common way a duplicate gets
            # in, since the two look different on screen.
            key = normalize_arabic(chunk.arabic.text)
            if (prior := arabic.get(key)) is not None:
                errors.append(
                    f"  line {lineno} ({chunk.id}): Arabic duplicates line "
                    f"{prior[0]} ({prior[1]}) once diacritics are stripped"
                )
            else:
                arabic[key] = (lineno, chunk.id)

    summary = (
        f"FAIL: {len(errors)} problem(s) across {total} chunks."
        if errors
        else f"OK: {total} chunks, no problems."
    )
    return "\n".join([*errors, "", summary]), len(errors)


def run(args: argparse.Namespace) -> str:
    """Validate the chunks CSV; exit non-zero (via stderr) if any row is invalid."""
    path = Path(args.input) if args.input else CHUNKS_CSV
    report, problems = lint_chunks(path)
    if problems:
        sys.exit(report)
    return report
