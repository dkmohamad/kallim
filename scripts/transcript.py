"""The shadowing transcript: one layout, read and written in one place.

Every shadowing output — a bank topic from ``generate`` or ``shadow``, and
reading material from ``shadow`` — has its transcript in this layout, so one
reading habit carries across all of them::

    # Title

    ## Section

    1. English line
       Arabic line

Numbering runs on across sections, English first because that is the order
you hear it. The Arabic is indented with a tab, which Notion reads as the list
item's child, so the text pastes into a page unchanged; any indent parses.

The same text is the render input for reading material (written by the
``shadow`` skill, approved, then parsed here) and the page published to Notion,
so what you approve is exactly what is voiced and what you read.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from .model import Chunk, Register, Utterance

__all__ = ["Pair", "Transcript", "TranscriptSection"]

_TITLE = re.compile(r"^#\s+(?P<text>.+)$")
_SECTION = re.compile(r"^##\s+(?P<text>.+)$")
_ITEM = re.compile(r"^\d+\.\s+(?P<text>.+)$")
_ARABIC_LETTER = re.compile(r"[ء-ي]")
# Western and Arabic-Indic digits. The voice misreads both, so a number in the
# Arabic must be written as words (DESIGN.md, "Rules for Arabic content").
_DIGIT = re.compile(r"[0-9٠-٩]")


@dataclass(frozen=True, slots=True)
class Pair:
    """One shadowing line: the English you hear first, then the Arabic."""

    english: Utterance
    arabic: Utterance

    @property
    def utterances(self) -> tuple[Utterance, Utterance]:
        """English then Arabic — the order they are voiced in."""
        return (self.english, self.arabic)

    @classmethod
    def of(cls, chunk: Chunk) -> Pair:
        """The pair a bank chunk shadows as."""
        return cls(chunk.english, chunk.arabic)


@dataclass(frozen=True, slots=True)
class TranscriptSection:
    """A run of pairs under one heading; ``title`` is None for an untitled run."""

    title: str | None
    pairs: Sequence[Pair]


@dataclass(frozen=True, slots=True)
class Transcript:
    """A titled, sectioned list of shadowing pairs."""

    title: str
    sections: Sequence[TranscriptSection]

    @property
    def pairs(self) -> Iterator[Pair]:
        """Every pair, in order."""
        return (pair for section in self.sections for pair in section.pairs)

    @classmethod
    def of_chunks(cls, title: str, chunks: Iterable[Chunk]) -> Transcript:
        """A one-section transcript of bank chunks, in bank order."""
        return cls(title, [TranscriptSection(None, [Pair.of(c) for c in chunks])])

    @classmethod
    def parse(cls, path: Path, register: Register = Register.MSA) -> Transcript:
        """Read a transcript written in the layout above.

        Strict on purpose: this text is about to be paid for and voiced, so a
        line that does not fit the layout is an error, not something to skip.

        Raises:
            ValueError: Naming the line, for a missing title, an unexpected
                line, a numbered line with no Arabic beneath it, English and
                Arabic the wrong way round, a digit in the Arabic, or no pairs.
        """
        title: str | None = None
        sections: list[TranscriptSection] = []
        heading: str | None = None
        pairs: list[Pair] = []
        english: tuple[int, str] | None = None

        def close_section() -> None:
            if pairs:
                sections.append(TranscriptSection(heading, list(pairs)))
                pairs.clear()

        for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = raw.rstrip()
            if not line.strip():
                continue
            if english is not None:
                if not raw[:1].isspace():
                    raise ValueError(f"line {english[0]}: no Arabic line beneath it")
                pairs.append(_pair(english, (n, line.strip()), register))
                english = None
                continue
            if title is None:
                if not (m := _TITLE.match(line)):
                    raise ValueError(f"line {n}: expected a '# Title' first")
                title = m["text"].strip()
            elif m := _SECTION.match(line):
                close_section()
                heading = m["text"].strip()
            elif m := _ITEM.match(line):
                english = (n, m["text"].strip())
            else:
                raise ValueError(f"line {n}: not part of the layout: {line.strip()!r}")

        if english is not None:
            raise ValueError(f"line {english[0]}: no Arabic line beneath it")
        close_section()
        if title is None or not sections:
            raise ValueError(f"{path.name}: no title, or no numbered lines")
        return cls(title, sections)

    def render(self) -> str:
        """The transcript as text, numbered on across sections."""
        out = [f"# {self.title}"]
        n = 0
        for section in self.sections:
            out.append("")
            if section.title:
                out += [f"## {section.title}", ""]
            for pair in section.pairs:
                n += 1
                out += [f"{n}. {pair.english.text}", f"\t{pair.arabic.text}"]
        return "\n".join(out) + "\n"


def _pair(
    english: tuple[int, str], arabic: tuple[int, str], register: Register
) -> Pair:
    """Check one English/Arabic pair and build it."""
    (en_line, en_text), (ar_line, ar_text) = english, arabic
    if _ARABIC_LETTER.search(en_text) or not _ARABIC_LETTER.search(ar_text):
        raise ValueError(f"line {en_line}: English first, then the Arabic beneath it")
    if _DIGIT.search(ar_text):
        raise ValueError(f"line {ar_line}: write numbers in the Arabic as words")
    return Pair(Utterance(en_text, Register.ENGLISH), Utterance(ar_text, register))
