#!/usr/bin/env python3
"""Kallim — Validate chunks.csv against the canonical taxonomy.

Builds a Chunk from every row; rows that fail construction (malformed, unknown
register/tag, or a tag outside the register's scheme — the rules live on Chunk
in scripts.generate) are reported with their line number. Exits non-zero if any
row is invalid, so it can gate commits.
"""

import csv
import sys
from pathlib import Path

from scripts.generate import CHUNKS_CSV, Chunk


def lint_chunks(path: Path) -> int:
    """Validate every row; print problems with line numbers. Return the count."""
    errors: list[str] = []
    total = 0
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for lineno, row in enumerate(reader, start=2):
            total += 1
            try:
                Chunk.from_row(row)
            except ValueError as exc:
                rid = row[0] if row else "?"
                errors.append(f"  line {lineno} ({rid}): {exc}")

    for line in errors:
        print(line)
    print()
    if errors:
        print(f"FAIL: {len(errors)} problem(s) across {total} chunks.")
    else:
        print(f"OK: {total} chunks, no problems.")
    return len(errors)


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else CHUNKS_CSV
    sys.exit(1 if lint_chunks(path) else 0)


if __name__ == "__main__":
    main()
