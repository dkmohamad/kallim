"""Tests for what the voice says of a line: ``spoken_text`` and the cache key.

A note in brackets is either for the reader or a cue the listener needs. Get
that wrong one way and the voice reads out "lit." glosses and stray "n"s; get
it wrong the other way and "You (female) sent me" loses the cue that decides
which Arabic is right. The key hashes what is said, so these also pin that a
line with no notes keys exactly as it always did.
"""

import pytest

from scripts.model import Register, Utterance, spoken_text
from scripts.utils import content_hash


@pytest.mark.parametrize(
    ("written", "said"),
    [
        ("Many happy returns (lit. every year may you be well)", "Many happy returns"),
        ("An idea has come to mind (حالِيّاً = currently)", "An idea has come to mind"),
        ("empire (n.)", "empire"),
        ("relatives (n. pl.)", "relatives"),
        ("towards, regarding (prep.)", "towards, regarding"),
        ("Thin (adj., f.)", "Thin (f.)"),
    ],
)
def test_notes_for_the_reader_are_not_said(written: str, said: str) -> None:
    """Memory aids, Arabic, and grammar labels are for reading, not hearing."""
    assert spoken_text(written) == said


@pytest.mark.parametrize(
    "written",
    [
        "You (female) sent me",
        "Good morning (reply)",
        "They (two) met in/at …",
        "How are you? (to a man)",
        "It existed (masc.).",
    ],
)
def test_cues_that_change_the_answer_are_said(written: str) -> None:
    """Without the cue the English prompt no longer decides the Arabic form."""
    assert spoken_text(written) == written


@pytest.mark.parametrize(
    "written", ["He was ... years old...", "سَلامٌ لِـ …", "Hello, friend."]
)
def test_a_line_without_notes_is_said_exactly_as_written(written: str) -> None:
    """Spacing and ellipses in frames are left alone, character for character."""
    assert spoken_text(written) == written


def test_a_line_without_notes_keys_as_it_always_has() -> None:
    """The key moved to the spoken text; for plain text that changes nothing."""
    utt = Utterance("Hello, friend.", Register.ENGLISH)
    assert utt.key == content_hash(f"{Register.ENGLISH}\nHello, friend.")


def test_editing_an_unsaid_note_does_not_change_the_audio() -> None:
    """Two texts that sound the same share one clip, so a note edit costs nothing."""
    a = Utterance("empire (n.)", Register.ENGLISH)
    b = Utterance("empire", Register.ENGLISH)
    assert a.key == b.key
    assert a.text != b.text


def test_a_line_that_is_only_a_note_is_still_said() -> None:
    """Never hand the voice an empty string; say the text as written instead."""
    assert spoken_text("(n.)") == "(n.)"
