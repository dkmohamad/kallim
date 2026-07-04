"""Kallim domain model — utterances, chunks, and the concept_tag taxonomy.

Pure data types with no audio/pipeline dependencies (no pydub, no ElevenLabs).
A Chunk pairs an English and an Arabic Utterance; an Utterance is text + the
voice it's said in, and owns its content-addressed audio *identity* (``key``).
Synthesis itself is done by the ``Synthesiser`` port (a callable), passed in by
the caller; the resulting bytes live in the audio cache. A ``VocabEntry`` is a
candidate row on its way to becoming a ``Chunk`` (see ``ingest``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Protocol

from .utils import content_hash

__all__ = [
    "ALLOWED_TAGS_BY_REGISTER",
    "Chunk",
    "ConceptTag",
    "PlayableAudio",
    "Register",
    "SITUATIONAL_TAGS",
    "Synthesiser",
    "TOPICAL_TAGS",
    "Utterance",
    "VocabEntry",
]


class PlayableAudio(Protocol):
    """Playable audio data — e.g. a pydub AudioSegment.

    The model's type for actual sound: clips concatenate (``+``). The concrete
    type and all heavy ops live in the audio layer, so the model needs no audio
    library. Identity is the utterance's ``key``, not the audio's.
    """

    def __add__(self, other: PlayableAudio) -> PlayableAudio: ...


# The model's port for text-to-speech: an utterance -> playable audio. The
# concrete engine (ElevenLabs) lives in the audio layer and is *passed in* by the
# caller (e.g. to ensure_cached), so the model declares the capability without
# importing any audio library. Just a Callable — the port has a single operation.
type Synthesiser = Callable[[Utterance], PlayableAudio]


class Register(StrEnum):
    """Voice role of an utterance (selects the TTS voice)."""

    ENGLISH = "english"
    EGYPTIAN = "egyptian"
    MSA = "msa"
    IRAQI = "iraqi"

    @property
    def label(self) -> str:
        """Full human-readable register name (for prompts and display)."""
        return _REGISTER_LABELS[self]


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
SITUATIONAL_TAGS = frozenset(
    {
        ConceptTag.GREETINGS,
        ConceptTag.SMALLTALK,
        ConceptTag.DINING,
        ConceptTag.HOTEL,
        ConceptTag.TAXIS,
        ConceptTag.DIRECTIONS,
        ConceptTag.SIGHTSEEING,
        ConceptTag.BEACH_AND_VENDORS,
        ConceptTag.SHOPPING,
        ConceptTag.MONEY,
    }
)

# Tags valid for the MSA / Iraqi topical scheme.
TOPICAL_TAGS = frozenset(
    {
        ConceptTag.GREETINGS,
        ConceptTag.FOOD,
        ConceptTag.TRAVEL,
        ConceptTag.PEOPLE,
        ConceptTag.FAMILY,
        ConceptTag.EMOTIONS,
        ConceptTag.LEISURE,
        ConceptTag.DAILY_LIFE,
        ConceptTag.CULTURE,
        ConceptTag.WORK,
        ConceptTag.HEALTH,
    }
)

# Which tag scheme each register is allowed to draw from.
ALLOWED_TAGS_BY_REGISTER = {
    Register.EGYPTIAN: SITUATIONAL_TAGS,
    Register.MSA: TOPICAL_TAGS,
    Register.IRAQI: TOPICAL_TAGS,
}

# Full register names for prompts / display (read by ``Register.label``).
_REGISTER_LABELS = {
    Register.ENGLISH: "English",
    Register.EGYPTIAN: "Egyptian Arabic dialect",
    Register.MSA: "Modern Standard Arabic",
    Register.IRAQI: "Iraqi Arabic dialect",
}


@dataclass(frozen=True, slots=True)
class Utterance:
    """A spoken unit: text said in a given register (voice role)."""

    text: str
    register: Register

    def __str__(self) -> str:
        return self.text

    @property
    def key(self) -> str:
        """Content hash identifying this utterance (and its cached audio)."""
        return content_hash(f"{self.register}\n{self.text}")


@dataclass(frozen=True, slots=True)
class Chunk:
    """An English/Arabic phrase pair from chunks.csv.

    Validates concept_tag against the Arabic register's tag scheme, so a Chunk
    can't carry a tag outside its taxonomy (see ALLOWED_TAGS_BY_REGISTER).
    """

    id: str
    english: Utterance
    arabic: Utterance
    concept_tag: ConceptTag

    # The chunks.csv schema — the single source of truth for column order,
    # shared by from_row (read) and to_row (write).
    FIELDS: ClassVar[tuple[str, ...]] = (
        "id",
        "arabic",
        "english",
        "register",
        "concept_tag",
    )

    def __str__(self) -> str:
        return f"{self.id}: {self.english} / {self.arabic}"

    @property
    def utterances(self) -> tuple[Utterance, Utterance]:
        """This chunk's utterances, English then Arabic (the synthesis order)."""
        return (self.english, self.arabic)

    def to_row(self) -> list[str]:
        """Serialise to a chunks.csv row, in ``FIELDS`` order."""
        return [
            self.id,
            self.arabic.text,
            self.english.text,
            self.arabic.register,
            self.concept_tag,
        ]

    def __post_init__(self) -> None:
        allowed = ALLOWED_TAGS_BY_REGISTER.get(self.arabic.register)
        if allowed is not None and self.concept_tag not in allowed:
            raise ValueError(
                f"concept_tag {self.concept_tag.value!r} not allowed for "
                f"register {self.arabic.register.value!r}"
            )

    @classmethod
    def from_row(cls, row: list[str]) -> Chunk:
        """Build a Chunk from a raw CSV row (id, arabic, english, register, tag).

        Raises:
            ValueError: If the row has the wrong field count, or its register or
                concept_tag is outside the taxonomy.
        """
        try:
            cid, arabic, english, register, concept_tag = row
        except ValueError:
            raise ValueError(f"expected 5 fields, got {len(row)}: {row!r}") from None
        reg, tag = _parse_taxonomy(register, concept_tag)
        return cls(
            cid, Utterance(english, Register.ENGLISH), Utterance(arabic, reg), tag
        )


