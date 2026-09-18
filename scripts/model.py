"""Kallim domain model — utterances, chunks, and the topic registry.

Pure data types with no audio/pipeline dependencies (no pydub, no ElevenLabs).
A Chunk pairs an English and an Arabic Utterance; an Utterance is text + the
voice it's said in, and owns its content-addressed audio *identity* (``key``).
Synthesis itself is done by the ``Synthesiser`` port (a callable), passed in by
the caller; the resulting bytes live in the audio cache. A ``VocabEntry`` is a
candidate row on its way to becoming a ``Chunk`` (see ``ingest``).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Protocol

from .utils import content_hash

__all__ = [
    "Chunk",
    "ContentBlockedError",
    "PlayableAudio",
    "Priority",
    "Register",
    "Synthesiser",
    "TOPICS",
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


class ContentBlockedError(RuntimeError):
    """The TTS provider refused an utterance's text on content-policy grounds.

    Raised by a Synthesiser in place of the provider-specific error so callers
    can skip that utterance's audio — the block is deterministic per text, so
    retrying won't clear it — while every other failure still stops the run.
    """


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


# a registry rather than an enum: adding a topic costs one line here instead of
# an enum member plus a scheme entry, which is
# the friction that makes people file things under a near-enough label. It is
# also what ``kallim tags`` reads to describe a topic to the extraction agent,
# so the entry has to exist regardless.
TOPICS: dict[str, str] = {
    "greetings": "hello, goodbye, pleasantries",
    "smalltalk": "casual chit-chat — first-time-here, the weather, traffic",
    "dining": "cafe/restaurant: ordering, menus, the bill",
    "hotel": "check-in, rooms, hotel amenities",
    "taxis": "hailing and agreeing rides, fares",
    "directions": "asking the way, finding places, 'walk from here'",
    "sightseeing": "landmarks, mosques, tours, excursions, boat trips",
    "beach_and_vendors": "the beach, sellers and hawkers",
    "shopping": "shops, markets, haggling, 'too expensive', 'best price?'",
    "money": "prices, change, paying amounts",
    "food": "diet, cooking, ingredients, meals, cafes and drinks",
    "travel": "transport, journeys, directions, sightseeing",
    "people": "society, community, and relationships beyond one's own family",
    "family": (
        "kin and relatives — parents, grandparents, cousins, marriage, "
        "childhood at home"
    ),
    "emotions": "feelings, moods, dreams, personality traits",
    "leisure": "nature, parks, weather, hobbies, free time",
    "daily_life": "everyday routine — home, technology, phones, errands",
    "culture": "religion, traditions, proverbs, the arts",
    "language": (
        "the language-learning journey — mother tongue, translation, foreign "
        "languages, self-discovery through language"
    ),
    "work": "business, career, professional life, pressure",
    "health": "the health system, the body, exercise, medicine",
    "history": "the Arab and Islamic past — events, dynasties, rulers, battles",
}

# Registered, not unchecked: an unregistered value is far more often a typo
# than a new dossier, and an unnoticed typo silently splits a section, drops
# rows from --section, and opens a second Anki namespace.
# One separator, underscore — daily-life and daily_life read identically.
_TOPIC_RE = re.compile(r"^[a-z0-9][a-z0-9_]*$")


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

    ``topic`` says what it is about. Which topic is under current study is a
    property of the syllabus, not of a chunk, so it is a question for
    ``--section`` rather than a column here.
    """

    id: str
    english: Utterance
    arabic: Utterance
    topic: str
    priority: Priority = Priority.NORMAL

    # The chunks.csv schema — the single source of truth for column order,
    # shared by from_row (read) and to_row (write).
    FIELDS: ClassVar[tuple[str, ...]] = (
        "id",
        "arabic",
        "english",
        "register",
        "topic",
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
            self.topic,
            self.priority,
        ]

    def __post_init__(self) -> None:
        _validate_topic(self.topic)
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
                tag, topic or priority is invalid.
        """
        try:
            cid, arabic, english, register, topic, priority = row
        except ValueError:
            raise ValueError(f"expected 6 fields, got {len(row)}: {row!r}") from None
        return cls(
            cid,
            Utterance(english, Register.ENGLISH),
            Utterance(arabic, _parse_register(register)),
            topic,
            _parse_priority(priority),
        )


@dataclass(frozen=True, slots=True)
class VocabEntry:
    """A candidate vocab row on its way to becoming a Chunk.

    Produced by the ``extract-vocab`` skill's first-pass agent and consumed by
    ``kallim ingest``, which dedups, assigns an id, and validates it into a
    ``Chunk``. ``register`` is an enum member; ``topic`` is a registered slug,
    validated here on construction just as it is on ``Chunk`` so a candidate
    can't carry a shape a chunk would reject.
    """

    arabic: str
    english: str
    register: Register
    topic: str
    priority: Priority = Priority.NORMAL

    def __post_init__(self) -> None:
        _validate_topic(self.topic)

    # The vocab_pairs.csv schema — the single source of truth for column order,
    # shared by from_row (read) and to_row (write). ``priority`` is optional on
    # read (an extraction agent may omit the column) but always written.
    FIELDS: ClassVar[tuple[str, ...]] = (
        "arabic",
        "english",
        "register",
        "topic",
        "priority",
    )

    def to_row(self) -> list[str]:
        """Serialise to a vocab_pairs.csv row, in ``FIELDS`` order."""
        return [
            self.arabic,
            self.english,
            self.register,
            self.topic,
            self.priority,
        ]

    def to_chunk(self, chunk_id: str) -> Chunk:
        """Build a validated Chunk from this entry.

        Args:
            chunk_id: The id to assign the new chunk.

        Returns:
            A Chunk carrying this entry's Arabic/English text and tag.

        Raises:
            ValueError: If the row is invalid.
        """
        return Chunk(
            id=chunk_id,
            english=Utterance(self.english, Register.ENGLISH),
            arabic=Utterance(self.arabic, self.register),
            topic=self.topic,
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
                tag or priority is invalid.
        """
        if len(row) == 4:
            arabic, english, register, topic = row
            priority = Priority.NORMAL
        elif len(row) == 5:
            arabic, english, register, topic, raw_priority = row
            # A blank cell means "unclassified", same as an omitted column.
            priority = (
                _parse_priority(raw_priority) if raw_priority else Priority.NORMAL
            )
        else:
            raise ValueError(f"expected 4 or 5 fields, got {len(row)}: {row!r}")
        return cls(arabic, english, _parse_register(register), topic, priority)


