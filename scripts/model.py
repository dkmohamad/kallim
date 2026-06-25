#!/usr/bin/env python3
"""Kallim domain model — the Chunk entity and its concept_tag taxonomy.

Pure data types with no pipeline/service dependencies (no ElevenLabs, no audio
I/O), so loaders, the linter, and the generator can all share one definition of
what a chunk is.
"""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from scripts.utils import content_hash

# Per-chunk audio cache filename scheme: audio/{id}_en.mp3, audio/{id}_ar.mp3.
# Owned here (and surfaced on Chunk) so both generate and prune agree on it.
_AUDIO_FILENAME_RE = re.compile(r"^(?P<id>.+)_(?:en|ar)\.mp3$")


class Register(StrEnum):
    """Arabic register / voice role."""

    ENGLISH = "english"
    EGYPTIAN = "egyptian"
    MSA = "msa"
    IRAQI = "iraqi"


class ConceptTag(StrEnum):
    """Canonical concept_tag values — the source of truth for chunks.csv.

    Two co-existing schemes (see ``SITUATIONAL_TAGS`` / ``TOPICAL_TAGS``):
    Egyptian chunks use situational travel-phrasebook tags; MSA/Iraqi chunks
    use abstract conversation topics. ``greetings`` is shared by both.
    """

    # Situational (Egyptian travel-phrasebook situations)
    GREETINGS = "greetings"
    SMALLTALK = "smalltalk"
    DINING = "dining"
    HOTEL = "hotel"
    TAXIS = "taxis"
    DIRECTIONS = "directions"
    SIGHTSEEING = "sightseeing"
    BEACH_AND_VENDORS = "beach_and_vendors"
    SHOPPING = "shopping"
    MONEY = "money"
    # Topical (MSA / Iraqi conversation topics)
    FOOD = "food"
    TRAVEL = "travel"
    PEOPLE = "people"
    FAMILY = "family"
    EMOTIONS = "emotions"
    LEISURE = "leisure"
    DAILY_LIFE = "daily_life"
    CULTURE = "culture"
    WORK = "work"
    HEALTH = "health"


# Tags valid for the Egyptian situational scheme.
SITUATIONAL_TAGS = frozenset({
    ConceptTag.GREETINGS, ConceptTag.SMALLTALK, ConceptTag.DINING,
    ConceptTag.HOTEL, ConceptTag.TAXIS, ConceptTag.DIRECTIONS,
    ConceptTag.SIGHTSEEING, ConceptTag.BEACH_AND_VENDORS,
    ConceptTag.SHOPPING, ConceptTag.MONEY,
})

# Tags valid for the MSA / Iraqi topical scheme.
TOPICAL_TAGS = frozenset({
    ConceptTag.GREETINGS, ConceptTag.FOOD, ConceptTag.TRAVEL,
    ConceptTag.PEOPLE, ConceptTag.FAMILY, ConceptTag.EMOTIONS,
    ConceptTag.LEISURE, ConceptTag.DAILY_LIFE, ConceptTag.CULTURE,
    ConceptTag.WORK, ConceptTag.HEALTH,
})

# Which tag scheme each register is allowed to draw from.
ALLOWED_TAGS_BY_REGISTER = {
    Register.EGYPTIAN: SITUATIONAL_TAGS,
    Register.MSA: TOPICAL_TAGS,
    Register.IRAQI: TOPICAL_TAGS,
}


