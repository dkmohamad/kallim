#!/usr/bin/env python3
"""ElevenLabs TTS synthesis and playable-clip composition.

``ElevenLabsSynthesiser`` turns an Utterance into playable audio (generation
only, no I/O) and is the callable adapter for the model's ``Synthesiser`` port;
``make_synthesiser`` builds it and wires it onto ``Utterance.synthesiser`` so
utterances can synthesise themselves. ``stitch`` concatenates clips for the
shadowing layout. (The audio *store* and the mp3 codec live in
``scripts.store`` with the other persistence.)

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
from typing import TYPE_CHECKING, cast

from .config import VOICES_JSON
from .model import PlayableAudio, Synthesiser, Utterance

if TYPE_CHECKING:
    from elevenlabs.client import ElevenLabs
    from pydub import AudioSegment

logger = logging.getLogger("kallim")


def list_voices() -> None:
    """Print all available ElevenLabs voices (for filling in voices.json)."""
    from elevenlabs.client import ElevenLabs

    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    response = client.voices.get_all()
    for voice in response.voices:
        labels = ", ".join(f"{k}={v}" for k, v in (voice.labels or {}).items())
        print(f"{voice.voice_id}  {voice.name}  [{labels}]")


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

        Raises on API failure — a failed utterance stops the run.
        """
        # NOTE: no retry. Add a retry/backoff here if transient API errors crop up.
        audio_iter = self._client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )
        return b"".join(audio_iter)

    @staticmethod
    def _normalize(segment: AudioSegment, target_dbfs: float = -20.0) -> AudioSegment:
        """Normalize a segment to a target loudness level."""
        return segment.apply_gain(target_dbfs - segment.dBFS)


def make_synthesiser() -> Synthesiser:
    """Build a synthesiser from the environment + config and wire it in.

    Reads ELEVENLABS_API_KEY and voices.json, then injects the engine onto
    ``Utterance.synthesiser`` so every utterance can synthesise itself. Returns
    it too. Raises if either input is absent — FileNotFoundError for
    voices.json, KeyError for the API key (and for a register whose voice isn't
    listed, when it's first synthesised).
    """
    from elevenlabs.client import ElevenLabs

    voice_map: dict[str, str] = json.loads(VOICES_JSON.read_text(encoding="utf-8"))
    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    synth = ElevenLabsSynthesiser(client, voice_map)
    Utterance.synthesiser = synth
    return synth


def stitch(clips: Iterable[PlayableAudio], pause_ms: int) -> PlayableAudio:
    """Concatenate clips with a pause after each (the shadowing layout)."""
    from pydub import AudioSegment

    section = cast(PlayableAudio, AudioSegment.empty())
    pause = cast(PlayableAudio, AudioSegment.silent(duration=pause_ms))
    for clip in clips:
        section = section + clip + pause
    return section
