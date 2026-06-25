#!/usr/bin/env python3
"""Kallim domain model — utterances, chunks, and the concept_tag taxonomy.

Pure data types with no audio/pipeline dependencies (no pydub, no ElevenLabs).
A Chunk pairs an English and an Arabic Utterance; an Utterance is text + the
voice it's said in. It owns its content-addressed audio *identity* (``key``)
and the *act* of synthesising itself; the concrete engine is the injected
``Synthesiser`` port, and the resulting bytes live in the audio cache.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Protocol

from .utils import content_hash


class PlayableAudio(Protocol):
    """Playable audio data — e.g. a pydub AudioSegment.

    The model's type for actual sound: clips concatenate (``+``). The concrete
    type and all heavy ops live in the audio layer, so the model needs no audio
    library. Identity is the utterance's ``key``, not the audio's.
    """

    def __add__(self, other: PlayableAudio) -> PlayableAudio: ...


# The model's port for text-to-speech: an utterance -> playable audio. The
# concrete engine (ElevenLabs) lives in the audio layer and is *injected* onto
# Utterance.synthesiser, so the model declares the capability without importing
# any audio library. Just a Callable — the port has a single operation.
type Synthesiser = Callable[[Utterance], PlayableAudio]


class Register(StrEnum):
    """Voice role of an utterance (selects the TTS voice)."""

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


@dataclass(frozen=True, slots=True)
class Utterance:
    """A spoken unit: text said in a given register (voice role)."""

    text: str
    register: Register

    # The TTS engine, injected once by make_synthesiser (shared by all
    # utterances). Unset until then — synthesise() raises AttributeError.
    synthesiser: ClassVar[Synthesiser]

    def __str__(self) -> str:
        return self.text

    @property
    def key(self) -> str:
        """Content hash identifying this utterance (and its cached audio)."""
        return content_hash(f"{self.register}\n{self.text}")

    def synthesise(self) -> PlayableAudio:
        """Produce this utterance's audio via the injected synthesiser.

        Raises AttributeError if no synthesiser has been wired yet (call
        make_synthesiser first).
        """
        return Utterance.synthesiser(self)


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
    def from_row(cls, row: list[str]) -> "Chunk":
        """Build a Chunk from a raw CSV row (id, arabic, english, register, tag).

        Raises:
            ValueError: If the row has the wrong field count, or its register or
                concept_tag is outside the taxonomy.
        """
        try:
            cid, arabic, english, register, concept_tag = row
        except ValueError:
            raise ValueError(f"expected 5 fields, got {len(row)}: {row!r}") from None
        try:
            reg = Register(register)
        except ValueError:
            raise ValueError(f"unknown register {register!r}") from None
        try:
            tag = ConceptTag(concept_tag)
        except ValueError:
            raise ValueError(f"unknown concept_tag {concept_tag!r}") from None
        return cls(
            cid, Utterance(english, Register.ENGLISH), Utterance(arabic, reg), tag
        )
