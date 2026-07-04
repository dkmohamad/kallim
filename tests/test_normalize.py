"""Tests for the diacritics-insensitive Arabic dedup key."""

from scripts.utils import normalize_arabic


def test_normalize_arabic_should_match_vocalized_and_bare() -> None:
    """A vocalized phrase and its bare spelling normalize to the same key.

    The ingest dedup compares extracted candidates against chunks.csv, whose
    Arabic mixes vocalized and unvocalized rows, so both spellings of one
    phrase must fold to a single key. Arrange two spellings of "I want a
    towel", act by normalizing, assert they're equal — and non-empty, guarding
    the regression where a too-broad tashkīl class deleted the letters too and
    collapsed everything to "" (so every phrase looked like a duplicate).
    """
    vocalized = "عايِز مَنْشَفَة"
    bare = "عايز منشفة"

    assert normalize_arabic(vocalized) == normalize_arabic(bare)
    assert normalize_arabic(vocalized), "normalization must not collapse letters"


def test_normalize_arabic_should_fold_alef_and_ta_marbuta() -> None:
    """Alef-hamza and ta-marbuta variants fold to their bare forms.

    Guards the fold table: أ/إ/آ → ا and ة → ه, so spelling variants of the
    same word (common across hand-typed chunks) don't survive as false
    distinct dedup keys.
    """
    assert normalize_arabic("أكل") == normalize_arabic("اكل")
    assert normalize_arabic("مدرسة") == normalize_arabic("مدرسه")
