"""Shared fixtures: a small bank and an Anki collection whose cards sit in it.

Both ``anki_progress`` and the ``shadow`` Anki source read the same collection,
so the fixture lives once here rather than in each test module.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts.anki_progress import CardQueue, CardType
from scripts.chunks import Chunks
from scripts.generate_anki import MODEL_ID, note_guid
from scripts.model import Chunk, Register, Utterance

# A card's (type, queue, ivl).
_NEW = (CardType.NEW, CardQueue.NEW, 0)
_LEARNING = (CardType.LEARNING, CardQueue.LEARNING, 0)
_RELEARNING = (CardType.RELEARNING, CardQueue.LEARNING, 0)
_YOUNG = (CardType.REVIEW, CardQueue.REVIEW, 10)
_MATURE = (CardType.REVIEW, CardQueue.REVIEW, 60)
_SUSPENDED = (CardType.LEARNING, CardQueue.SUSPENDED, 0)

# Chunk id -> (topic, the note's cards). The id names the note's state.
_ANKI_CARDS = {
    "new": ("greetings", [_NEW, _NEW]),
    "learning": ("greetings", [_LEARNING, _NEW]),
    "relearning": ("food", [_MATURE, _RELEARNING]),
    "young": ("greetings", [_YOUNG, _MATURE]),
    "mature": ("food", [_MATURE, _MATURE]),
    "suspended": ("food", [_SUSPENDED, _NEW]),
}


@pytest.fixture
def young_ivl() -> int:
    """The interval of the one young review card, for boundary tests."""
    return _YOUNG[2]


@pytest.fixture
def anki_bank() -> Chunks:
    """One MSA chunk per note in the collection, its English the chunk id."""
    return Chunks(
        Chunk(cid, Utterance(cid, Register.ENGLISH), Utterance("نَعَم", Register.MSA), t)
        for cid, (t, _) in _ANKI_CARDS.items()
    )


@pytest.fixture
def make_anki_collection(tmp_path: Path, anki_bank: Chunks) -> Callable[[int], Path]:
    """Build a collection of the bank's notes under the given note-type id.

    Only the two tables the query reads, with only the columns it reads.
    """

    def build(mid: int) -> Path:
        path = tmp_path / "collection.anki2"
        db = sqlite3.connect(path)
        db.execute("CREATE TABLE notes (id INTEGER, guid TEXT, mid INTEGER)")
        db.execute(
            "CREATE TABLE cards (id INTEGER, nid INTEGER,"
            " type INTEGER, queue INTEGER, ivl INTEGER)"
        )
        for nid, chunk in enumerate(anki_bank):
            db.execute(
                "INSERT INTO notes VALUES (?, ?, ?)", (nid, note_guid(chunk), mid)
            )
            for card in _ANKI_CARDS[chunk.id][1]:
                db.execute("INSERT INTO cards VALUES (NULL, ?, ?, ?, ?)", (nid, *card))
        db.commit()
        db.close()
        return path

    return build


@pytest.fixture
def anki_collection(make_anki_collection: Callable[[int], Path]) -> Path:
    """The collection with the bank's notes under the Kallim note type."""
    return make_anki_collection(MODEL_ID)
