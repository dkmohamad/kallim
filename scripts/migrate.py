#!/usr/bin/env python3
"""One-time migration: phrases.txt -> chunks.csv."""

import csv
import re
import uuid
from pathlib import Path
from typing import NamedTuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = PROJECT_ROOT / "phrases.txt"
OUTPUT_PATH = PROJECT_ROOT / "chunks.csv"

SPEAKER_PREFIX = re.compile(
    r"^(YOU|STAFF|VENDOR|DRIVER|LOCAL|OPERATOR):\s*", re.IGNORECASE
)
SUB_HEADER = re.compile(r"^---\s+.+\s+---$")
SECTION_HEADER = re.compile(r"^#\s+(.+)")
NUMBERED_LINE = re.compile(r"^\d+\.\s+(.+)")

COLUMNS = ["id", "arabic", "english", "register", "concept_tag"]


class Chunk(NamedTuple):
    """A single phrase pair ready for CSV output."""

    id: str
    arabic: str
    english: str
    register: str
    concept_tag: str


def generate_id() -> str:
    """Generate a short stable hex ID (8 chars from uuid4)."""
    return uuid.uuid4().hex[:8]


def strip_speaker(text: str) -> str:
    """Remove speaker labels like 'YOU:', 'STAFF:', etc."""
    return SPEAKER_PREFIX.sub("", text).strip()


def parse_phrases(path: Path) -> list[Chunk]:
    """Parse phrases.txt into a list of Chunks."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    chunks: list[Chunk] = []
    section_name = ""
    i = 0

    while i < len(lines):
        line = lines[i]

        # Skip sub-headers like "--- Browsing ---"
        if SUB_HEADER.match(line.strip()):
            i += 1
            continue

        # Section header: # section_name
        header_match = SECTION_HEADER.match(line)
        if header_match:
            section_name = header_match.group(1).strip()
            i += 1
            continue

        # Numbered English line: 1. phrase text
        numbered_match = NUMBERED_LINE.match(line.strip())
        if numbered_match and section_name:
            english = strip_speaker(numbered_match.group(1))

            # Next non-blank line is the Arabic
            i += 1
            while i < len(lines) and lines[i].strip() == "":
                i += 1

            if i < len(lines) and not SECTION_HEADER.match(lines[i]):
                arabic = lines[i].strip()
                register = "egyptian" if "egyptian" in section_name else "msa"
                # Strip register suffix from tag (e.g. "cafe_egyptian" -> "cafe")
                tag = re.sub(r"_(?:egyptian|msa|iraqi)$", "", section_name)
                chunks.append(Chunk(
                    id=generate_id(),
                    arabic=arabic,
                    english=english,
                    register=register,
                    concept_tag=tag,
                ))
            i += 1
            continue

        i += 1

    return chunks


def write_csv(chunks: list[Chunk], path: Path) -> None:
    """Write chunks to CSV."""
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for chunk in chunks:
            writer.writerow(chunk)


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"{INPUT_PATH} not found")

    if OUTPUT_PATH.exists():
        raise FileExistsError(
            f"{OUTPUT_PATH} already exists — delete it first to re-migrate"
        )

    chunks = parse_phrases(INPUT_PATH)
    write_csv(chunks, OUTPUT_PATH)
    print(f"Migrated {len(chunks)} chunks to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
