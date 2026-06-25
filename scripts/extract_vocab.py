#!/usr/bin/env python3
"""Extract Arabic vocabulary pairs from teacher-chat.txt.

Outputs:
  vocab.txt        — one Arabic entry per line (for quick review)
  vocab_pairs.csv  — arabic,english,register,concept_tag (for promote step)
"""

import csv
import re
import sys
from pathlib import Path
from typing import NamedTuple

ARABIC_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)


def is_arabic(text: str) -> bool:
    return bool(ARABIC_RE.search(text))


def arabic_ratio(text: str) -> float:
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return 0.0
    arabic = [c for c in alpha if ARABIC_RE.match(c)]
    return len(arabic) / len(alpha)


class VocabEntry(NamedTuple):
    arabic: str
    english: str  # empty string if no translation available
    register: str
    concept_tag: str


# ── Section definitions ─────────────────────────────────────────────
# Each section is a range of line numbers in teacher-chat.txt (1-indexed)
# mapped to (register, concept_tag).  Line ranges are inclusive.

SECTIONS: list[tuple[int, int, str, str]] = [
    # (start_line, end_line, register, concept_tag)
    (791, 807, "msa", "food"),  # Jan 13: diet vocab
    (839, 857, "msa", "travel"),  # Jan 16: transport, Morocco
    (940, 987, "msa", "food"),  # Feb 1: food, family meals, geography
    (1060, 1102, "msa", "travel"),  # Feb 6: travel (partial repeat) + Morocco
    (1112, 1131, "msa", "emotions"),  # Feb 9: feelings, countryside, dreams
    (1259, 1300, "msa", "people"),  # Feb 25: refugees, integration, generosity
    (1694, 1732, "msa", "leisure"),  # Apr 1 MSA: camping, spring, planning
    (1739, 1758, "egyptian", "greetings"),  # Apr 1 Egyptian: greetings + cafe
    (1837, 1868, "msa", "food"),  # Apr 16: Egyptian food, cooking, health
    (1940, 1966, "msa", "culture"),  # Apr 24: religion, reading, travel stories
    (2041, 2079, "msa", "leisure"),  # Apr 30: daily life, nature, parks
    (2112, 2141, "egyptian", "cafe"),  # May 14: Egyptian cafe ordering
]


def _line_to_section(line_num: int) -> tuple[str, str] | None:
    """Return (register, concept_tag) for a line number, or None."""
    for start, end, register, tag in SECTIONS:
        if start <= line_num <= end:
            return register, tag
    return None


def extract_vocab(chat_path: str) -> list[VocabEntry]:
    """Parse the chat file and return deduplicated vocab entries with metadata."""
    text = Path(chat_path).read_text(encoding="utf-8")
    lines = text.splitlines()

    # First pass: identify tab-separated vocab lines
    tab_vocab_lines: set[int] = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "\t" in stripped and is_arabic(stripped):
            parts = [p.strip() for p in stripped.split("\t")]
            if len(parts) == 2:
                if any(
                    h in stripped.lower()
                    for h in ["english", "المعنى", "العربية", "arabic"]
                ):
                    continue
                tab_vocab_lines.add(i)

    # Build vocab block ranges (±5 lines around tab vocab)
    in_vocab_block: set[int] = set()
    for i in tab_vocab_lines:
        for j in range(max(0, i - 5), min(len(lines), i + 6)):
            in_vocab_block.add(j)

    # Identify runs of consecutive Arabic-only lines (3+)
    run_start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if (
            stripped
            and is_arabic(stripped)
            and arabic_ratio(stripped) > 0.7
            and "\t" not in stripped
            and len(stripped) > 1
            and stripped not in {"img", "y"}
        ):
            if run_start is None:
                run_start = i
        else:
            if run_start is not None and i - run_start >= 3:
                for j in range(run_start, i):
                    in_vocab_block.add(j)
            run_start = None
    if run_start is not None and len(lines) - run_start >= 3:
        for j in range(run_start, len(lines)):
            in_vocab_block.add(j)

    # Second pass: extract entries with translations
    raw_entries: list[VocabEntry] = []
    seen: set[str] = set()

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or not is_arabic(stripped):
            continue
        if stripped in {"img", "y"}:
            continue

        # Determine section metadata (1-indexed line numbers in chat)
        section = _line_to_section(i + 1)
        if not section:
            continue  # not in a known vocab section
        register, tag = section

        # Tab-separated vocab line
        if "\t" in stripped:
            parts = [p.strip() for p in stripped.split("\t")]
            if len(parts) == 2:
                left, right = parts
                if any(
                    h in stripped.lower()
                    for h in ["english", "المعنى", "العربية", "arabic"]
                ):
                    continue
                if arabic_ratio(left) > arabic_ratio(right):
                    arabic_text, english_text = left, right
                elif arabic_ratio(right) > arabic_ratio(left):
                    arabic_text, english_text = right, left
                else:
                    arabic_text, english_text = left, right
                arabic_text = arabic_text.strip()
                english_text = english_text.strip()
                if arabic_text and arabic_text not in seen:
                    seen.add(arabic_text)
                    raw_entries.append(
                        VocabEntry(arabic_text, english_text, register, tag)
                    )
            continue

        # Non-tab Arabic lines inside a vocab block
        if i in in_vocab_block and arabic_ratio(stripped) > 0.7 and len(stripped) > 1:
            clean = stripped.strip("- ,،.")
            if clean and clean not in seen:
                seen.add(clean)
                raw_entries.append(VocabEntry(clean, "", register, tag))

    return _clean_entries(raw_entries)


