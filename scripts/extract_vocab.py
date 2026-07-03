#!/usr/bin/env python3
"""Extract Arabic vocabulary pairs from teacher-chat.txt.

Outputs:
  vocab.txt        — one Arabic entry per line (for quick review)
  vocab_pairs.csv  — arabic,english,register,concept_tag (for promote step)
"""

import argparse
import logging
import re
from pathlib import Path

from .config import TEACHER_CHAT, VOCAB_PAIRS_CSV, VOCAB_TXT
from .model import ConceptTag, Register, VocabEntry
from .utils import setup_logging, write_csv_rows

__all__ = ["arabic_ratio", "extract_vocab", "is_arabic", "run"]

logger = logging.getLogger("kallim.vocab")

_ARABIC_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)


def is_arabic(text: str) -> bool:
    """True if the text contains any Arabic-script character."""
    return bool(_ARABIC_RE.search(text))


def arabic_ratio(text: str) -> float:
    """Fraction of alphabetic characters that are Arabic script (0.0 if none)."""
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return 0.0
    arabic = [c for c in alpha if _ARABIC_RE.match(c)]
    return len(arabic) / len(alpha)


def extract_vocab(chat_path: Path) -> list[VocabEntry]:
    """Parse the chat file and return deduplicated vocab entries with metadata."""
    lines = chat_path.read_text(encoding="utf-8").splitlines()
    tab_lines = _tab_vocab_lines(lines)
    in_block = _vocab_block(lines, tab_lines)
    raw_entries = _extract_entries(lines, in_block)
    return _clean_entries(raw_entries)


# ── Section definitions ─────────────────────────────────────────────
# Each section is a range of line numbers in teacher-chat.txt (1-indexed)
# mapped to (register, concept_tag).  Line ranges are inclusive.

_SECTIONS: list[tuple[int, int, Register, ConceptTag]] = [
    # (start_line, end_line, register, concept_tag)
    (791, 807, Register.MSA, ConceptTag.FOOD),  # Jan 13: diet vocab
    (839, 857, Register.MSA, ConceptTag.TRAVEL),  # Jan 16: transport, Morocco
    (940, 987, Register.MSA, ConceptTag.FOOD),  # Feb 1: food, family meals
    (1060, 1102, Register.MSA, ConceptTag.TRAVEL),  # Feb 6: travel + Morocco
    (1112, 1131, Register.MSA, ConceptTag.EMOTIONS),  # Feb 9: feelings, dreams
    (1259, 1300, Register.MSA, ConceptTag.PEOPLE),  # Feb 25: refugees, generosity
    (1694, 1732, Register.MSA, ConceptTag.LEISURE),  # Apr 1 MSA: camping, spring
    (1739, 1758, Register.EGYPTIAN, ConceptTag.GREETINGS),  # Apr 1 Egyptian
    (1837, 1868, Register.MSA, ConceptTag.FOOD),  # Apr 16: food, cooking, health
    (1940, 1966, Register.MSA, ConceptTag.CULTURE),  # Apr 24: religion, reading
    (2041, 2079, Register.MSA, ConceptTag.LEISURE),  # Apr 30: daily life, parks
    (2112, 2141, Register.EGYPTIAN, ConceptTag.DINING),  # May 14: Egyptian cafe
]

_HEADER_MARKERS = ("english", "المعنى", "العربية", "arabic")


def _is_header(text: str) -> bool:
    """True if a tab line is a column header (English/Arabic labels), not vocab."""
    lowered = text.lower()
    return any(marker in lowered for marker in _HEADER_MARKERS)


def _line_to_section(line_num: int) -> tuple[Register, ConceptTag] | None:
    """Return (register, concept_tag) for a 1-indexed line number, or None."""
    for start, end, register, tag in _SECTIONS:
        if start <= line_num <= end:
            return register, tag
    return None


def _is_arabic_run_line(line: str) -> bool:
    """True if a line is a standalone (non-tab) mostly-Arabic vocab line."""
    stripped = line.strip()
    return (
        bool(stripped)
        and is_arabic(stripped)
        and arabic_ratio(stripped) > 0.7
        and "\t" not in stripped
        and len(stripped) > 1
        and stripped not in {"img", "y"}
    )


def _tab_vocab_lines(lines: list[str]) -> set[int]:
    """First pass: line numbers of tab-separated arabic/english vocab rows."""
    found: set[int] = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "\t" not in stripped or not is_arabic(stripped):
            continue
        parts = [p.strip() for p in stripped.split("\t")]
        if len(parts) == 2 and not _is_header(stripped):
            found.add(i)
    return found


def _vocab_block(lines: list[str], tab_lines: set[int]) -> set[int]:
    """Line numbers inside a vocab block: ±5 of a tab row, or a 3+ Arabic run."""
    block: set[int] = set()
    for i in tab_lines:
        block.update(range(max(0, i - 5), min(len(lines), i + 6)))

    run_start: int | None = None
    for i, line in enumerate(lines):
        if _is_arabic_run_line(line):
            if run_start is None:
                run_start = i
        else:
            if run_start is not None and i - run_start >= 3:
                block.update(range(run_start, i))
            run_start = None
    if run_start is not None and len(lines) - run_start >= 3:
        block.update(range(run_start, len(lines)))
    return block


def _tab_entry(stripped: str, register: Register, tag: ConceptTag) -> VocabEntry | None:
    """Build a VocabEntry from a tab line, picking the more-Arabic side."""
    parts = [p.strip() for p in stripped.split("\t")]
    if len(parts) != 2 or _is_header(stripped):
        return None
    left, right = parts
    if arabic_ratio(right) > arabic_ratio(left):
        arabic_text, english_text = right, left
    else:
        arabic_text, english_text = left, right
    arabic_text = arabic_text.strip()
    if not arabic_text:
        return None
    return VocabEntry(arabic_text, english_text.strip(), register, tag)


def _extract_entries(lines: list[str], in_block: set[int]) -> list[VocabEntry]:
    """Second pass: pull vocab entries out of tab rows and Arabic-run lines."""
    entries: list[VocabEntry] = []
    seen: set[str] = set()

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or not is_arabic(stripped) or stripped in {"img", "y"}:
            continue

        section = _line_to_section(i + 1)  # 1-indexed line numbers in chat
        if section is None:
            continue  # not in a known vocab section
        register, tag = section

        if "\t" in stripped:
            entry = _tab_entry(stripped, register, tag)
            if entry is not None and entry.arabic not in seen:
                seen.add(entry.arabic)
                entries.append(entry)
            continue

        if i in in_block and arabic_ratio(stripped) > 0.7 and len(stripped) > 1:
            clean = stripped.strip("- ,،.")
            if clean and clean not in seen:
                seen.add(clean)
                entries.append(VocabEntry(clean, "", register, tag))

    return entries


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


def run(_args: argparse.Namespace) -> None:
    """Extract vocab from teacher-chat.txt into vocab.txt and vocab_pairs.csv."""
    setup_logging()
    if not TEACHER_CHAT.exists():
        raise FileNotFoundError(f"{TEACHER_CHAT} not found")

    entries = extract_vocab(TEACHER_CHAT)

    VOCAB_TXT.write_text("\n".join(e.arabic for e in entries) + "\n", encoding="utf-8")
    write_csv_rows(VOCAB_PAIRS_CSV, VocabEntry.FIELDS, (e.to_row() for e in entries))

    with_en = sum(1 for e in entries if e.english)
    logger.info("Extracted %d entries to %s", len(entries), VOCAB_PAIRS_CSV)
    logger.info(
        "  %d with English translations, %d without", with_en, len(entries) - with_en
    )
