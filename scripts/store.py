"""Persistence: the chunks.csv loader and the content-addressed audio cache.

``load_chunks`` reads the source-of-truth CSV. ``AudioCache`` is the audio
store — a MutableMapping of ``key`` to an ``<key>.mp3`` file, a live view of the
cache dir (assignment writes, access decodes, del unlinks). It encodes/decodes
through a ``Codec``, which is the single place this module imports pydub. The
cache builds its codec lazily, so commands that only delete cache files (prune)
never load pydub. PLC0415 is waived here in pyproject for that one import.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, cast

from .config import AUDIO_DIR
from .model import Chunk, ConceptTag, PlayableAudio, Register, Synthesiser, Utterance

if TYPE_CHECKING:
    from pydub import AudioSegment

__all__ = [
    "AudioCache",
    "Codec",
    "Section",
    "ensure_cached",
    "group_sections",
    "load_chunks",
    "make_codec",
    "needs_synth",
    "select_section",
]


def load_chunks(path: Path) -> list[Chunk]:
    """Load all chunks from the CSV file.

    Raises:
        FileNotFoundError: If ``path`` doesn't exist.
        ValueError: If a row is malformed/off-taxonomy, or the file has no chunks.
    """
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        chunks = [Chunk.from_row(row) for row in reader]
    if not chunks:
        raise ValueError(f"no chunks in {path}")
    return chunks


def select_section(chunks: list[Chunk], tag: str | None) -> list[Chunk]:
    """Filter chunks to a single concept_tag; return all when ``tag`` is None.

    Args:
        chunks: The chunks to filter.
        tag: The concept_tag to keep, or None for no filtering.

    Returns:
        The matching chunks (all of them when ``tag`` is None).

    Raises:
        ValueError: If ``tag`` is given but no chunk carries it.
    """
    if tag is None:
        return chunks
    selected = [c for c in chunks if c.concept_tag == tag]
    if not selected:
        raise ValueError(f"section {tag!r} not found")
    return selected


@dataclass(frozen=True, slots=True)
class Section:
    """Chunks sharing a concept_tag and Arabic register — one output unit.

    The group ``generate`` writes a single MP3 (and transcript) per, and the
    dry-run report tallies per. Owns its own ``label`` so the real run and the
    dry run can't format it differently.
    """

    tag: ConceptTag
    register: Register
    chunks: list[Chunk]

    @property
    def label(self) -> str:
        """Human label for the section, e.g. ``greetings (egyptian)``."""
        return f"{self.tag} ({self.register})"


def group_sections(chunks: list[Chunk]) -> list[Section]:
    """Group chunks into sections by (concept_tag, Arabic register).

    Preserves first-seen order, so the output sections follow the CSV. Shared by
    the real run (``generate``) and the dry-run report (``plan``) so both see the
    same sectioning.
    """
    groups: dict[tuple[ConceptTag, Register], list[Chunk]] = {}
    for chunk in chunks:
        groups.setdefault((chunk.concept_tag, chunk.arabic.register), []).append(chunk)
    return [Section(tag, reg, cs) for (tag, reg), cs in groups.items()]


class Codec:
    """The cache's mp3 boundary — the one place pydub is imported.

    Holds both directions so encode and decode can't drift onto different
    assumptions about whether pydub is loaded: building a Codec imports it once,
    up front, and both methods go through that.
    """

    def __init__(self) -> None:
        from pydub import AudioSegment

        self._segment = AudioSegment

    def decode(self, path: Path) -> PlayableAudio:
        """Read an mp3 file into a playable clip."""
        return cast(PlayableAudio, self._segment.from_file(str(path), format="mp3"))

    def encode(self, audio: PlayableAudio, path: Path) -> None:
        """Write a playable clip to an mp3 file."""
        cast("AudioSegment", audio).export(str(path), format="mp3", bitrate="128k")


def make_codec() -> Codec:
    """Build the mp3 codec (loads pydub)."""
    return Codec()


class AudioCache(MutableMapping[str, PlayableAudio]):
    """Content-addressed audio cache: key <-> ``audio_dir/<key>.mp3``.

    A live filesystem view — ``cache[key] = audio`` exports immediately,
    ``cache[key]`` decodes on access, ``del cache[key]`` unlinks. No load/save
    step. Iterating yields the cached keys (file stems), so prune is
    ``set(cache) - live_keys``. The mp3 ``Codec`` is built lazily on first
    read/write, so a delete-only pass (prune) never loads pydub.
    """

    def __init__(self, audio_dir: Path = AUDIO_DIR) -> None:
        self._dir = audio_dir

    @cached_property
    def _codec(self) -> Codec:
        return make_codec()

    def path(self, key: str) -> Path:
        return self._dir / f"{key}.mp3"

    def __getitem__(self, key: str) -> PlayableAudio:
        path = self.path(key)
        if not path.exists():
            raise KeyError(key)
        return self._codec.decode(path)

    def __setitem__(self, key: str, audio: PlayableAudio) -> None:
        self._dir.mkdir(exist_ok=True)
        self._codec.encode(audio, self.path(key))

    def __delitem__(self, key: str) -> None:
        try:
            self.path(key).unlink()
        except FileNotFoundError:
            raise KeyError(key) from None

    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and self.path(key).exists()

    def __iter__(self) -> Iterator[str]:
        return (p.stem for p in self._dir.glob("*.mp3"))

    def __len__(self) -> int:
        return sum(1 for _ in self._dir.glob("*.mp3"))


def needs_synth(utt: Utterance, cache: AudioCache, *, force: bool) -> bool:
    """Whether an utterance must be synthesised: a cache miss, or ``force``.

    The one place the synth-vs-reuse decision lives, so the dry-run plan and the
    real run can't drift on it.
    """
    return force or utt.key not in cache


def ensure_cached(
    chunk: Chunk,
    synth: Synthesiser,
    cache: AudioCache,
    *,
    force: bool = False,
) -> None:
    """Ensure both of a chunk's utterances have audio in the cache.

    Synthesises (via ``synth``) any utterance that is missing, or every one when
    ``force`` is set. The caller then reads back what it needs — the decoded
    clip (``cache[key]``) or the file path (``cache.path(key)``).

    Args:
        chunk: The chunk whose English + Arabic audio to materialise.
        synth: The synthesiser to call on a cache miss.
        cache: The audio cache to populate.
        force: Re-synthesise even when a cached file already exists.
    """
    for utt in chunk.utterances:
        if needs_synth(utt, cache, force=force):
            cache[utt.key] = synth(utt)
