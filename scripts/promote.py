"""Promote vocabulary words into chunks with example sentences.

Reads vocab_pairs.csv (arabic,english,register,concept_tag) and:
- Passes through entries that are already phrase-length chunks.
- Generates example sentences for single words using the Anthropic API.
- Outputs a review CSV ready to be appended to chunks.csv.
"""

import argparse
import csv
import logging
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from .config import CHUNKS_CSV, VOCAB_CHUNKS_REVIEW_CSV, VOCAB_PAIRS_CSV
from .model import Chunk, VocabEntry
from .store import load_chunks
from .utils import generate_id, setup_logging, write_csv_rows

__all__ = [
    "is_chunk",
    "load_existing_arabic",
    "load_vocab_pairs",
    "promote_batch",
    "run",
]

logger = logging.getLogger("kallim.promote")


def is_chunk(arabic: str) -> bool:
    """Heuristic: an entry with 3+ words is already a usable chunk."""
    return len(arabic.split()) >= 3


def load_existing_arabic(chunks_path: Path) -> set[str]:
    """Arabic text already in chunks.csv, for dedup (empty if it doesn't exist)."""
    if not chunks_path.exists():
        return set()
    return {chunk.arabic.text for chunk in load_chunks(chunks_path)}


def load_vocab_pairs(path: Path) -> list[VocabEntry]:
    """Load vocab entries from a CSV (arabic,english,register,concept_tag).

    Args:
        path: Path to a ``.csv`` with the four vocab columns.

    Returns:
        One VocabEntry per row, with register/concept_tag as taxonomy members.

    Raises:
        ValueError: If ``path`` isn't a CSV (a bare word list has no register or
            concept_tag, so it can't become chunks), or a row is off-taxonomy.
    """
    if path.suffix != ".csv":
        raise ValueError(
            f"{path} is not a .csv; vocab input needs arabic,english,register,"
            "concept_tag columns (a plain word list carries no register/tag)"
        )
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        return [VocabEntry.from_row(row) for row in reader]


def promote_batch(
    words: list[VocabEntry],
    api_key: str,
    batch_size: int = 30,
) -> list[tuple[str, str]]:
    """Generate (arabic_sentence, english_translation) pairs for each word.

    Calls the Anthropic API in batches. Returns one pair per parsed reply line;
    the caller checks the count matches the input.
    """
    client = anthropic.Anthropic(api_key=api_key)
    results: list[tuple[str, str]] = []

    for i in range(0, len(words), batch_size):
        batch = words[i : i + batch_size]
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": _build_prompt(batch)}],
        )
        text = response.content[0].text  # type: ignore[union-attr]
        results.extend(_parse_reply(text))
        logger.info("Generated %d/%d sentences...", len(results), len(words))

    return results


def run(args: argparse.Namespace) -> None:
    """Promote single vocab words into example-sentence chunks (review CSV)."""
    load_dotenv()
    setup_logging()

    vocab_path = Path(args.input_file) if args.input_file else VOCAB_PAIRS_CSV
    pairs = load_vocab_pairs(vocab_path)  # raises FileNotFoundError if absent
    existing = load_existing_arabic(CHUNKS_CSV)

    # Split into pass-through chunks and words needing promotion
    passthrough: list[VocabEntry] = []
    needs_promotion: list[VocabEntry] = []
    for entry in pairs:
        if entry.arabic in existing:
            continue  # already in chunks.csv
        if is_chunk(entry.arabic) and entry.english:
            passthrough.append(entry)
        else:
            needs_promotion.append(entry)

    logger.info("Total entries: %d", len(pairs))
    logger.info(
        "  Already in chunks.csv: %d",
        len(pairs) - len(passthrough) - len(needs_promotion),
    )
    logger.info("  Pass-through (already chunks): %d", len(passthrough))
    logger.info("  Need promotion (single words): %d", len(needs_promotion))

    promoted: list[VocabEntry] = []
    if needs_promotion:
        api_key = os.environ["ANTHROPIC_API_KEY"]  # raises KeyError if unset
        logger.info("Generating sentences for %d words...", len(needs_promotion))
        generated = promote_batch(needs_promotion, api_key)
        if len(generated) != len(needs_promotion):
            raise ValueError(
                f"expected {len(needs_promotion)} sentences, got {len(generated)}"
            )
        # Keep each original's register/tag; take the generated arabic/english.
        promoted = [
            VocabEntry(
                arabic=arabic,
                english=english,
                register=orig.register,
                concept_tag=orig.concept_tag,
            )
            for orig, (arabic, english) in zip(needs_promotion, generated)
        ]

    # Build validated chunks and write the review CSV
    chunks = [entry.to_chunk(generate_id()) for entry in passthrough + promoted]
    write_csv_rows(
        VOCAB_CHUNKS_REVIEW_CSV, Chunk.FIELDS, (chunk.to_row() for chunk in chunks)
    )

    logger.info("Wrote %d chunks to %s", len(chunks), VOCAB_CHUNKS_REVIEW_CSV)
    logger.info("Review this file, then append to chunks.csv when ready.")


def _build_prompt(batch: list[VocabEntry]) -> str:
    """Build the sentence-generation prompt for one batch of words."""
    prompt_lines: list[str] = []
    for idx, entry in enumerate(batch, 1):
        english_hint = f" (meaning: {entry.english})" if entry.english else ""
        prompt_lines.append(
            f"{idx}. {entry.arabic}{english_hint} — register: {entry.register.label}"
        )
    return (
        "You are helping an intermediate Arabic learner build flashcards.\n\n"
        "For each word below, generate:\n"
        "1. A short, natural example sentence (5-10 words) using the word "
        "in the specified register. The sentence should be something a "
        "learner might actually say or hear in daily life.\n"
        "2. An English translation of the sentence.\n\n"
        "IMPORTANT: Write all Arabic text with full tashkeel "
        "(vowel diacritics: fatḥa, kasra, ḍamma, sukūn, shadda, tanwīn). "
        "This is essential for the learner to read correctly.\n\n"
        "Format each response as:\n"
        "N. arabic_sentence ||| english_translation\n\n"
        "Words:\n" + "\n".join(prompt_lines)
    )


def _parse_reply(text: str) -> list[tuple[str, str]]:
    """Parse 'N. arabic ||| english' reply lines into (arabic, english) pairs."""
    pairs: list[tuple[str, str]] = []
    for raw in text.strip().splitlines():
        line = raw.strip()
        if not line or "|||" not in line:
            continue
        ar_part, _, en_part = line.partition("|||")
        # Drop the leading list number from the Arabic half.
        arabic = ar_part.strip().lstrip("0123456789. ").strip()
        english = en_part.strip()
        if arabic and english:
            pairs.append((arabic, english))
    return pairs
