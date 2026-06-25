#!/usr/bin/env python3
"""Persistence: loading chunks from chunks.csv."""

import csv
from pathlib import Path

from scripts.model import Chunk


def load_chunks(path: Path) -> list[Chunk]:
    """Load all chunks from the CSV file.

    Raises:
        FileNotFoundError: If ``path`` doesn't exist.
        ValueError: If a row is malformed/off-taxonomy, or the file has no chunks.
    """
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        chunks = [Chunk.from_row(row) for row in reader]
    if not chunks:
        raise ValueError(f"no chunks in {path}")
    return chunks
