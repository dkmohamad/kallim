"""The chunks.csv loader and chunk grouping — the chunk side of persistence.

``load_chunks`` reads the source-of-truth CSV into the domain ``Chunk`` model;
``select_section`` filters to one concept_tag; ``group_sections`` groups chunks
into the ``Section`` units ``generate`` writes one MP3 per (and the dry-run
report tallies per). No audio dependencies live here — the content-addressed
audio cache is ``scripts.cache``.
"""

from __future__ import annotations

import csv
from collections.abc import Collection, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from .model import Chunk, ConceptTag, Register
from .utils import normalize_arabic

__all__ = ["Chunks", "Section", "group_sections", "load_chunks", "select_section"]


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


class Chunks(Collection[Chunk]):
    """A collection of chunks owning the identity lookups its callers need.

    ``arabic_keys`` are diacritics-insensitive dedup identities — ingest keeps a
    candidate only when its key isn't already among them. ``audio_keys`` are the
    content keys of every utterance's audio — prune deletes a cache file whose
    key is no longer among them. Both used to be re-derived by hand at each call
    site; they live here so the identity rule is defined once.
    """

    def __init__(self, chunks: Iterable[Chunk] = ()) -> None:
        self._chunks = list(chunks)

    @classmethod
    def load(cls, path: Path) -> Chunks:
        """Load the chunks from a CSV (raises like ``load_chunks`` if absent)."""
        return cls(load_chunks(path))

    def __contains__(self, item: object) -> bool:
        return item in self._chunks

    def __iter__(self) -> Iterator[Chunk]:
        return iter(self._chunks)

    def __len__(self) -> int:
        return len(self._chunks)

    def arabic_keys(self) -> set[str]:
        """Diacritics-insensitive Arabic identities, for dedup."""
        return {normalize_arabic(c.arabic.text) for c in self._chunks}

    def audio_keys(self) -> set[str]:
        """Content keys of every utterance's audio, for orphan detection."""
        return {utt.key for c in self._chunks for utt in c.utterances}


def select_section(chunks: list[Chunk], tag: str | None) -> list[Chunk]:
    """Filter chunks to a single concept_tag; return all when ``tag`` is None.

    Args:
        chunks: The chunks to filter.
        tag: The concept_tag to keep, or None for no filtering.

    Returns:
        The matching chunks (all of them when ``tag`` is None).

    Raises:
        ValueError: If ``tag`` is given but no chunk carries it.
    """
    if tag is None:
        return chunks
    selected = [c for c in chunks if c.concept_tag == tag]
    if not selected:
        raise ValueError(f"section {tag!r} not found")
    return selected


@dataclass(frozen=True, slots=True)
class Section:
    """Chunks sharing a concept_tag and Arabic register — one output unit.

    The group ``generate`` writes a single MP3 (and transcript) per, and the
    dry-run report tallies per. Owns its own ``label`` so the real run and the
    dry run can't format it differently.
    """

    tag: ConceptTag
    register: Register
    chunks: list[Chunk]

    @property
    def label(self) -> str:
        """Human label for the section, e.g. ``greetings (egyptian)``."""
        return f"{self.tag} ({self.register})"


def group_sections(chunks: list[Chunk]) -> list[Section]:
    """Group chunks into sections by (concept_tag, Arabic register).

    Preserves first-seen order, so the output sections follow the CSV. Shared by
    the real run (``generate``) and the dry-run report (``plan``) so both see the
    same sectioning.
    """
    groups: dict[tuple[ConceptTag, Register], list[Chunk]] = {}
    for chunk in chunks:
        groups.setdefault((chunk.concept_tag, chunk.arabic.register), []).append(chunk)
    return [Section(tag, reg, cs) for (tag, reg), cs in groups.items()]
