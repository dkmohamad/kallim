"""ElevenLabs TTS synthesis and playable-clip composition.

``ElevenLabsSynthesiser`` turns an Utterance into playable audio (generation
only, no I/O) and is the callable adapter for the model's ``Synthesiser`` port;
``make_synthesiser`` builds it and returns it for the caller to inject (e.g. into
``ensure_cached``). ``stitch`` concatenates clips for the shadowing layout. (The
audio cache and the mp3 codec live in ``scripts.cache`` with the other
persistence.)

This module imports pydub/elevenlabs *lazily* (inside the functions that use
them) so commands that don't make audio — lint, prune, --help — don't pay to
load them. PLC0415 is waived here in pyproject for exactly this.
"""

from __future__ import annotations

import io
import json
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from .config import TTS_MODEL_ID, VOICES_JSON
from .model import ContentBlockedError, PlayableAudio, Synthesiser, Utterance

if TYPE_CHECKING:
    from elevenlabs.client import ElevenLabs
    from pydub import AudioSegment

__all__ = [
    "ElevenLabsSynthesiser",
    "Quota",
    "get_quota",
    "list_voices",
    "make_synthesiser",
    "stitch",
]

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Quota:
    """An ElevenLabs subscription's character (credit) usage snapshot."""

    used: int
    limit: int
    tier: str

    @property
    def remaining(self) -> int:
        """Characters (credits) left before the quota is exhausted."""
        return self.limit - self.used

    def covers(self, chars: int) -> bool:
        """Whether ``chars`` more characters fit within the remaining quota."""
        return chars <= self.remaining


def get_quota() -> Quota | None:
    """Live ElevenLabs usage as a ``Quota``, or None if it can't be fetched.

    Best-effort — returns None on any failure (missing API key, offline, API
    error) so the dry-run report still prints its offline character/credit
    counts. Reads ELEVENLABS_API_KEY from the environment like the synthesiser.
    """
    from elevenlabs.client import ElevenLabs

    try:
        client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
        sub = client.user.subscription.get()
        return Quota(sub.character_count, sub.character_limit, sub.tier)
    except Exception:  # best-effort resilience boundary: any failure hides quota
        logger.debug("ElevenLabs quota lookup failed", exc_info=True)
        return None


def list_voices() -> str:
    """Return a listing of all available ElevenLabs voices (for voices.json)."""
    from elevenlabs.client import ElevenLabs

    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    response = client.voices.get_all()
    lines = []
    for voice in response.voices:
        labels = ", ".join(f"{k}={v}" for k, v in (voice.labels or {}).items())
        lines.append(f"{voice.voice_id}  {voice.name}  [{labels}]")
    return "\n".join(lines)


class ElevenLabsSynthesiser:
    """Generates an utterance's audio via ElevenLabs TTS — generation only.

    The callable adapter for the model's ``Synthesiser`` port (``__call__``
    takes an Utterance and returns a clip). Persistence is the AudioCache's job;
    the caller decides when to synthesise (missing / --force) vs. load.
    """

    def __init__(self, client: ElevenLabs, voice_map: dict[str, str]) -> None:
        self._client = client
        self._voice_map = voice_map

    def __call__(self, utterance: Utterance) -> PlayableAudio:
        from pydub import AudioSegment

        audio_bytes = self._tts(utterance.text, self._voice_map[utterance.register])
        seg = self._normalize(
            AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
        )
        logger.info("  synth %s", utterance.key)
        return cast(PlayableAudio, seg)

    def _tts(self, text: str, voice_id: str) -> bytes:
        """Generate TTS audio bytes via the ElevenLabs API.

        Raises ContentBlockedError when ElevenLabs refuses the text on
        content-policy grounds; any other API failure stops the run.
        """
        from elevenlabs.core.api_error import ApiError

        # NOTE: no retry. Add a retry/backoff here if transient API errors crop up.
        try:
            audio_iter = self._client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id=TTS_MODEL_ID,
                output_format="mp3_44100_128",
            )
            return b"".join(audio_iter)
        except ApiError as e:
            if self._is_content_block(e.body):
                raise ContentBlockedError(text) from e
            raise

    @staticmethod
    def _is_content_block(body: object) -> bool:
        """Whether an ElevenLabs error body reports a content-policy refusal."""
        match body:
            case {"detail": {"status": "content_against_policy"}}:
                return True
            case _:
                return False

    @staticmethod
    def _normalize(segment: AudioSegment, target_dbfs: float = -20.0) -> AudioSegment:
        """Normalize a segment to a target loudness level."""
        return segment.apply_gain(target_dbfs - segment.dBFS)


def make_synthesiser() -> Synthesiser:
    """Build a synthesiser from the environment + config.

    Reads ELEVENLABS_API_KEY and voices.json and returns the ready engine for
    the caller to inject (e.g. into ``ensure_cached``). Raises if either input
    is absent — FileNotFoundError for voices.json, KeyError for the API key (and
    for a register whose voice isn't listed, when it's first synthesised).
    """
    from elevenlabs.client import ElevenLabs

    voice_map: dict[str, str] = json.loads(VOICES_JSON.read_text(encoding="utf-8"))
    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    return ElevenLabsSynthesiser(client, voice_map)


def stitch(clips: Iterable[PlayableAudio], pause_ms: int) -> PlayableAudio:
    """Concatenate clips with a pause after each (the shadowing layout)."""
    from pydub import AudioSegment

    section = cast(PlayableAudio, AudioSegment.empty())
    pause = cast(PlayableAudio, AudioSegment.silent(duration=pause_ms))
    for clip in clips:
        section = section + clip + pause
    return section
