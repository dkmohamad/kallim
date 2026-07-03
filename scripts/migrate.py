"""One-time migration: phrases.txt -> chunks.csv."""

import argparse
import logging
import re
from pathlib import Path

from .config import CHUNKS_CSV, PHRASES_TXT
from .model import Chunk
from .utils import generate_id, setup_logging, write_csv_rows

__all__ = ["parse_phrases", "run", "strip_speaker", "write_csv"]

logger = logging.getLogger("kallim.migrate")

_SPEAKER_PREFIX = re.compile(
    r"^(YOU|STAFF|VENDOR|DRIVER|LOCAL|OPERATOR):\s*", re.IGNORECASE
)
_SUB_HEADER = re.compile(r"^---\s+.+\s+---$")
_SECTION_HEADER = re.compile(r"^#\s+(.+)")
_NUMBERED_LINE = re.compile(r"^\d+\.\s+(.+)")


def strip_speaker(text: str) -> str:
    """Remove speaker labels like 'YOU:', 'STAFF:', etc."""
    return _SPEAKER_PREFIX.sub("", text).strip()


def parse_phrases(path: Path) -> list[Chunk]:
    """Parse phrases.txt into validated Chunks.

    Raises:
        ValueError: If a parsed row is off-taxonomy (unknown register or a tag
            outside the register's scheme) — surfaced by ``Chunk.from_row``.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    chunks: list[Chunk] = []
    section_name = ""
    i = 0

    while i < len(lines):
        line = lines[i]

        # Skip sub-headers like "--- Browsing ---"
        if _SUB_HEADER.match(line.strip()):
            i += 1
            continue

        # Section header: # section_name
        header_match = _SECTION_HEADER.match(line)
        if header_match:
            section_name = header_match.group(1).strip()
            i += 1
            continue

        # Numbered English line: 1. phrase text
        numbered_match = _NUMBERED_LINE.match(line.strip())
        if numbered_match and section_name:
            english = strip_speaker(numbered_match.group(1))

            # Next non-blank line is the Arabic
            i += 1
            while i < len(lines) and lines[i].strip() == "":
                i += 1

            if i < len(lines) and not _SECTION_HEADER.match(lines[i]):
                arabic = lines[i].strip()
                register = "egyptian" if "egyptian" in section_name else "msa"
                # Strip register suffix from tag (e.g. "cafe_egyptian" -> "cafe")
                tag = re.sub(r"_(?:egyptian|msa|iraqi)$", "", section_name)
                chunks.append(
                    Chunk.from_row([generate_id(), arabic, english, register, tag])
                )
            i += 1
            continue

        i += 1

    return chunks


def write_csv(chunks: list[Chunk], path: Path) -> None:
    """Write chunks to CSV in the canonical ``Chunk.FIELDS`` order."""
    write_csv_rows(path, Chunk.FIELDS, (chunk.to_row() for chunk in chunks))


def run(_args: argparse.Namespace) -> None:
    """Migrate phrases.txt into chunks.csv (refuses to overwrite an existing one)."""
    setup_logging()
    if not PHRASES_TXT.exists():
        raise FileNotFoundError(f"{PHRASES_TXT} not found")

    if CHUNKS_CSV.exists():
        raise FileExistsError(
            f"{CHUNKS_CSV} already exists — delete it first to re-migrate"
        )

    chunks = parse_phrases(PHRASES_TXT)
    write_csv(chunks, CHUNKS_CSV)
    logger.info("Migrated %d chunks to %s", len(chunks), CHUNKS_CSV)
