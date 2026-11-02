"""Which bank chunks are being learned in Anki — read from the local collection.

The Kallim deck's note GUIDs come from ``generate_anki.note_guid``, so a note in
the collection maps straight back to its row in the bank. This reads the desktop
collection, which is only as current as its last AnkiWeb sync: open desktop Anki
first so it pulls the phone's reviews.

Safe while Anki is open, and never writes to it. Anki holds the collection
under an exclusive lock and keeps a fresh sync in its write-ahead log rather
than the main file, so this reads a copy of both: opening the original
``immutable`` would skip the log and miss the sync.
"""

from __future__ import annotations

import contextlib
import shutil
import sqlite3
import tempfile
from enum import IntEnum
from pathlib import Path

from .chunks import Chunks
from .generate_anki import MODEL_ID, note_guid

__all__ = ["CardQueue", "CardType", "learning"]


# The codes Anki stores in ``cards.type`` and ``cards.queue``, from its database
# schema (the CardType and CardQueue enums in Anki's rslib/src/card/mod.rs).
class CardType(IntEnum):
    """A card's place in the learning cycle (``cards.type``)."""

    NEW = 0
    LEARNING = 1
    REVIEW = 2
    RELEARNING = 3


class CardQueue(IntEnum):
    """Which queue a card is scheduled in (``cards.queue``); only those read here."""

    SUSPENDED = -1
    NEW = 0
    LEARNING = 1
    REVIEW = 2


# A suspended card is one set aside, so it is left out whatever its type.
_LEARNING = """
    SELECT DISTINCT n.guid FROM cards c JOIN notes n ON n.id = c.nid
    WHERE n.mid = ? AND c.queue != ?
      AND (c.type IN (?, ?) OR (c.type = ? AND c.ivl <= ?))
"""


def learning(bank: Chunks, collection: Path, max_ivl: int) -> Chunks:
    """The bank's chunks with a card in learning or a young review, in bank order.

    A review card is young while its interval is at most ``max_ivl`` days.

    Raises:
        FileNotFoundError: If ``collection`` doesn't exist.
    """
    params = (
        MODEL_ID,
        CardQueue.SUSPENDED,
        CardType.LEARNING,
        CardType.RELEARNING,
        CardType.REVIEW,
        max_ivl,
    )
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / collection.name
        try:
            shutil.copy2(collection, copy)
        except FileNotFoundError:
            raise FileNotFoundError(f"no Anki collection at {collection}") from None
        wal = collection.with_name(f"{collection.name}-wal")
        with contextlib.suppress(FileNotFoundError):
            shutil.copy2(wal, copy.with_name(wal.name))
        db = sqlite3.connect(copy)
        try:
            guids = {row[0] for row in db.execute(_LEARNING, params)}
        finally:
            db.close()
    return Chunks(c for c in bank if note_guid(c) in guids)
