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
from typing import ClassVar, NamedTuple, Protocol

from .utils import content_hash

__all__ = [
    "ALLOWED_TAGS_BY_REGISTER",
    "Chunk",
    "ConceptTag",
    "PlayableAudio",
    "Priority",
    "Register",
    "Scheme",
    "SITUATIONAL_TAGS",
    "Synthesiser",
    "TOPICAL_TAGS",
    "Utterance",
    "VocabEntry",
    "tags_for",
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


class Priority(StrEnum):
    """How broadly useful a chunk is in live conversation.

    ``HIGH`` marks chunks used constantly — high-utility, generally applicable
    across topics — so drills and decks can foreground them. Everything else is
    ``NORMAL``.
    """

    NORMAL = "normal"
    HIGH = "high"


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
    LANGUAGE = "language"
    WORK = "work"
    HEALTH = "health"

    @property
    def description(self) -> str:
        """One-line 'covers…' gloss (for prompts, display, and ``kallim tags``)."""
        return _TAXONOMY[self].description


class Scheme(StrEnum):
    """The two co-existing concept_tag schemes (see ``ConceptTag``)."""

    SITUATIONAL = "situational"  # Egyptian travel-phrasebook situations
    TOPICAL = "topical"  # MSA / Iraqi conversation topics


class _TagInfo(NamedTuple):
    """What the taxonomy records per tag: its scheme(s) and a 'covers' gloss."""

    schemes: frozenset[Scheme]
    description: str


# Scheme-membership shorthands, kept terse so the taxonomy table stays scannable
# (``_SIT``/``_TOP`` = the tag lives in that scheme only; ``_BOTH`` = shared).
_BOTH = frozenset({Scheme.SITUATIONAL, Scheme.TOPICAL})
_SIT = frozenset({Scheme.SITUATIONAL})
_TOP = frozenset({Scheme.TOPICAL})

# The concept_tag taxonomy — the single source of truth. Each tag maps to the
# scheme(s) it belongs to and a one-line description of what it covers.
# ``kallim tags`` renders this for the extract-vocab skill, and the frozensets
# and ``ConceptTag.description`` below all derive from it, so the taxonomy can
# never drift out of sync with a hand-copied table.
_TAXONOMY: dict[ConceptTag, _TagInfo] = {
    ConceptTag.GREETINGS: _TagInfo(_BOTH, "hello, goodbye, pleasantries"),
    ConceptTag.SMALLTALK: _TagInfo(
        _SIT, "casual chit-chat — first-time-here, the weather, traffic"
    ),
    ConceptTag.DINING: _TagInfo(_SIT, "cafe/restaurant: ordering, menus, the bill"),
    ConceptTag.HOTEL: _TagInfo(_SIT, "check-in, rooms, hotel amenities"),
    ConceptTag.TAXIS: _TagInfo(_SIT, "hailing and agreeing rides, fares"),
    ConceptTag.DIRECTIONS: _TagInfo(
        _SIT, "asking the way, finding places, 'walk from here'"
    ),
    ConceptTag.SIGHTSEEING: _TagInfo(
        _SIT, "landmarks, mosques, tours, excursions, boat trips"
    ),
    ConceptTag.BEACH_AND_VENDORS: _TagInfo(_SIT, "the beach, sellers and hawkers"),
    ConceptTag.SHOPPING: _TagInfo(
        _SIT, "shops, markets, haggling, 'too expensive', 'best price?'"
    ),
    ConceptTag.MONEY: _TagInfo(_SIT, "prices, change, paying amounts"),
    ConceptTag.FOOD: _TagInfo(
        _TOP, "diet, cooking, ingredients, meals, cafes and drinks"
    ),
    ConceptTag.TRAVEL: _TagInfo(_TOP, "transport, journeys, directions, sightseeing"),
    ConceptTag.PEOPLE: _TagInfo(
        _TOP, "society, community, and relationships beyond one's own family"
    ),
    ConceptTag.FAMILY: _TagInfo(
        _TOP,
        "kin and relatives — parents, grandparents, cousins, marriage, childhood at home",
    ),
    ConceptTag.EMOTIONS: _TagInfo(_TOP, "feelings, moods, dreams, personality traits"),
    ConceptTag.LEISURE: _TagInfo(_TOP, "nature, parks, weather, hobbies, free time"),
    ConceptTag.DAILY_LIFE: _TagInfo(
        _TOP, "everyday routine — home, technology, phones, errands"
    ),
    ConceptTag.CULTURE: _TagInfo(
        _TOP, "religion, traditions, proverbs, history, the arts"
    ),
    ConceptTag.LANGUAGE: _TagInfo(
        _TOP,
        "the language-learning journey — mother tongue, translation, foreign "
        "languages, self-discovery through language",
    ),
    ConceptTag.WORK: _TagInfo(_TOP, "business, career, professional life, pressure"),
    ConceptTag.HEALTH: _TagInfo(
        _TOP, "the health system, the body, exercise, medicine"
    ),
}

# Fail early on drift: every ConceptTag needs exactly one _TAXONOMY entry (with
# its scheme membership and description), so a new tag can't be half-added. An
# explicit raise (not ``assert``) so the guard survives ``python -O``.
if set(_TAXONOMY) != set(ConceptTag):
    raise RuntimeError(
        f"_TAXONOMY out of sync with ConceptTag: {set(ConceptTag) ^ set(_TAXONOMY)}"
    )


def tags_for(scheme: Scheme) -> frozenset[ConceptTag]:
    """The set of tags valid in ``scheme``, derived from the taxonomy above."""
    return frozenset(tag for tag, info in _TAXONOMY.items() if scheme in info.schemes)


# Tags valid for each scheme, derived from the taxonomy above.
SITUATIONAL_TAGS = tags_for(Scheme.SITUATIONAL)
TOPICAL_TAGS = tags_for(Scheme.TOPICAL)

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
    priority: Priority = Priority.NORMAL

    # The chunks.csv schema — the single source of truth for column order,
    # shared by from_row (read) and to_row (write).
    FIELDS: ClassVar[tuple[str, ...]] = (
        "id",
        "arabic",
        "english",
        "register",
        "concept_tag",
        "priority",
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
            self.priority,
        ]

    def __post_init__(self) -> None:
        allowed = ALLOWED_TAGS_BY_REGISTER.get(self.arabic.register)
        if allowed is not None and self.concept_tag not in allowed:
            raise ValueError(
                f"concept_tag {self.concept_tag.value!r} not allowed for "
                f"register {self.arabic.register.value!r}"
            )
        # One surface form per chunk: slash-alternates (عايز/عايزة) aren't a
        # drillable unit and read badly in TTS — store each variant as its own
        # chunk instead.
        if "/" in self.arabic.text:
            raise ValueError(
                f"arabic carries a slash-alternate {self.arabic.text!r}; "
                "store one surface form per chunk"
            )

    @classmethod
    def from_row(cls, row: list[str]) -> Chunk:
        """Build a Chunk from a raw CSV row in ``FIELDS`` order.

        Raises:
            ValueError: If the row has the wrong field count, or its register,
                concept_tag, or priority is outside the taxonomy.
        """
        try:
            cid, arabic, english, register, concept_tag, priority = row
        except ValueError:
            raise ValueError(f"expected 6 fields, got {len(row)}: {row!r}") from None
        reg, tag = _parse_taxonomy(register, concept_tag)
        return cls(
            cid,
            Utterance(english, Register.ENGLISH),
            Utterance(arabic, reg),
            tag,
            _parse_priority(priority),
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
    priority: Priority = Priority.NORMAL

    # The vocab_pairs.csv schema — the single source of truth for column order,
    # shared by from_row (read) and to_row (write). ``priority`` is optional on
    # read (an extraction agent may omit the column) but always written.
    FIELDS: ClassVar[tuple[str, ...]] = (
        "arabic",
        "english",
        "register",
        "concept_tag",
        "priority",
    )

    def to_row(self) -> list[str]:
        """Serialise to a vocab_pairs.csv row, in ``FIELDS`` order."""
        return [
            self.arabic,
            self.english,
            self.register,
            self.concept_tag,
            self.priority,
        ]

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
            priority=self.priority,
        )

    @classmethod
    def from_row(cls, row: list[str]) -> VocabEntry:
        """Build a VocabEntry from a vocab_pairs.csv row (arabic, english, …).

        Mirrors ``Chunk.from_row``: a positional row in ``FIELDS`` order, except
        that ``priority`` may be omitted or blank (defaults to normal) so
        extraction agents that don't classify priority still produce valid
        candidates.

        Raises:
            ValueError: If the row has the wrong field count, or its register,
                concept_tag, or priority is off-taxonomy.
        """
        if len(row) == 4:
            arabic, english, register, concept_tag = row
            priority = Priority.NORMAL
        elif len(row) == 5:
            arabic, english, register, concept_tag, raw_priority = row
            # A blank cell means "unclassified", same as an omitted column.
            priority = (
                _parse_priority(raw_priority) if raw_priority else Priority.NORMAL
            )
        else:
            raise ValueError(f"expected 4 or 5 fields, got {len(row)}: {row!r}")
        reg, tag = _parse_taxonomy(register, concept_tag)
        return cls(arabic, english, reg, tag, priority)


def _parse_priority(priority: str) -> Priority:
    """Parse a raw priority value into its enum member.

    Shared by ``Chunk.from_row`` and ``VocabEntry.from_row`` so the CSV
    priority-decode lives in one place.

    Raises:
        ValueError: If ``priority`` is outside the enum.
    """
    try:
        return Priority(priority)
    except ValueError:
        raise ValueError(f"unknown priority {priority!r}") from None


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


# Full register names for prompts / display (read by ``Register.label``).
_REGISTER_LABELS = {
    Register.ENGLISH: "English",
    Register.EGYPTIAN: "Egyptian Arabic dialect",
    Register.MSA: "Modern Standard Arabic",
    Register.IRAQI: "Iraqi Arabic dialect",
}
