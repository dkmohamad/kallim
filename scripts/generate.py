"""Kallim — Generate shadowing audio from chunks.csv."""

import argparse
import logging

from dotenv import load_dotenv

from .audio import list_voices, make_synthesiser, stitch
from .cache import AudioCache, Codec, ensure_cached
from .command import dry_run_report, scoped_chunks
from .model import PlayableAudio
from .utils import make_run_dir, setup_logging

__all__ = ["list_installed_voices", "run"]

logger = logging.getLogger(__name__)


def list_installed_voices(_args: argparse.Namespace) -> str | None:
    """Return the available ElevenLabs voices (the ``voices`` command)."""
    load_dotenv()
    return list_voices() or None


def run(args: argparse.Namespace) -> str | None:
    """Generate one shadowing MP3 (and transcript) per chunk section.

    Returns the dry-run report to print in ``--dry-run`` mode; otherwise writes
    the audio/transcripts and returns None (progress goes through the logger).
    """
    chunks = scoped_chunks(args)

    if args.dry_run:
        return dry_run_report("generate", args, chunks, audio_enabled=True)

    run_dir = make_run_dir()
    setup_logging(run_dir)

    pause_ms = int(args.pause * 1000)
    synth = make_synthesiser()
    cache = AudioCache()
    codec = Codec()

    sections = chunks.sections()
    for idx, section in enumerate(sections, 1):
        prefix = section.slug(idx)
        logger.info(
            "Processing section: %s (%d chunks)", section.label, len(section.chunks)
        )

        # Always write the transcript
        (run_dir / f"{prefix}.txt").write_text(section.transcript(), encoding="utf-8")

        # Synthesise/load each utterance's audio, then stitch the section
        clips: list[PlayableAudio] = []
        for chunk in section.chunks:
            logger.info("  %s", chunk)
            ensure_cached(chunk, synth, cache, force=args.force)
            for utt in chunk.utterances:
                try:
                    clip = cache[utt.key]
                except KeyError:  # no audio — a content-blocked text
                    continue
                clips.append(clip)

        mp3_path = run_dir / f"{prefix}.mp3"
        codec.encode(stitch(clips, pause_ms), mp3_path)
        logger.info("Exported: %s", mp3_path)

    logger.info("Done. %d section(s) processed.", len(sections))
