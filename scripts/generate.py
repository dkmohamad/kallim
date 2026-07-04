"""Kallim — Generate shadowing audio from chunks.csv."""

import argparse
import logging

from dotenv import load_dotenv

from .audio import list_voices, make_synthesiser, stitch
from .cache import AudioCache, ensure_cached, make_codec
from .chunks import group_sections
from .command import dry_run_report, scoped_chunks
from .model import Chunk, PlayableAudio
from .utils import make_run_dir, setup_logging

__all__ = ["list_installed_voices", "run"]

logger = logging.getLogger("kallim")


def list_installed_voices(_args: argparse.Namespace) -> None:
    """List available ElevenLabs voices (the ``voices`` command)."""
    load_dotenv()
    list_voices()


def run(args: argparse.Namespace) -> None:
    """Generate one shadowing MP3 (and transcript) per chunk section."""
    chunks = scoped_chunks(args)

    if args.dry_run:
        dry_run_report("generate", args, chunks, audio_enabled=True)
        return

    run_dir = make_run_dir()
    setup_logging(run_dir)

    pause_ms = int(args.pause * 1000)
    synth = make_synthesiser()
    cache = AudioCache()
    codec = make_codec()

    sections = group_sections(chunks)
    for idx, section in enumerate(sections, 1):
        prefix = f"{idx:02d}_{section.tag}_{section.register}"
        logger.info(
            "Processing section: %s (%d chunks)", section.label, len(section.chunks)
        )

        # Always write the transcript
        (run_dir / f"{prefix}.txt").write_text(
            _transcript(section.label, section.chunks), encoding="utf-8"
        )

        # Synthesise/load each utterance's audio, then stitch the section
        clips: list[PlayableAudio] = []
        for chunk in section.chunks:
            logger.info("  %s", chunk)
            ensure_cached(chunk, synth, cache, force=args.force)
            clips.extend(cache[utt.key] for utt in chunk.utterances)

        mp3_path = run_dir / f"{prefix}.mp3"
        codec.encode(stitch(clips, pause_ms), mp3_path)
        logger.info("Exported: %s", mp3_path)

    logger.info("Done. %d section(s) processed.", len(sections))


def _transcript(label: str, chunks: list[Chunk]) -> str:
    """A section transcript: a title then numbered english/arabic pairs."""
    title = label.replace("_", " ").title()
    lines = [f"=== {title} ===\n"]
    for idx, chunk in enumerate(chunks, 1):
        lines.append(f"{idx}. {chunk.english.text}")
        lines.append(f"   {chunk.arabic.text}\n")
    return "\n".join(lines)