@dataclass(frozen=True, slots=True)
class VocabEntry:
    """A candidate vocab row on its way to becoming a Chunk.

    Produced by the ``extract-vocab`` skill's first-pass agent and consumed by
    ``kallim ingest``, which dedups, assigns an id, and validates it into a
    ``Chunk``. The ``register`` and ``concept_tag`` are taxonomy members.
    Validation of the tag against the register's scheme lives on ``Chunk`` —
    call ``to_chunk`` for a validated one.
    """

    arabic: str
    english: str
    register: Register
    concept_tag: ConceptTag

    # The vocab_pairs.csv schema — the single source of truth for column order,
    # shared by from_row (read) and to_row (write).
    FIELDS: ClassVar[tuple[str, ...]] = ("arabic", "english", "register", "concept_tag")

    def to_row(self) -> list[str]:
        """Serialise to a vocab_pairs.csv row, in ``FIELDS`` order."""
        return [self.arabic, self.english, self.register, self.concept_tag]

    def to_chunk(self, chunk_id: str) -> Chunk:
        """Build a validated Chunk from this entry.

        Args:
            chunk_id: The id to assign the new chunk.

        Returns:
            A Chunk carrying this entry's Arabic/English text and tag.

        Raises:
            ValueError: If ``concept_tag`` is outside ``register``'s scheme.
        """
        return Chunk(
            id=chunk_id,
            english=Utterance(self.english, Register.ENGLISH),
            arabic=Utterance(self.arabic, self.register),
            concept_tag=self.concept_tag,
        )

    @classmethod
    def from_row(cls, row: list[str]) -> VocabEntry:
        """Build a VocabEntry from a vocab_pairs.csv row (arabic, english, …).

        Mirrors ``Chunk.from_row``: a positional row in ``FIELDS`` order.

        Raises:
            ValueError: If the row has the wrong field count, or its register or
                concept_tag is off-taxonomy.
        """
        try:
            arabic, english, register, concept_tag = row
        except ValueError:
            raise ValueError(f"expected 4 fields, got {len(row)}: {row!r}") from None
        reg, tag = _parse_taxonomy(register, concept_tag)
        return cls(arabic, english, reg, tag)


def _parse_taxonomy(register: str, concept_tag: str) -> tuple[Register, ConceptTag]:
    """Parse a raw register + concept_tag pair into their enum members.

    Shared by ``Chunk.from_row`` and ``VocabEntry.from_row`` so the CSV
    taxonomy-decode lives in one place.

    Raises:
        ValueError: If ``register`` or ``concept_tag`` is outside its enum.
    """
    try:
        reg = Register(register)
    except ValueError:
        raise ValueError(f"unknown register {register!r}") from None
    try:
        tag = ConceptTag(concept_tag)
    except ValueError:
        raise ValueError(f"unknown concept_tag {concept_tag!r}") from None
    return reg, tag
