#!/usr/bin/env python3
"""Persistence: loading chunks from chunks.csv and the audio cache manifest."""

import csv
import json
from collections.abc import Iterator, MutableMapping
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


class Manifest(MutableMapping[str, dict[str, str]]):
    """Audio cache sidecar mapping chunk id -> {"en": <hash>, "ar": <hash>}.

    The hashes let the cache tell when a chunk's text changed (the id alone is
    content-blind). Behaves as a plain mutable mapping; ``load``/``save`` bind it
    to ``audio_dir / FILENAME``.
    """

    FILENAME = "manifest.json"

    def __init__(self, data: dict[str, dict[str, str]] | None = None) -> None:
        self._data: dict[str, dict[str, str]] = dict(data or {})

    def __getitem__(self, key: str) -> dict[str, str]:
        return self._data[key]

    def __setitem__(self, key: str, value: dict[str, str]) -> None:
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    @classmethod
    def load(cls, audio_dir: Path) -> "Manifest":
        """Load the manifest from ``audio_dir``, or an empty one if absent."""
        path = audio_dir / cls.FILENAME
        if path.exists():
            return cls(json.loads(path.read_text(encoding="utf-8")))
        return cls()

    def save(self, audio_dir: Path) -> None:
        """Persist the manifest to ``audio_dir``."""
        path = audio_dir / self.FILENAME
        path.write_text(
            json.dumps(self._data, ensure_ascii=False, sort_keys=True, indent=0),
            encoding="utf-8",
        )