def _clean_entries(entries: list[VocabEntry]) -> list[VocabEntry]:
    """Post-process extracted entries: normalise separators, drop junk."""
    multi_dash_re = re.compile(r"-{2,}")
    emdash_re = re.compile(r"[—–]")
    pipe_re = re.compile(r"\|")

    skip_words = {"على", "عن", "له", "حب"}
    skip_phrases = {
        "شكرا لك",
        "لا مشكلة",
        "لدي زكام و صداع",
        "اهلا انا بخير الحمد لله",
        "هذا صحيح",
        "الان احتاج الى درس واحد في الاسبوع",
    }
    skip_prefixes = ("الدرس ",)
    skip_exact = {"محل-خليج نعمة", "يوم"}
    conjugation_fragments = {"حبو", "اكلو", "شِربو", "راحو", "حبيا", "اكلنا"}

    cleaned: list[VocabEntry] = []
    seen: set[str] = set()

    for entry in entries:
        ar = entry.arabic
        if ar in skip_words or ar in skip_phrases or ar in skip_exact:
            continue
        if ar in conjugation_fragments:
            continue
        if any(ar.startswith(p) for p in skip_prefixes):
            continue

        # Split on multi-dashes, em/en-dashes, pipes, adjacent-word dashes
        parts_str = multi_dash_re.sub("\x00", ar)
        parts_str = emdash_re.sub("\x00", parts_str)
        parts_str = pipe_re.sub("\x00", parts_str)
        parts_str = re.sub(r"(?<=\S{2})-(?=\S{2})", "\x00", parts_str)
        parts = parts_str.split("\x00")

        for part in parts:
            part = part.strip("- –—,،.|\\/ ")
            part = re.sub(r"^[\s\-–—,.،|\\]+", "", part)
            part = re.sub(r"[\s\-–—,.،|\\]+$", "", part)
            if not part or len(part) <= 1 or part in seen:
                continue
            if not is_arabic(part):
                continue
            if (
                part in conjugation_fragments
                or part in skip_words
                or part in skip_exact
            ):
                continue
            seen.add(part)
            # If the entry was split, the English applies to the whole
            # group — clear it for sub-parts since it won't be accurate
            english = entry.english if len(parts) == 1 else ""
            cleaned.append(VocabEntry(part, english, entry.register, entry.concept_tag))

    return cleaned


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    chat_path = root / "teacher-chat.txt"
    vocab_txt = root / "vocab.txt"
    vocab_csv = root / "vocab_pairs.csv"

    if not chat_path.exists():
        print(f"Error: {chat_path} not found", file=sys.stderr)
        sys.exit(1)

    entries = extract_vocab(str(chat_path))

    # Write plain text (Arabic only)
    vocab_txt.write_text("\n".join(e.arabic for e in entries) + "\n", encoding="utf-8")

    # Write CSV with all metadata
    with vocab_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["arabic", "english", "register", "concept_tag"])
        for e in entries:
            writer.writerow([e.arabic, e.english, e.register, e.concept_tag])

    with_en = sum(1 for e in entries if e.english)
    without_en = sum(1 for e in entries if not e.english)
    print(f"Extracted {len(entries)} entries to {vocab_csv}")
    print(f"  {with_en} with English translations, {without_en} without")


if __name__ == "__main__":
    main()
