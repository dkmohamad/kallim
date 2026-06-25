#!/usr/bin/env python3
"""ElevenLabs TTS audio generation and content-addressed caching.

Everything about turning a Chunk into per-side mp3 files: the ElevenLabs client,
the voice map, the content manifest, and the AudioGenerator service.
"""

import io
import json
import logging
import os
import sys
import time
from pathlib import Path

from elevenlabs.client import ElevenLabs
from pydub import AudioSegment

from scripts.config import AUDIO_DIR, VOICES_JSON
from scripts.model import Chunk, Register
from scripts.store import Manifest

logger = logging.getLogger("kallim")

# Registers required by the generate/anki pipelines.
_REQUIRED_VOICES = {Register.ENGLISH, Register.EGYPTIAN, Register.MSA, Register.IRAQI}


def load_voice_map(require: set[Register] | None = None) -> dict[str, str]:
    """Load register -> voice ID mapping from voices.json.

    Args:
        require: Set of registers that must be present.  Defaults to the
                 four TTS registers (english, egyptian, msa, iraqi).

    Returns:
        Mapping of register value string to ElevenLabs voice ID.

    Raises:
        SystemExit: If voices.json is missing or required keys are absent.
    """
    if not VOICES_JSON.exists():
        sys.exit(f"Error: {VOICES_JSON} not found. See voices.json.example.")

    with VOICES_JSON.open(encoding="utf-8") as f:
        voice_map: dict[str, str] = json.load(f)

    needed = {r.value for r in (require if require is not None else _REQUIRED_VOICES)}
    missing = needed - voice_map.keys()
    if missing:
        sys.exit(f"Error: missing voices in {VOICES_JSON}: {', '.join(sorted(missing))}")

    return voice_map


def make_client() -> ElevenLabs:
    """Build an ElevenLabs client from ELEVENLABS_API_KEY (exits if unset)."""
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        sys.exit("Error: ELEVENLABS_API_KEY not set. Check your .env file.")
    return ElevenLabs(api_key=api_key)


def generate_tts(client: ElevenLabs, text: str, voice_id: str) -> bytes:
    """Generate TTS audio bytes via ElevenLabs API, retrying once.

    Raises:
        Exception: Propagates the API error if both attempts fail — a failed
            chunk should stop the run, not be silently skipped.
    """
    for attempt in range(2):
        try:
            audio_iter = client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
            )
            return b"".join(audio_iter)
        except Exception as e:
            logger.warning(
                "TTS failed for '%s' (attempt %d/2): %s", text[:40], attempt + 1, e
            )
            if attempt == 0:
                time.sleep(2)
            else:
                raise
    raise AssertionError("unreachable: loop returns or raises")


def normalize_audio(
    segment: AudioSegment, target_dbfs: float = -20.0
) -> AudioSegment:
    """Normalize audio segment to a target loudness level."""
    change = target_dbfs - segment.dBFS
    return segment.apply_gain(change)


def list_voices(client: ElevenLabs) -> None:
    """Print all available ElevenLabs voices."""
    response = client.voices.get_all()
    for voice in response.voices:
        labels = ", ".join(
            f"{k}={v}" for k, v in (voice.labels or {}).items()
        )
        print(f"{voice.voice_id}  {voice.name}  [{labels}]")


def load_clip(path: Path) -> AudioSegment:
    """Decode a cached mp3 into an AudioSegment (a model.AudioClip)."""
    return AudioSegment.from_file(str(path), format="mp3")


class AudioGenerator:
    """Generates and caches per-chunk TTS audio.

    Holds the generation collaborators (ElevenLabs client, voice map, cache dir)
    and owns the content manifest, so callers build one per run and call
    ``generate(chunk)`` — the chunk stays a passive value object. Use as a
    context manager to persist the manifest on exit, including on error, so
    audio already paid for isn't forgotten if a run dies mid-loop.
    """

    def __init__(
        self,
        client: ElevenLabs,
        voice_map: dict[str, str],
        audio_dir: Path,
        *,
        force: bool = False,
    ) -> None:
        self._client = client
        self._voice_map = voice_map
        self._audio_dir = audio_dir
        self._force = force
        self._manifest = Manifest.load(audio_dir)

    @classmethod
    def from_env(
        cls, audio_dir: Path = AUDIO_DIR, *, force: bool = False
    ) -> "AudioGenerator":
        """Build a generator from environment + config.

        Resolves the API key into a client, loads the voice map, and ensures the
        cache dir exists — the wiring otherwise duplicated across entry points.
        """
        client = make_client()
        voice_map = load_voice_map()
        audio_dir.mkdir(exist_ok=True)
        return cls(client, voice_map, audio_dir, force=force)

    def __enter__(self) -> "AudioGenerator":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.save()

    def save(self) -> None:
        """Persist the content manifest."""
        self._manifest.save(self._audio_dir)

    def _ensure_side(self, text: str, voice_id: str, path: Path) -> None:
        """Generate, normalize, and write one TTS file. Raises on TTS failure."""
        audio_bytes = generate_tts(self._client, text, voice_id)
        seg = normalize_audio(
            AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
        )
        seg.export(str(path), format="mp3", bitrate="128k")

    def generate(self, chunk: Chunk) -> None:
        """Ensure the chunk's cached audio is present and current.

        Caches as audio/{id}_en.mp3 and audio/{id}_ar.mp3, keyed by the content
        hash in the manifest, so an edited chunk regenerates instead of serving
        stale audio. Only the side(s) whose text changed are regenerated (both
        when constructed with ``force=True``). The files are at
        ``chunk.audio_paths(audio_dir)``; decode them with ``load_clip``. Raises
        on TTS failure — a bad chunk stops the run rather than being skipped.
        """
        en_path, ar_path = chunk.audio_paths(self._audio_dir)
        en_key = chunk.en_cache_key
        ar_key = chunk.ar_cache_key
        entry = self._manifest.get(chunk.id, {})

        en_ok = not self._force and en_path.exists() and entry.get("en") == en_key
        ar_ok = not self._force and ar_path.exists() and entry.get("ar") == ar_key

        if en_ok and ar_ok:
            logger.info("  Cached: %s", chunk.id)
            return

        if not en_ok:
            self._ensure_side(chunk.english, self._voice_map["english"], en_path)
        if not ar_ok:
            self._ensure_side(chunk.arabic, self._voice_map[chunk.register], ar_path)

        self._manifest[chunk.id] = {"en": en_key, "ar": ar_key}
        logger.info("  Generated: %s", chunk.id)
