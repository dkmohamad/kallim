"""Kallim — render English-then-Arabic shadowing audio from one source.

A source is either an approved reading-material transcript (written by the
``shadow`` skill from a YouTube or podcast transcript or any text) or one topic
of a bank. Both come out the same way: ``<name>.mp3``, English, pause, Arabic,
pause, line by line, and ``<name>.md``, the transcript in the one layout
(``scripts.transcript``), ready to publish.

Dry run by default, like ``script``: the cost is reported and nothing is spent
until ``--render``.

Reading-material clips are cached in ``audio-shadow/``, apart from the banks'
``audio/``: ``prune`` deletes every clip in ``audio/`` that no bank row
produces, which would be every reading-material line. A topic's clips are bank
clips, so they share the bank cache and are usually already there.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from dotenv import load_dotenv

from .audio import get_quota, make_synthesiser, stitch
from .cache import AudioCache, Codec, needs_synth
from .chunks import Chunks
from .config import AUDIO_DIR, SHADOW_AUDIO_DIR, TTS_MODEL_ID
from .model import ContentBlockedError, PlayableAudio, Synthesiser, Utterance
from .plan import quota_lines
from .transcript import Pair, Transcript
from .utils import make_run_dir

if TYPE_CHECKING:
    from pydub import AudioSegment

__all__ = ["Source", "render_pairs", "report", "run"]

logger = logging.getLogger(__name__)

# A reading-material transcript is named <slug>-transcript.md; its outputs are
# named <slug>.
_TRANSCRIPT_SUFFIX = "-transcript"


@dataclass(frozen=True, slots=True)
class Source:
    """What to shadow: its outputs' name, its transcript, and where its clips live."""

    name: str
    transcript: Transcript
    cache: AudioCache

    @classmethod
    def from_transcript(cls, path: Path) -> Source:
        """An approved reading-material transcript, cached apart from the banks."""
        name = path.stem.removesuffix(_TRANSCRIPT_SUFFIX)
        return cls(name, Transcript.parse(path), AudioCache(SHADOW_AUDIO_DIR))

    @classmethod
    def from_topic(cls, topic: str, bank: Path) -> Source:
        """One topic of a bank, in bank order, sharing the bank's cache.

        Raises:
            ValueError: If no row in the bank carries the topic.
        """
        chunks = Chunks.load(bank).section(topic)
        title = topic.replace("_", " ").title()
        return cls(topic, Transcript.of_chunks(title, chunks), AudioCache(AUDIO_DIR))


def _to_synth(source: Source, *, force: bool) -> list[Utterance]:
    """The utterances a render would synthesise, each repeated text once."""
    seen: set[str] = set()
    due: list[Utterance] = []
    for pair in source.transcript.pairs:
        for utt in pair.utterances:
            if needs_synth(utt, source.cache, force=force) and utt.key not in seen:
                seen.add(utt.key)
                due.append(utt)
    return due


def report(source: Source, *, force: bool) -> str:
    """The dry-run summary: what would be synthesised, and what it costs."""
    pairs = list(source.transcript.pairs)
    due = _to_synth(source, force=force)
    chars = sum(len(u.spoken) for u in due)
    out = [
        f"Shadow:   {source.name}  ({source.transcript.title})",
        f"Lines:    {len(pairs)} in {len(source.transcript.sections)} section(s)",
        f"Cached:   {len(pairs) * 2 - len(due)} of {len(pairs) * 2} clips",
        f"To synth: {len(due)} clips, {chars:,} characters "
        f"== {chars:,} credits ({TTS_MODEL_ID}, 1 credit/char)",
    ]
    out += quota_lines(get_quota(), chars)
    return "\n".join(out)


def render_pairs(
    pairs: list[Pair], synth: Synthesiser, cache: AudioCache, *, force: bool
) -> tuple[list[PlayableAudio], list[Pair]]:
    """Every pair's two clips in order, synthesising what the cache lacks.

    A pair whose text the provider refuses is left out whole, English and
    Arabic together, and returned so the caller can report it: half a pair
    would play an English prompt with no Arabic after it.
    """
    clips: list[PlayableAudio] = []
    blocked: list[Pair] = []
    for pair in pairs:
        try:
            for utt in pair.utterances:
                if needs_synth(utt, cache, force=force):
                    cache[utt.key] = synth(utt)
        except ContentBlockedError:
            logger.warning("blocked by TTS content policy: %s", pair.arabic)
            blocked.append(pair)
            continue
        clips += [cache[utt.key] for utt in pair.utterances]
    return clips, blocked


def run(args: argparse.Namespace) -> str:
    """Render a shadowing source to audio (dry run unless ``--render``)."""
    load_dotenv()
    try:
        source = (
            Source.from_topic(args.topic, Path(args.input))
            if args.topic
            else Source.from_transcript(Path(args.transcript))
        )
    except ValueError as exc:
        sys.exit(f"Error: {exc}")

    if not args.render:
        return (
            report(source, force=args.force)
            + "\n\nDry run — nothing synthesised. Re-run with --render to build it."
        )

    clips, blocked = render_pairs(
        list(source.transcript.pairs),
        make_synthesiser(),
        source.cache,
        force=args.force,
    )
    track = stitch(clips, int(args.pause * 1000))

    run_dir = make_run_dir()
    mp3, md = run_dir / f"{source.name}.mp3", run_dir / f"{source.name}.md"
    Codec().encode(track, mp3)
    md.write_text(source.transcript.render(), encoding="utf-8")

    secs = len(cast("AudioSegment", track)) // 1000
    out = [f"Written:\n  {mp3}  ({secs // 60}m {secs % 60:02d}s)\n  {md}"]
    if blocked:
        out.append(f"\nLeft out, refused by the TTS content policy ({len(blocked)}):")
        out += [f"  {pair.english.text} / {pair.arabic.text}" for pair in blocked]
    return "\n".join(out)
