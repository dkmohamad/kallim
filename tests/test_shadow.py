"""Tests for the shadowing transcript and the ``kallim shadow`` render.

The transcript is both what you approve and what gets voiced, so a parse that
quietly drops or reorders a line produces a track that disagrees with the page
you are reading. These pin the layout, the refusals that guard a paid render,
and the cache split that keeps reading-material clips out of ``prune``'s reach.
"""

from pathlib import Path
from typing import cast

import pytest
from pydub import AudioSegment

from scripts.cache import AudioCache
from scripts.chunks import Chunks
from scripts.config import AUDIO_DIR, SHADOW_AUDIO_DIR
from scripts.model import (
    Chunk,
    ContentBlockedError,
    PlayableAudio,
    Register,
    Speech,
    Utterance,
)
from scripts.shadow import Source, render_pairs, report
from scripts.transcript import Pair, Transcript

TRANSCRIPT = """# Baghdad

## The founding

1. Al-Mansur chose its site with care
   اِخْتَارَ الْمَنْصُورُ مَوْقِعَهَا بِعِنَايَةٍ
2. on the banks of the Tigris.
   عَلَى ضِفَافِ دِجْلَةَ.

## The round city

3. The city was round.
   كَانَتِ الْمَدِينَةُ مُدَوَّرَةً.
"""


def _write(tmp_path: Path, text: str, name: str = "baghdad-transcript.md") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_parse_keeps_sections_and_order_english_first(tmp_path: Path) -> None:
    """Every pair comes back in page order, under its section, English first."""
    t = Transcript.parse(_write(tmp_path, TRANSCRIPT))
    assert t.title == "Baghdad"
    assert [s.title for s in t.sections] == ["The founding", "The round city"]
    pairs = list(t.pairs)
    assert pairs[0].english == Utterance(
        "Al-Mansur chose its site with care", Register.ENGLISH
    )
    assert pairs[0].arabic.register is Register.MSA
    assert pairs[2].arabic.text.startswith("كَانَتِ")


def test_render_numbers_on_across_sections_and_round_trips(tmp_path: Path) -> None:
    """The rendered page is the input layout again, so approve-then-publish agrees."""
    t = Transcript.parse(_write(tmp_path, TRANSCRIPT))
    rendered = t.render()
    assert "3. The city was round." in rendered
    assert Transcript.parse(_write(tmp_path, rendered, "again.md")) == t


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("1. Hello\n   مَرْحَبًا\n", "expected a '# Title' first"),
        ("# T\n\n1. Hello\n\n2. Bye\n   مَعَ السَّلَامَةِ\n", "no Arabic line"),
        ("# T\n\n1. مَرْحَبًا\n   Hello\n", "English first"),
        ("# T\n\n1. In 762\n   فِي ٧٦٢\n", "numbers in the Arabic as words"),
        ("# T\n\nA note for the teacher\n", "not part of the layout"),
        ("# T\n", "no numbered lines"),
    ],
)
def test_parse_refuses_what_should_not_be_voiced(
    tmp_path: Path, text: str, message: str
) -> None:
    """Each of these would be paid for and voiced wrongly, so each is an error."""
    with pytest.raises(ValueError, match=message):
        Transcript.parse(_write(tmp_path, text))


def test_reading_material_is_cached_out_of_prunes_reach(tmp_path: Path) -> None:
    """Its lines are in no bank, so they live apart from audio/."""
    source = Source.from_transcript(_write(tmp_path, TRANSCRIPT))
    assert source.name == "baghdad"
    assert source.cache.path("x").parent == SHADOW_AUDIO_DIR


def test_a_topic_uses_the_bank_and_its_cache(tmp_path: Path) -> None:
    """A topic's clips are bank clips, so they share audio/ and are usually cached."""
    bank = tmp_path / "bank.csv"
    rows = [
        Chunk(
            "a1",
            Utterance("Hello", Register.ENGLISH),
            Utterance("مَرْحَبًا", Register.MSA),
            "greetings",
        ).to_row(),
        Chunk(
            "a2",
            Utterance("Bye", Register.ENGLISH),
            Utterance("مَعَ السَّلَامَةِ", Register.MSA),
            "greetings",
        ).to_row(),
    ]
    bank.write_text(
        "id,arabic,english,register,topic,priority\n"
        + "\n".join(",".join(r) for r in rows)
        + "\n",
        encoding="utf-8",
    )
    source = Source.from_topic("greetings", bank)
    assert source.name == "greetings"
    assert [p.english.text for p in source.transcript.pairs] == ["Hello", "Bye"]
    assert source.cache.path("x").parent == AUDIO_DIR
    with pytest.raises(ValueError, match="not found"):
        Source.from_topic("dining", bank)


def test_generate_sections_use_the_same_layout() -> None:
    """A bank section's transcript is the shadow layout, not a format of its own."""
    chunk = Chunk(
        "a1",
        Utterance("Hello", Register.ENGLISH),
        Utterance("مَرْحَبًا", Register.MSA),
        "greetings",
    )
    section = Chunks([chunk]).sections()[0]
    assert section.transcript() == "# Greetings (Msa)\n\n1. Hello\n\tمَرْحَبًا\n"


def test_dry_run_counts_cached_clips_and_bills_a_repeat_once(tmp_path: Path) -> None:
    """The cost is the uncached characters, each repeated text counted once."""
    text = "# T\n\n1. Yes.\n   نَعَم.\n2. Yes.\n   نَعَم.\n3. No.\n   لَا.\n"
    cache = AudioCache(tmp_path / "cache")
    cache.path("x").parent.mkdir()
    no = Utterance("No.", Register.ENGLISH)
    cache[no.key] = cast(PlayableAudio, AudioSegment.silent(duration=10))
    source = Source("t", Transcript.parse(_write(tmp_path, text)), cache)
    summary = report(source, force=False)
    assert "Lines:    3" in summary
    # Clips due: "Yes." + "نَعَم." once each, plus "لَا." = 3; "No." is cached.
    assert (
        f"To synth: 3 clips, {len('Yes.') + len('نَعَم.') + len('لَا.')} characters"
        in summary
    )


def test_a_refused_pair_is_left_out_whole(tmp_path: Path) -> None:
    """Half a pair would play an English prompt with no Arabic after it."""
    pairs = list(Transcript.parse(_write(tmp_path, TRANSCRIPT)).pairs)
    refused = pairs[1].arabic.text

    def synth(speech: Speech) -> PlayableAudio:
        if speech.text == refused:
            raise ContentBlockedError(speech.text)
        return cast(PlayableAudio, AudioSegment.silent(duration=10))

    cache = AudioCache(tmp_path / "cache")
    cache.path("x").parent.mkdir()
    clips, blocked = render_pairs(pairs, synth, cache, force=False)
    assert blocked == [pairs[1]]
    assert len(clips) == 4  # two pairs, English and Arabic each


def test_pair_of_a_chunk_is_english_then_arabic() -> None:
    chunk = Chunk(
        "a1",
        Utterance("Hello", Register.ENGLISH),
        Utterance("مَرْحَبًا", Register.MSA),
        "greetings",
    )
    assert Pair.of(chunk).utterances == (chunk.english, chunk.arabic)
