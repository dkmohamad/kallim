"""The chunks.csv loader and the Chunks collection — the chunk side of persistence.

``Chunks`` is the domain collection of chunks: it loads chunks.csv
(``Chunks.load``), narrows to a concept_tag (``section``), groups into ``Section``
output units (``sections``), and owns the identity lookups ingest/prune dedup on
(``arabic_keys``/``audio_keys``). No audio dependencies live here — the
content-addressed audio cache is ``scripts.cache``.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from .model import Chunk, ConceptTag, Register
from .utils import normalize_arabic, read_csv_rows

__all__ = ["Chunks", "Section"]


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

    def slug(self, index: int) -> str:
        """Filename stem for this section's outputs, e.g. ``03_dining_egyptian``."""
        return f"{index:02d}_{self.tag}_{self.register}"

    def transcript(self) -> str:
        """The section transcript: a title then numbered english/arabic pairs."""
        title = self.label.replace("_", " ").title()
        lines = [f"=== {title} ===\n"]
        for idx, chunk in enumerate(self.chunks, 1):
            lines.append(f"{idx}. {chunk.english.text}")
            lines.append(f"   {chunk.arabic.text}\n")
        return "\n".join(lines)


class Chunks(Collection[Chunk]):
    """The collection of chunks, owning the chunk-set operations callers need.

    Loads from CSV (``load``), narrows to one concept_tag (``section``), groups
    into ``Section`` output units (``sections``), and derives the identity sets
    ingest and prune dedup on: ``arabic_keys`` (diacritics-insensitive dedup) and
    ``audio_keys`` (every utterance's audio content key, for orphan detection).
    """

    def __init__(self, chunks: Iterable[Chunk] = ()) -> None:
        self._chunks = list(chunks)

    @classmethod
    def load(cls, path: Path) -> Chunks:
        """Load the chunks from a CSV.

        Raises:
            FileNotFoundError: If ``path`` doesn't exist.
            ValueError: If a row is malformed/off-taxonomy, or the file is empty.
        """
        chunks = cls(read_csv_rows(path, Chunk.from_row))
        if not chunks:
            raise ValueError(f"no chunks in {path}")
        return chunks

    def __contains__(self, item: object) -> bool:
        return item in self._chunks

    def __iter__(self) -> Iterator[Chunk]:
        return iter(self._chunks)

    def __len__(self) -> int:
        return len(self._chunks)

    def section(self, tag: ConceptTag | None) -> Chunks:
        """Narrow to a single concept_tag; all chunks when ``tag`` is None.

        Raises:
            ValueError: If ``tag`` is given but no chunk carries it.
        """
        if tag is None:
            return self
        selected = Chunks(c for c in self if c.concept_tag == tag)
        if not selected:
            raise ValueError(f"section {tag!r} not found")
        return selected

    def sections(self) -> list[Section]:
        """Group into ``Section`` units by (concept_tag, Arabic register).

        Preserves first-seen order, so the output sections follow the CSV. Shared
        by the real run (``generate``) and the dry-run report (``plan``) so both
        see the same sectioning.
        """
        groups: dict[tuple[ConceptTag, Register], list[Chunk]] = {}
        for chunk in self:
            key = (chunk.concept_tag, chunk.arabic.register)
            groups.setdefault(key, []).append(chunk)
        return [Section(tag, reg, cs) for (tag, reg), cs in groups.items()]

    def arabic_keys(self) -> set[str]:
        """Diacritics-insensitive Arabic identities, for dedup."""
        return {normalize_arabic(c.arabic.text) for c in self._chunks}

    def audio_keys(self) -> set[str]:
        """Content keys of every utterance's audio, for orphan detection."""
        return {utt.key for c in self._chunks for utt in c.utterances}
