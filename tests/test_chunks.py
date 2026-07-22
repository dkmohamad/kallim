"""Tests for the Chunks collection's identity lookups (dedup + audio keys)."""

from pathlib import Path

import pytest

from scripts.chunks import Chunks
from scripts.model import Chunk, ConceptTag

# One phrase in two spellings (vocalized + bare) sharing an English gloss.
_ROWS = [
    ["c1", "عايِز مَنْشَفَة", "I want a towel", "egyptian", "hotel", "normal"],
    ["c2", "عايز منشفة", "I want a towel", "egyptian", "hotel", "normal"],
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


def test_chunk_should_reject_slash_alternate_arabic() -> None:
    """A slash-double like عايز/عايزة is not one drillable surface form.

    Guards the one-surface-form rule: Chunk construction (and therefore lint
    and ingest) must fail loudly on Arabic text carrying '/', instead of
    letting a two-variant row through to TTS and the deck.
    """
    row = ["x1", "عايز/عايزة قهوة", "I want coffee", "egyptian", "dining", "normal"]
    with pytest.raises(ValueError, match="slash-alternate"):
        Chunk.from_row(row)


def test_section_narrows_by_tag_and_sections_group_by_tag_and_register() -> None:
    """`section` filters to one concept_tag; `sections` groups tag+register.

    Guards the collection operations moved onto Chunks in the restructure: a
    concept_tag not present raises, a present one narrows, and grouping yields
    one Section per (tag, register) with the label the real run and dry run share.
    """
    rows = [
        ["s1", "السلام عليكم", "Hello", "egyptian", "greetings", "normal"],
        ["s2", "صباح الخير", "Good morning", "egyptian", "greetings", "high"],
        ["s3", "أنا بخير", "I am fine", "msa", "greetings", "normal"],
    ]
    chunks = Chunks(Chunk.from_row(row) for row in rows)

    assert len(chunks.section(ConceptTag.GREETINGS)) == 3
    assert chunks.section(None) is chunks

    sections = chunks.sections()
    labels = [s.label for s in sections]
    assert labels == ["greetings (egyptian)", "greetings (msa)"]
    assert sections[0].slug(3) == "03_greetings_egyptian"


def test_load_raises_when_the_csv_is_absent(tmp_path: Path) -> None:
    """Chunks.load propagates FileNotFoundError rather than yielding empty.

    prune builds its live-key set from Chunks.load; if a missing chunks.csv
    silently became an empty collection, every cache file would look orphaned and
    `prune --apply` could wipe the whole cache. The loader must fail loud.
    """
    with pytest.raises(FileNotFoundError):
        Chunks.load(tmp_path / "nope.csv")
