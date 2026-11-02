"""Tests for reading Anki progress back onto the bank.

The selection decides what the "learning" track drills, so a card in the wrong
state slipping in (a new card never seen, a suspended one, a settled one) or a
learning card slipping out makes the shadowing disagree with the deck. The bank
and collection fixtures are in ``conftest.py``.
"""

import re
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts.anki_progress import learning
from scripts.chunks import Chunks


def test_learning_should_select_learning_relearning_and_young_reviews(
    anki_bank: Chunks, anki_collection: Path
) -> None:
    """New, mature-only and suspended notes are not being learned; bank order holds."""
    chunks = learning(anki_bank, anki_collection, max_ivl=21)
    assert [c.id for c in chunks] == ["learning", "relearning", "young"]


def test_learning_should_count_a_mature_card_under_a_raised_max_ivl(
    anki_bank: Chunks, anki_collection: Path
) -> None:
    """``max_ivl`` is the only line between young and settled, so it must move it."""
    chunks = learning(anki_bank, anki_collection, max_ivl=90)
    assert [c.id for c in chunks] == ["learning", "relearning", "young", "mature"]


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (-1, ["learning", "relearning"]),
        (0, ["learning", "relearning", "young"]),
    ],
)
def test_learning_should_include_a_review_whose_ivl_equals_max_ivl(
    anki_bank: Chunks,
    anki_collection: Path,
    young_ivl: int,
    offset: int,
    expected: list[str],
) -> None:
    """The bound is inclusive: a card due on the last young day is still young."""
    chunks = learning(anki_bank, anki_collection, max_ivl=young_ivl + offset)
    assert [c.id for c in chunks] == expected


def test_learning_should_ignore_other_note_types(
    anki_bank: Chunks, make_anki_collection: Callable[[int], Path]
) -> None:
    """Only the Kallim model's notes count, even with a matching GUID."""
    assert list(learning(anki_bank, make_anki_collection(1), max_ivl=21)) == []


def test_learning_should_name_a_missing_collection(
    anki_bank: Chunks, tmp_path: Path
) -> None:
    """The default path may not be this machine's, so the error says where it looked."""
    missing = tmp_path / "nope.anki2"
    with pytest.raises(
        FileNotFoundError, match=re.escape(f"no Anki collection at {missing}")
    ):
        learning(anki_bank, missing, max_ivl=21)