@dataclass(frozen=True, slots=True)
class Chunk:
    """A single phrase pair from chunks.csv.

    Validates its register and concept_tag on construction, so a Chunk cannot
    exist with a register or tag outside the taxonomy (see ConceptTag and
    ALLOWED_TAGS_BY_REGISTER).
    """

    id: str
    arabic: str
    english: str
    register: Register
    concept_tag: ConceptTag

    def __post_init__(self) -> None:
        allowed = ALLOWED_TAGS_BY_REGISTER.get(self.register)
        if allowed is not None and self.concept_tag not in allowed:
            raise ValueError(
                f"concept_tag {self.concept_tag.value!r} not allowed for "
                f"register {self.register.value!r}"
            )

    @classmethod
    def from_row(cls, row: list[str]) -> "Chunk":
        """Build a Chunk from a raw CSV row, coercing register/concept_tag.

        Raises:
            ValueError: If the row has the wrong field count, or its register
                or concept_tag is outside the taxonomy.
        """
        try:
            cid, arabic, english, register, concept_tag = row
        except ValueError:
            field_count = len(cls.__dataclass_fields__)
            raise ValueError(
                f"expected {field_count} fields, got {len(row)}: {row!r}"
            ) from None
        try:
            reg = Register(register)
        except ValueError:
            raise ValueError(f"unknown register {register!r}") from None
        try:
            tag = ConceptTag(concept_tag)
        except ValueError:
            raise ValueError(f"unknown concept_tag {concept_tag!r}") from None
        return cls(cid, arabic, english, reg, tag)

    # --- audio cache binding --------------------------------------------------
    # The chunk owns its cache filename convention and content identity, so
    # generate (writer) and prune (reader) share one source of truth. Note this
    # is the *content* identity (SHA-256, persistable), distinct from the
    # frozen-dataclass __hash__ used for in-memory set/dict membership.

    @property
    def en_filename(self) -> str:
        """Cache filename for this chunk's English audio."""
        return f"{self.id}_en.mp3"

    @property
    def ar_filename(self) -> str:
        """Cache filename for this chunk's Arabic audio."""
        return f"{self.id}_ar.mp3"

    def audio_paths(self, audio_dir: Path) -> tuple[Path, Path]:
        """(english, arabic) cache file paths under ``audio_dir``."""
        return audio_dir / self.en_filename, audio_dir / self.ar_filename

    def segments[Clip](
        self, audio_dir: Path, load: Callable[[Path], Clip]
    ) -> tuple[Clip, Clip]:
        """The chunk's (english, arabic) audio, decoded from its cache files.

        ``load`` is the decoder (see scripts.audio.load_clip). Taking it as a
        parameter keeps the model free of any audio library, and being generic
        over the clip type means callers get their concrete type back.
        """
        en_path, ar_path = self.audio_paths(audio_dir)
        return load(en_path), load(ar_path)

    @property
    def en_cache_key(self) -> str:
        """Stable content hash of the English side (invalidates on text edit)."""
        return content_hash(self.english)

    @property
    def ar_cache_key(self) -> str:
        """Stable content hash of the Arabic side.

        Folds in ``register`` because it selects the voice, so a register change
        must invalidate even when the Arabic text is unchanged.
        """
        return content_hash(f"{self.register}\n{self.arabic}")

    @staticmethod
    def id_from_audio_filename(filename: str) -> str:
        """Inverse of en_filename/ar_filename: the chunk id for a cache file.

        Raises:
            ValueError: If the name isn't a per-chunk audio cache file.
        """
        match = _AUDIO_FILENAME_RE.match(filename)
        if match is None:
            raise ValueError(f"not a chunk audio filename: {filename!r}")
        return match["id"]


@dataclass(frozen=True, slots=True)
class Section:
    """A group of chunks sharing a concept_tag and register.

    generate renders one transcript + MP3 per section; ``label`` and ``prefix``
    are the single source of truth for those names.
    """

    concept_tag: ConceptTag
    register: Register
    chunks: tuple[Chunk, ...]

    @property
    def label(self) -> str:
        """Human-readable name, e.g. 'dining (egyptian)'."""
        return f"{self.concept_tag} ({self.register})"

    def prefix(self, index: int) -> str:
        """Output filename stem, e.g. '03_dining_egyptian'."""
        return f"{index:02d}_{self.concept_tag}_{self.register}"

    def transcript_text(self) -> str:
        """Human-readable transcript: a title then numbered english/arabic pairs."""
        title = self.label.replace("_", " ").title()
        lines = [f"=== {title} ===\n"]
        for idx, chunk in enumerate(self.chunks, 1):
            lines.append(f"{idx}. {chunk.english}")
            lines.append(f"   {chunk.arabic}\n")
        return "\n".join(lines)

    @classmethod
    def group(cls, chunks: Iterable[Chunk]) -> list["Section"]:
        """Group chunks by (concept_tag, register).

        Preserves the order each (concept_tag, register) pair is first seen.
        """
        buckets: dict[tuple[ConceptTag, Register], list[Chunk]] = {}
        for chunk in chunks:
            buckets.setdefault((chunk.concept_tag, chunk.register), []).append(chunk)
        return [cls(tag, reg, tuple(cs)) for (tag, reg), cs in buckets.items()]
