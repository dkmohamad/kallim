"""Tests for the lesson-script parser and its audio identity.

The parse rules are the load-bearing half of ``kallim script``: a page that
parses wrongly produces a track with a turn missing or a speaker in the wrong
voice, and neither is visible until you listen to ten minutes of Arabic.
"""

import json
from pathlib import Path
from typing import cast

import pytest
from pydub import AudioSegment
from pydub.generators import Sine

from scripts.model import PlayableAudio, Register, Speaker, Utterance
from scripts.script import (
    Cue,
    Line,
    Marker,
    Script,
    clip_lengths,
    layout,
    stitch,
    to_vtt,
)

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


# The VTT format has a writer here and a reader in player/src/lib/lines.ts. This
# one file is what both are held to: to_vtt must reproduce it exactly, and the
# player's parser is tested against the same bytes (player/test/lines.test.ts).
VTT_FIXTURE = Path(__file__).parent / "fixtures" / "lesson.vtt"

# PAGE with a gloss carrying "-->", which must not end its cue.
FIXTURE_PAGE = PAGE.replace("*Hi, teacher.*", "*Hi, teacher --> hello, teacher.*")


def _fixture_cues(tmp_path: Path) -> list[Cue]:
    return layout(_script(tmp_path, FIXTURE_PAGE), [1000, 2000, 3000])


def test_layout_places_turn_and_section_gaps_before_each_turn(tmp_path: Path) -> None:
    """A section adds 1600 ms on top of the 700 ms turn gap; the opening one adds none.

    These are the timings the web player seeks and loops by. A cue that starts
    a gap early or late puts the highlight on the wrong line, or loops a line
    with the tail of the next one on it. With clips of 1000, 2000 and 3000 ms:
    line 2 starts 1000 + 700, and line 3 (after a section) 3700 + 700 + 1600.
    """
    cues = layout(_script(tmp_path), [1000, 2000, 3000])
    assert [(c.start_ms, c.end_ms) for c in cues] == [
        (0, 1000),
        (1700, 3700),
        (6000, 9000),
    ]
    assert [c.n for c in cues] == [1, 2, 3]
    assert [c.section for c in cues] == ["المُقَدِّمَة", "المُقَدِّمَة", "المَوْضُوع"]


def test_layout_stacks_two_section_breaks_in_a_row(tmp_path: Path) -> None:
    """Back-to-back headings each add their gap, as the original stitch did."""
    page = (
        "### **ديفيد:** نَعَم\n\n*Yes.*\n\n## أ\n\n## ب\n\n### **المعلِّمة:** لَا\n\n*No.*\n"
    )
    cues = layout(_script(tmp_path, page), [1000, 1000])
    assert cues[1].start_ms == 1000 + 700 + 1600 + 1600
    assert cues[1].section == "ب"


def test_layout_refuses_a_length_count_that_does_not_match_the_lines(
    tmp_path: Path,
) -> None:
    """One missing or extra clip would shift every later line against its audio."""
    with pytest.raises(ValueError, match="2 clip lengths for 3 spoken lines"):
        layout(_script(tmp_path), [1000, 2000])


def test_stitch_puts_each_clip_where_its_cue_says(tmp_path: Path) -> None:
    """Sound starts at every cue start, and the moment before it is silence.

    Real tones rather than silent clips, so a clip laid at the wrong place is
    audible in the check instead of vanishing into the gaps around it.
    """
    clips = [
        cast(PlayableAudio, Sine(440).to_audio_segment(duration=ms))
        for ms in (400, 500, 600)
    ]
    cues = layout(_script(tmp_path), clip_lengths(clips))
    track = cast(AudioSegment, stitch(cues, clips))
    assert len(track) == cues[-1].end_ms
    for cue in cues:
        assert track[cue.start_ms : cue.start_ms + 50].rms > 0
        if cue.start_ms:  # pydub sizes silence in whole samples, so allow 5 ms
            assert track[cue.start_ms - 50 : cue.start_ms - 5].rms == 0


def test_stitch_refuses_a_cue_that_starts_inside_the_previous_clip(
    tmp_path: Path,
) -> None:
    """Overlapping cues would place the clip late and put audio and VTT out of step."""
    clips = [cast(PlayableAudio, AudioSegment.silent(duration=1000))] * 2
    line = _script(tmp_path).lines[0]
    cues = [Cue(1, 0, 1000, line, None), Cue(2, 500, 1500, line, None)]
    with pytest.raises(ValueError, match="cue 2 starts before"):
        stitch(cues, clips)


def test_vtt_matches_the_fixture_the_player_is_tested_against(tmp_path: Path) -> None:
    """Writer and reader are held to one file, so a format change breaks a test."""
    assert to_vtt(_fixture_cues(tmp_path)) == VTT_FIXTURE.read_text(encoding="utf-8")


def test_vtt_payloads_are_json_with_arabic_intact(tmp_path: Path) -> None:
    """Each cue is ``HH:MM:SS.mmm`` timings over one line of JSON."""
    lines = to_vtt(
        [Cue(1, 3_723_004, 3_725_050, _script(tmp_path).lines[0], "المُقَدِّمَة")]
    ).split("\n")
    assert lines[0] == "WEBVTT"
    assert lines[2] == "01:02:03.004 --> 01:02:05.050"
    assert json.loads(lines[3])["ar"].startswith("مَرْحَبًا")


def test_vtt_escapes_arrows_so_a_gloss_cannot_end_its_cue(tmp_path: Path) -> None:
    """``-->`` inside a payload would be read as a new timing line."""
    vtt = to_vtt(_fixture_cues(tmp_path))
    payloads = vtt.split("\n")[3::3]
    assert not any("-->" in payload for payload in payloads)
    assert json.loads(payloads[1])["en"] == "Hi, teacher --> hello, teacher."


def test_vtt_numbers_lines_as_the_transcript_does(tmp_path: Path) -> None:
    """The player shows ``n`` beside a line, so it must match the .txt numbering."""
    script = _script(tmp_path)
    numbered = [
        ln.strip()
        for ln in script.transcript().splitlines()
        if ln.strip()[:1].isdigit()
    ]
    payloads = [
        json.loads(ln) for ln in to_vtt(layout(script, [1, 1, 1])).split("\n")[3::3]
    ]
    assert [f"{p['n']}. {p['label']}: {p['ar']}" for p in payloads] == numbered
