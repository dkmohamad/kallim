#!/usr/bin/env python3
"""Promote vocabulary words into chunks with example sentences.

Reads vocab_pairs.csv (or a plain text file of Arabic entries) and:
- Passes through entries that are already phrase-length chunks.
- Generates example sentences for single words using the Anthropic API.
- Outputs a review CSV ready to be appended to chunks.csv.
"""

import csv
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

from scripts.generate import CHUNKS_CSV, Chunk

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def generate_id() -> str:
    return uuid.uuid4().hex[:8]


def is_chunk(arabic: str) -> bool:
    """Heuristic: an entry with 3+ words is already a usable chunk."""
    return len(arabic.split()) >= 3


def load_existing_arabic(chunks_path: Path) -> set[str]:
    """Load existing Arabic text from chunks.csv for dedup."""
    if not chunks_path.exists():
        return set()
    existing: set[str] = set()
    with chunks_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            chunk = Chunk(*row)
            existing.add(chunk.arabic)
    return existing


def load_vocab_pairs(path: Path) -> list[dict[str, str]]:
    """Load vocab pairs from CSV or plain text."""
    if path.suffix == ".csv":
        with path.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    else:
        # Plain text: one Arabic entry per line, no English
        lines = path.read_text(encoding="utf-8").splitlines()
        return [
            {"arabic": line.strip(), "english": "", "register": "msa", "concept_tag": ""}
            for line in lines
            if line.strip()
        ]


def promote_batch(
    words: list[dict[str, str]],
    api_key: str,
    batch_size: int = 30,
) -> list[dict[str, str]]:
    """Generate example sentences for words that need promotion.

    Calls the Anthropic API in batches to generate natural Arabic sentences.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    results: list[dict[str, str]] = []

    for i in range(0, len(words), batch_size):
        batch = words[i : i + batch_size]
        prompt_lines: list[str] = []
        for idx, w in enumerate(batch, 1):
            register_label = {
                "msa": "Modern Standard Arabic",
                "egyptian": "Egyptian Arabic dialect",
                "iraqi": "Iraqi Arabic dialect",
            }.get(w["register"], "Arabic")
            english_hint = f' (meaning: {w["english"]})' if w["english"] else ""
            prompt_lines.append(
                f'{idx}. {w["arabic"]}{english_hint} — register: {register_label}'
            )

        prompt = (
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

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse the response
        response_text = response.content[0].text  # type: ignore[union-attr]
        for line in response_text.strip().splitlines():
            line = line.strip()
            if not line or "|||" not in line:
                continue
            # Parse "N. arabic ||| english"
            parts = line.split("|||", 1)
            if len(parts) != 2:
                continue
            ar_part = parts[0].strip()
            en_part = parts[1].strip()
            # Remove the leading number
            ar_part = ar_part.lstrip("0123456789. ").strip()
            if ar_part and en_part:
                results.append({"arabic": ar_part, "english": en_part})

        print(f"  Generated {len(results)}/{len(words)} sentences...", file=sys.stderr)

    return results


def main(input_path: str | None = None) -> None:
    root = PROJECT_ROOT
    if input_path:
        vocab_path = Path(input_path)
    else:
        vocab_path = root / "vocab_pairs.csv"

    if not vocab_path.exists():
        sys.exit(f"Error: {vocab_path} not found")

    pairs = load_vocab_pairs(vocab_path)
    existing = load_existing_arabic(CHUNKS_CSV)

    # Split into pass-through chunks and words needing promotion
    passthrough: list[dict[str, str]] = []
    needs_promotion: list[dict[str, str]] = []

    for pair in pairs:
        arabic = pair["arabic"]
        if arabic in existing:
            continue  # already in chunks.csv
        if is_chunk(arabic) and pair["english"]:
            passthrough.append(pair)
        else:
            needs_promotion.append(pair)

    print(f"Total entries: {len(pairs)}", file=sys.stderr)
    print(f"  Already in chunks.csv: {len(pairs) - len(passthrough) - len(needs_promotion)}", file=sys.stderr)
    print(f"  Pass-through (already chunks): {len(passthrough)}", file=sys.stderr)
    print(f"  Need promotion (single words): {len(needs_promotion)}", file=sys.stderr)

    # Generate sentences for words
    promoted: list[dict[str, str]] = []
    if needs_promotion:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            sys.exit(
                "Error: ANTHROPIC_API_KEY not set. "
                "Check your .env file."
            )
        else:
            print(f"Generating sentences for {len(needs_promotion)} words...", file=sys.stderr)
            generated = promote_batch(needs_promotion, api_key)

            # Match generated sentences back to original entries for metadata
            if len(generated) == len(needs_promotion):
                for orig, gen in zip(needs_promotion, generated):
                    promoted.append({
                        "arabic": gen["arabic"],
                        "english": gen["english"],
                        "register": orig["register"],
                        "concept_tag": orig["concept_tag"],
                    })
            else:
                print(
                    f"Warning: got {len(generated)} sentences for "
                    f"{len(needs_promotion)} words. Writing originals.",
                    file=sys.stderr,
                )
                promoted = needs_promotion

    # Combine and write review CSV
    all_entries = passthrough + promoted
    out_path = root / "vocab_chunks_review.csv"

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "arabic", "english", "register", "concept_tag"])
        for entry in all_entries:
            writer.writerow([
                generate_id(),
                entry["arabic"],
                entry["english"],
                entry["register"],
                entry["concept_tag"],
            ])

    print(f"\nWrote {len(all_entries)} chunks to {out_path}", file=sys.stderr)
    print("Review this file, then append to chunks.csv when ready.", file=sys.stderr)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    main(path)
