"""Kallim — render a lesson script page into a two-voice Arabic MP3.

A *script* is the distilled form of a recorded lesson: a dialogue between the
teacher and David, written as a Notion page and exported to markdown. This turns
one into a single track to shadow against, plus a numbered transcript to follow.

Two things make it different from ``generate``, which renders the chunk banks:

- **Two voices in one dialect.** Both people speak MSA, so ``Register`` cannot
  tell them apart. A ``Speaker`` selects the voice instead, which is why the
  synthesiser depends on the ``Speech`` port rather than on ``Utterance``.
- **Arabic only.** The English gloss is on the page for reading, never voiced,
  so glosses cost nothing. It is still required: a block without one is a parse
  error, because a half-written block is far likelier than a deliberate omission.

The page convention is the one in ``.claude/skills/distil-lesson``: ``H3`` per
turn prefixed ``**Speaker:**``, the italic gloss beneath it, ``H2`` as a silent
section break. Page order is audio order — the whole point is following along.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from dotenv import load_dotenv

from .audio import ElevenLabsSynthesiser, get_quota
from .cache import AudioCache, needs_synth
from .config import SCRIPT_AUDIO_DIR, SPEAKERS_JSON, TTS_MODEL_ID
from .model import PlayableAudio, Speaker, Synthesiser
from .utils import content_hash, make_run_dir

if TYPE_CHECKING:
    from elevenlabs.client import ElevenLabs
    from pydub import AudioSegment

__all__ = ["Line", "Marker", "Script", "run"]

# Between turns. Long enough to hear the handover, short enough that the track
# still sounds like a conversation rather than a drill.
GAP_MS = 700
SECTION_GAP_MS = 1600

BLOCK = re.compile(r"^###\s+\*\*(?P<speaker>[^:*]+):\*\*\s*(?P<arabic>.+)$")
SECTION = re.compile(r"^##\s+(?!#)(?P<title>.+)$")
GLOSS = re.compile(r"^\*(?P<text>.+)\*$")
# A bracketed aside marks something the lesson left unresolved or unclear. It is
# written on the page for the reader and must never reach the audio as speech.
BRACKETED = re.compile(r"\[[^\]]*\]")


@dataclass(frozen=True, slots=True)
class Line:
    """One spoken block: a speaker, their Arabic, and its English gloss.

    Satisfies ``Speech``, so it goes through the same TTS adapter and the same
    content-addressed cache as a bank ``Utterance``. Its voice is the speaker,
    so the same sentence said by each of them caches as two clips rather than
    one of them silently serving the other's audio.
    """

    speaker: Speaker
    arabic: str
    english: str

    @property
    def text(self) -> str:
        """The words to be spoken — the Arabic; the gloss is never voiced."""
        return self.arabic

    @property
    def voice(self) -> str:
        """The voice-map key selecting who says it."""
        return self.speaker

    @property
    def key(self) -> str:
        """Content hash identifying this line (and its cached audio)."""
        return content_hash(f"{self.speaker}\n{self.arabic}")


@dataclass(frozen=True, slots=True)
class Marker:
    """A section heading: a longer gap in the audio, no speech."""

    title: str


type Block = Line | Marker


@dataclass(frozen=True, slots=True)
class Script:
    """A parsed script page: its blocks in page order, and what they cost."""

    name: str
    blocks: list[Block]

    @classmethod
    def parse(cls, path: Path) -> Script:
        """Parse an S3-convention script page into blocks, in page order.

        Raises:
            ValueError: On an unknown speaker label, or a turn with no gloss
                beneath it — both of which mean the page is malformed rather
                than merely unusual, and would otherwise drop a turn silently.
        """
        blocks: list[Block] = []
        pending: tuple[Speaker, str] | None = None

        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if section := SECTION.match(line):
                blocks.append(Marker(section.group("title").strip()))
                continue
            if block := BLOCK.match(line):
                if pending:
                    raise ValueError(f"block with no English gloss: {pending[1][:40]}")
                speaker = Speaker.from_label(block.group("speaker").strip())
                pending = (speaker, block.group("arabic").strip())
                continue
            if pending and (gloss := GLOSS.match(line)):
                speaker, arabic = pending
                if not BRACKETED.search(arabic):  # gaps never become dead air
                    blocks.append(Line(speaker, arabic, gloss.group("text").strip()))
                pending = None

        if pending:
            raise ValueError(f"block with no English gloss: {pending[1][:40]}")
        return cls(path.stem, blocks)

    @property
    def lines(self) -> list[Line]:
        """The spoken blocks, in page order."""
        return [b for b in self.blocks if isinstance(b, Line)]

    @property
    def markers(self) -> list[Marker]:
        """The silent section breaks."""
        return [b for b in self.blocks if isinstance(b, Marker)]

    @property
    def characters(self) -> int:
        """Arabic characters across every turn — the credit cost of a full run."""
        return sum(len(line.arabic) for line in self.lines)

    def transcript(self) -> str:
        """A numbered transcript, 1:1 with the page, for following along."""
        out: list[str] = []
        n = 0
        for block in self.blocks:
            if isinstance(block, Marker):
                out += ["", f"— {block.title} —", ""]
                continue
            n += 1
            out += [
                f"{n:>3}. {block.speaker.label}: {block.arabic}",
                f"     {block.english}",
            ]
        return "\n".join(out)

    def report(self, cache: AudioCache, *, force: bool) -> str:
        """The dry-run summary: what would be synthesised, and what it costs."""
        due = [ln for ln in self.lines if needs_synth(ln, cache, force=force)]
        chars = sum(len(ln.arabic) for ln in due)

        tally: dict[Speaker, tuple[int, int]] = {}
        for ln in self.lines:
            n, c = tally.get(ln.speaker, (0, 0))
            tally[ln.speaker] = (n + 1, c + len(ln.arabic))

        out = [
            f"Script:   {self.name}",
            f"Blocks:   {len(self.lines)} turns, {len(self.markers)} section breaks",
            "",
            "By speaker (turns -> characters):",
        ]
        out += [
            f"  {sp.label:<12} {n:>3} -> {c:,}  (voice key: {sp.value})"
            for sp, (n, c) in tally.items()
        ]
        out += [
            "",
            f"Cached:   {len(self.lines) - len(due)} of {len(self.lines)} turns",
            f"To synth: {len(due)} turns, {chars:,} characters "
            f"== {chars:,} credits ({TTS_MODEL_ID}, 1 credit/char)",
            "English is not voiced, so the glosses cost nothing.",
        ]

        quota = get_quota()
        if quota is None:
            out.append("\nQuota: unavailable (no permission / offline)")
        else:
            out.append(
                f"\nQuota: {quota.used:,} / {quota.limit:,} used — "
                f"{quota.remaining:,} remaining ({quota.tier})"
            )
            if not quota.covers(chars):
                out.append(f"This run needs {chars:,} and would exceed the quota.")
        return "\n".join(out)


def load_speakers() -> dict[str, str]:
    """The speaker -> voice id map from speakers.json.

    Raises:
        FileNotFoundError: If speakers.json is absent.
        ValueError: If a speaker has no voice, which would otherwise surface as
            a bare KeyError partway through a paid run.
    """
    try:
        voices: dict[str, str] = json.loads(SPEAKERS_JSON.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"voice map not found: {SPEAKERS_JSON}") from None
    if missing := [s.value for s in Speaker if not voices.get(s.value)]:
        raise ValueError(f"{SPEAKERS_JSON}: no voice id for {', '.join(missing)}")
    return voices


def synthesise(
    lines: list[Line], synth: Synthesiser, cache: AudioCache, *, force: bool
) -> list[PlayableAudio]:
    """Materialise each line's audio in the cache, and return the clips in order.

    A content-policy refusal is *not* swallowed here, unlike ``ensure_cached``:
    a script is one continuous track, so a missing clip would leave a silent
    hole mid-dialogue rather than one skipped flashcard.
    """
    clips: list[PlayableAudio] = []
    for line in lines:
        if needs_synth(line, cache, force=force):
            cache[line.key] = synth(line)
        clips.append(cache[line.key])
    return clips


def stitch(script: Script, clips: list[PlayableAudio]) -> PlayableAudio:
    """Lay the clips out in page order with a gap between turns.

    The gap goes *before* each turn rather than after, so the track never ends
    on silence. One layout only: it is slow and clear enough to shadow against
    directly, so there is no repeat-pause variant.
    """
    from pydub import AudioSegment

    track = AudioSegment.empty()
    remaining = iter(clips)
    started = False
    for block in script.blocks:
        if isinstance(block, Marker):
            if started:
                track += AudioSegment.silent(duration=SECTION_GAP_MS)
            continue
        if started:
            track += AudioSegment.silent(duration=GAP_MS)
        track += cast("AudioSegment", next(remaining))
        started = True
    return cast(PlayableAudio, track)


def run(args: argparse.Namespace) -> str:
    """Render a script page to audio (dry run unless ``--render``)."""
    load_dotenv()
    script = Script.parse(Path(args.script))
    cache = AudioCache(audio_dir=SCRIPT_AUDIO_DIR)

    if not args.render:
        return (
            script.report(cache, force=args.force)
            + "\n\nDry run — nothing synthesised. Re-run with --render to build it."
        )

    synth = ElevenLabsSynthesiser(_client(), load_speakers())
    clips = synthesise(script.lines, synth, cache, force=args.force)
    track = stitch(script, clips)

    run_dir = make_run_dir()
    mp3, txt = run_dir / f"{script.name}.mp3", run_dir / f"{script.name}.txt"
    _export(track, mp3)
    txt.write_text(script.transcript(), encoding="utf-8")

    secs = _duration_seconds(track)
    return f"Written:\n  {mp3}  ({secs // 60}m {secs % 60:02d}s)\n  {txt}"


def _client() -> ElevenLabs:
    """The ElevenLabs client, built from the environment."""
    from elevenlabs.client import ElevenLabs

    return ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])


def _export(track: PlayableAudio, path: Path) -> None:
    """Write the finished track to an mp3."""
    cast("AudioSegment", track).export(str(path), format="mp3", bitrate="128k")


def _duration_seconds(track: PlayableAudio) -> int:
    """The track's length in whole seconds."""
    return len(cast("AudioSegment", track)) // 1000
