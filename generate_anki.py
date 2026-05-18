#!/usr/bin/env python3
"""Kallim — Generate Anki flashcard deck with audio from phrases.txt."""

import argparse
import hashlib
import io
import logging
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from generate import parse_input, generate_tts, normalize_audio

logger = logging.getLogger("kallim.anki")

# Fixed IDs so re-runs update existing cards rather than creating duplicates
DECK_ID = 2059400110
MODEL_ID = 1607392319

SPEAKER_PREFIX = re.compile(
    r"^(?:YOU|STAFF|VENDOR|DRIVER|LOCAL|OPERATOR):\s*", re.IGNORECASE
)


def setup_logging():
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    logger.addHandler(sh)


def strip_speaker(text: str) -> str:
    return SPEAKER_PREFIX.sub("", text)


def audio_filename(text: str, lang: str) -> str:
    """Deterministic filename from text content for caching."""
    h = hashlib.md5(text.encode("utf-8")).hexdigest()[:10]
    return f"kallim_{lang}_{h}.mp3"


def get_or_generate_audio(
    client, text: str, voice_id: str, lang: str, cache_dir: Path
) -> Path | None:
    """Return path to audio file, generating via TTS if not cached."""
    fname = audio_filename(text, lang)
    fpath = cache_dir / fname
    if fpath.exists():
        logger.info("  Cached: %s", fname)
        return fpath

    audio_bytes = generate_tts(client, text, voice_id)
    if not audio_bytes:
        return None

    # Normalize volume
    from pydub import AudioSegment

    seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
    seg = normalize_audio(seg)
    seg.export(str(fpath), format="mp3", bitrate="128k")
    logger.info("  Generated: %s", fname)
    return fpath


def build_model():
    import genanki

    return genanki.Model(
        MODEL_ID,
        "Kallim Egyptian Arabic",
        fields=[
            {"name": "English"},
            {"name": "Arabic"},
            {"name": "EnglishAudio"},
            {"name": "ArabicAudio"},
        ],
        templates=[
            {
                "name": "English → Arabic",
                "qfmt": (
                    '<div class="english">{{English}}</div>'
                    "<div>{{EnglishAudio}}</div>"
                ),
                "afmt": (
                    '{{FrontSide}}<hr id="answer">'
                    '<div class="arabic">{{Arabic}}</div>'
                    "<div>{{ArabicAudio}}</div>"
                ),
            },
        ],
        css=(
            ".card { font-family: sans-serif; text-align: center; padding: 20px; }\n"
            ".english { font-size: 24px; margin-bottom: 15px; }\n"
            ".arabic { font-size: 36px; direction: rtl; font-family: 'Noto Sans Arabic', "
            "'Arial', sans-serif; margin-top: 15px; line-height: 1.6; }\n"
        ),
    )


def main():
    load_dotenv()
    setup_logging()

    parser = argparse.ArgumentParser(description="Kallim — Anki deck generator")
    parser.add_argument(
        "--input", "-i", default="phrases.txt", help="Path to phrases file"
    )
    parser.add_argument(
        "--output", "-o", default="kallim_egyptian_arabic.apkg", help="Output .apkg path"
    )
    parser.add_argument("--section", "-s", help="Process only this section")
    parser.add_argument(
        "--no-audio", action="store_true", help="Generate text-only cards (no TTS)"
    )
    args = parser.parse_args()

    import genanki

    sections = parse_input(args.input)
    if not sections:
        sys.exit("Error: no sections found in input file")

    if args.section:
        sections = [s for s in sections if s.name == args.section]
        if not sections:
            sys.exit(f"Error: section '{args.section}' not found")

    # Set up ElevenLabs client if generating audio
    client = None
    en_voice = None
    ar_voice = None
    cache_dir = Path("anki_audio")

    if not args.no_audio:
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        en_voice = os.environ.get("ELEVENLABS_ENGLISH_VOICE_ID")
        ar_voice = os.environ.get("ELEVENLABS_ARABIC_VOICE_ID")
        if not all([api_key, en_voice, ar_voice]):
            sys.exit(
                "Error: ELEVENLABS_API_KEY, ELEVENLABS_ENGLISH_VOICE_ID, and "
                "ELEVENLABS_ARABIC_VOICE_ID must be set in .env"
            )
        from elevenlabs.client import ElevenLabs

        client = ElevenLabs(api_key=api_key)
        cache_dir.mkdir(exist_ok=True)

    model = build_model()
    deck = genanki.Deck(DECK_ID, "Kallim Egyptian Arabic")
    media_files = []

    total_cards = 0
    for section in sections:
        tag = section.name
        logger.info("Section: %s (%d phrases)", section.name, len(section.phrases))

        for en_raw, ar_text in section.phrases:
            en_text = strip_speaker(en_raw)

            en_sound = ""
            ar_sound = ""

            if client:
                logger.info("  TTS: %s / %s", en_text[:30], ar_text[:30])
                en_path = get_or_generate_audio(
                    client, en_text, en_voice, "en", cache_dir
                )
                ar_path = get_or_generate_audio(
                    client, ar_text, ar_voice, "ar", cache_dir
                )
                if en_path:
                    en_sound = f"[sound:{en_path.name}]"
                    media_files.append(str(en_path))
                if ar_path:
                    ar_sound = f"[sound:{ar_path.name}]"
                    media_files.append(str(ar_path))

            note = genanki.Note(
                model=model,
                fields=[en_text, ar_text, en_sound, ar_sound],
                tags=[tag],
            )
            deck.add_note(note)
            total_cards += 1

    package = genanki.Package(deck)
    package.media_files = media_files
    package.write_to_file(args.output)

    logger.info(
        "Done. %d cards across %d section(s) → %s",
        total_cards,
        len(sections),
        args.output,
    )


if __name__ == "__main__":
    main()
