"""Tests for the lesson-script parser and its audio identity.

The parse rules are the load-bearing half of ``kallim script``: a page that
parses wrongly produces a track with a turn missing or a speaker in the wrong
voice, and neither is visible until you listen to ten minutes of Arabic.
"""

from pathlib import Path

import pytest

from scripts.model import Register, Speaker, Utterance
from scripts.script import Line, Marker, Script

PAGE = """# الدَّرْس

- **الوضع:** dialogue

## المُقَدِّمَة

### **المعلِّمة:** مَرْحَبًا يَا أُسْتَاذ

*Hello.*

### **ديفيد:** أَهْلًا يَا أُسْتَاذَة

*Hi, teacher.*

## المَوْضُوع

### **المعلِّمة:** [تعذّر الفهم]

*[unclear]*

### **ديفيد:** أُرِيدُ أَنْ أَتَحَدَّثَ عَنِ التَّارِيخ

*I want to talk about history.*
"""


def _script(tmp_path: Path, text: str = PAGE, name: str = "lesson") -> Script:
    path = tmp_path / f"{name}.md"
    path.write_text(text, encoding="utf-8")
    return Script.parse(path)


def test_parse_keeps_page_order_and_both_speakers(tmp_path: Path) -> None:
    """Blocks come back in page order, each under the speaker who said it.

    Page order is audio order — following the page against the track is the
    whole point — so a parser that grouped or reordered would break the feature
    while still producing a plausible-sounding MP3.
    """
    script = _script(tmp_path)
    assert [ln.speaker for ln in script.lines] == [
        Speaker.TEACHER,
        Speaker.DAVID,
        Speaker.DAVID,
    ]
    assert script.lines[0].arabic.startswith("مَرْحَبًا")
    assert script.name == "lesson"


def test_parse_skips_a_bracketed_turn(tmp_path: Path) -> None:
    """A ``[...]`` aside is written for the reader and never voiced.

    Brackets mark what the lesson left unclear or unresolved. Voicing one would
    put "unclear" into the middle of the dialogue as if the teacher had said it.
    """
    script = _script(tmp_path)
    assert len(script.lines) == 3
    assert not any("[" in ln.arabic for ln in script.lines)


def test_parse_counts_section_markers_without_voicing_them(tmp_path: Path) -> None:
    """``H2`` is a longer gap, not speech, so it is a block but not a line."""
    script = _script(tmp_path)
    assert [m.title for m in script.markers] == ["المُقَدِّمَة", "المَوْضُوع"]
    assert all(isinstance(m, Marker) for m in script.markers)


def test_parse_rejects_an_unknown_speaker(tmp_path: Path) -> None:
    """An unrecognised label stops the run instead of dropping the turn.

    The speaker prefix selects the voice, so a typo'd label has no voice to map
    to. Failing here is far cheaper than discovering a missing turn after
    paying for the synthesis.
    """
    page = "### **حسن:** مَرْحَبًا\n\n*Hello.*\n"
    with pytest.raises(ValueError, match="unknown speaker"):
        _script(tmp_path, page)


def test_parse_rejects_a_turn_with_no_gloss(tmp_path: Path) -> None:
    """A turn whose gloss is missing is a malformed page, not a silent skip.

    Without this the block is held pending, the next one overwrites it, and the
    turn vanishes from both the audio and the transcript with no warning.
    """
    page = "### **ديفيد:** مَرْحَبًا\n\n### **المعلِّمة:** أَهْلًا\n\n*Hi.*\n"
    with pytest.raises(ValueError, match="no English gloss"):
        _script(tmp_path, page)


def test_characters_count_arabic_only(tmp_path: Path) -> None:
    """The credit cost is the Arabic; glosses are never voiced, so cost nothing.

    Guards the spend gate: counting the English too would overstate every run
    and make the quota check reject affordable scripts.
    """
    script = _script(tmp_path)
    assert script.characters == sum(len(ln.arabic) for ln in script.lines)
    assert "I want to talk" not in "".join(ln.arabic for ln in script.lines)


def test_the_same_sentence_caches_separately_per_speaker() -> None:
    """Two speakers saying one sentence get two clips, not one shared clip.

    The cache is content-addressed on voice + text. If the voice were dropped
    from the key, whichever speaker was synthesised first would silently supply
    the other's audio, and the dialogue would be read by one person.
    """
    said = "نَعَم"
    assert (
        Line(Speaker.TEACHER, said, "Yes.").key != Line(Speaker.DAVID, said, "Yes.").key
    )


def test_a_line_and_an_utterance_are_distinct_speech_identities() -> None:
    """A script line never collides with a bank chunk over the same Arabic.

    Both satisfy ``Speech`` and share one cache implementation, so a line keyed
    like an MSA utterance would let ``prune`` and the script feature fight over
    the same file. The voice differs (speaker vs register), so the keys differ.
    """
    said = "نَعَم"
    assert Line(Speaker.DAVID, said, "Yes.").key != Utterance(said, Register.MSA).key


def test_transcript_numbers_only_spoken_turns(tmp_path: Path) -> None:
    """The transcript is 1:1 with the audio, so markers break but don't number.

    It is what gets read while the track plays; a number that doesn't match the
    turn you are hearing makes it useless for following along.
    """
    lines = _script(tmp_path).transcript().splitlines()
    numbered = [ln for ln in lines if ln.strip().startswith(("1.", "2.", "3."))]
    assert len(numbered) == 3
    assert "— المُقَدِّمَة —" in lines
