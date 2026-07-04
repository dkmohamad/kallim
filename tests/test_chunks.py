"""Tests for the Chunks collection's identity lookups (dedup + audio keys)."""

from pathlib import Path

import pytest

from scripts.chunks import Chunks
from scripts.model import Chunk

# One phrase in two spellings (vocalized + bare) sharing an English gloss.
_ROWS = [
    ["c1", "عايِز مَنْشَفَة", "I want a towel", "egyptian", "hotel"],
    ["c2", "عايز منشفة", "I want a towel", "egyptian", "hotel"],
]


def _chunks() -> Chunks:
    return Chunks(Chunk.from_row(row) for row in _ROWS)


def test_arabic_keys_fold_vocalized_and_bare_to_one_identity() -> None:
    """Diacritics variants of one phrase collapse to a single dedup key.

    The ingest dedup compares candidates against this set, and chunks.csv mixes
    vocalized and bare Arabic, so both spellings of "I want a towel" must fold to
    one identity — otherwise a bare re-entry of a vocalized phrase looks new.
    Guards that arabic_keys runs through normalize_arabic, not raw text.
    """
    chunks = _chunks()
    assert len(chunks) == 2
    assert len(chunks.arabic_keys()) == 1


def test_audio_keys_are_content_keys_deduped_across_chunks() -> None:
    """audio_keys is the set of per-utterance content keys, shared text merged.

    The two chunks share an identical English gloss (one content key) but differ
    in Arabic text (vocalized vs bare hash to two keys), so the audio-key set has
    three entries, not four. Guards prune's orphan set: a repeated utterance
    contributes one cache file, and audio_keys must reflect that.
    """
    assert len(_chunks().audio_keys()) == 3


def test_load_raises_when_the_csv_is_absent(tmp_path: Path) -> None:
    """Chunks.load propagates FileNotFoundError rather than yielding empty.

    prune builds its live-key set from Chunks.load; if a missing chunks.csv
    silently became an empty collection, every cache file would look orphaned and
    `prune --apply` could wipe the whole cache. The loader must fail loud.
    """
    with pytest.raises(FileNotFoundError):
        Chunks.load(tmp_path / "nope.csv")
