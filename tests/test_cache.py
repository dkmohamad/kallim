"""Tests for ensure_cached's content-policy skip (the blocked-utterance path)."""

from pathlib import Path
from typing import cast

from scripts.cache import AudioCache, ensure_cached
from scripts.model import Chunk, ContentBlockedError, PlayableAudio, Utterance


class _FakeClip:
    """Stand-in playable clip whose mp3 export just touches the file."""

    def export(self, path: str, format: str, bitrate: str) -> None:  # noqa: A002
        Path(path).touch()

    def __add__(self, other: PlayableAudio) -> PlayableAudio:
        return cast(PlayableAudio, self)


def _chunk() -> Chunk:
    # (id, arabic, english, register, concept_tag, priority) — Chunk.FIELDS order.
    return Chunk.from_row(["b1", "قَتَلُوا", "They killed", "msa", "culture", "normal"])


def test_ensure_cached_should_skip_a_blocked_utterance(tmp_path: Path) -> None:
    """A content-blocked utterance stays out of the cache; the other side lands.

    The provider refuses the Arabic side (deterministic content-policy block).
    ensure_cached must not raise, must leave that key out of the cache, and
    cache the accepted English side as normal — consumers then pass over the
    utterance that has no audio.
    """
    chunk = _chunk()
    cache = AudioCache(tmp_path)

    def synth(utt: Utterance) -> PlayableAudio:
        if utt == chunk.arabic:
            raise ContentBlockedError(utt.text)
        return cast(PlayableAudio, _FakeClip())

    ensure_cached(chunk, synth, cache, force=False)

    assert chunk.english.key in cache
    assert chunk.arabic.key not in cache


def test_ensure_cached_should_cache_both_sides_when_nothing_is_blocked(
    tmp_path: Path,
) -> None:
    """A synth that accepts everything leaves both utterances cached.

    Runs ensure_cached over a fresh chunk with a synthesiser that never
    refuses, then asserts both content keys have cache entries — guarding that
    the ContentBlockedError handling added for blocked texts doesn't disturb
    the normal write path.
    """
    chunk = _chunk()
    cache = AudioCache(tmp_path)

    ensure_cached(
        chunk, lambda _utt: cast(PlayableAudio, _FakeClip()), cache, force=False
    )

    assert all(utt.key in cache for utt in chunk.utterances)
