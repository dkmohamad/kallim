#!/usr/bin/env python3
"""Kallim domain model — the Chunk entity and its concept_tag taxonomy.

Pure data types with no pipeline/service dependencies (no ElevenLabs, no audio
I/O), so loaders, the linter, and the generator can all share one definition of
what a chunk is.
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from scripts.utils import content_hash


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
    # Audio is content-addressed: each side's file is named by the hash of its
    # text, so editing a chunk changes the filename and the cache self-invalidates
    # (the old file becomes an orphan for `prune`); identical text dedups. This is
    # the *content* identity, distinct from the frozen-dataclass __hash__ used for
    # in-memory set/dict membership.

    @property
    def en_cache_key(self) -> str:
        """Content hash of the English side."""
        return content_hash(self.english)

    @property
    def ar_cache_key(self) -> str:
        """Content hash of the Arabic side.

        Folds in ``register`` because it selects the voice, so a register change
        invalidates even when the Arabic text is unchanged.
        """
        return content_hash(f"{self.register}\n{self.arabic}")

    @property
    def en_filename(self) -> str:
        """Content-addressed cache filename for the English audio."""
        return f"{self.en_cache_key}.mp3"

    @property
    def ar_filename(self) -> str:
        """Content-addressed cache filename for the Arabic audio."""
        return f"{self.ar_cache_key}.mp3"

    def audio_paths(self, audio_dir: Path) -> tuple[Path, Path]:
        """(english, arabic) cache file paths under ``audio_dir``."""
        return audio_dir / self.en_filename, audio_dir / self.ar_filename