def _validate_topic(topic: str) -> None:
    """Check a topic is a registered slug.

    Shared by ``Chunk`` and ``VocabEntry`` so one policy governs both.

    Raises:
        ValueError: If the topic isn't a slug, or isn't registered in TOPICS.
    """
    if not _TOPIC_RE.match(topic):
        raise ValueError(
            f"topic {topic!r} is not a slug (lowercase letters, digits and _)"
        )
    if topic not in TOPICS:
        raise ValueError(
            f"unknown topic {topic!r} — add it to TOPICS with a description if "
            "it is a real dossier, or fix the typo"
        )


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


def _parse_register(register: str) -> Register:
    """Parse a raw register into its enum member.

    Shared by ``Chunk.from_row`` and ``VocabEntry.from_row`` so the CSV
    enum-decode lives in one place.

    Raises:
        ValueError: If ``register`` is outside the enum.
    """
    try:
        return Register(register)
    except ValueError:
        raise ValueError(f"unknown register {register!r}") from None


# Full register names for prompts / display (read by ``Register.label``).
_REGISTER_LABELS = {
    Register.ENGLISH: "English",
    Register.EGYPTIAN: "Egyptian Arabic dialect",
    Register.MSA: "Modern Standard Arabic",
    Register.IRAQI: "Iraqi Arabic dialect",
}
