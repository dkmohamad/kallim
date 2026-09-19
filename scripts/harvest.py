"""Harvest extracted vocab candidates straight into the chunk banks.

Reads a candidates CSV written by an extraction skill, dedups it against every
bank and within itself, gives each survivor an id, validates it, appends it to
the bank its register belongs to, and lints what it wrote.

**There is no staging file.** The banks in the working tree *are* the staging
area. Git already separates what has changed from what is committed, and does
it better than a second CSV can: ``git diff`` shows the new rows in their
context, ``git checkout`` discards a bad batch whole. A parallel review CSV
bought nothing git did not already provide, and cost a second copy of the data
that could be — and once was — silently overwritten.

What git cannot do is notice that a new row duplicates an existing one once
diacritics are stripped. That check belongs to ``lint``, and it runs here so a
harvest can never leave a bank in a state nobody has looked at.

All language work — extraction, translation, register and topic assignment —
happens in the skill that produced the candidates. This is the deterministic
tail: dedup, ids, validation, the append, and the lint.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .config import CHUNKS_CSV, EGYPTIAN_CSV, VOCAB_PAIRS_CSV
from .lint import lint_chunks
from .model import Chunk, Register, VocabEntry
from .utils import (
    append_csv_rows,
    generate_id,
    normalize_arabic,
    read_csv_rows,
    setup_logging,
)

__all__ = ["BANKS", "Harvest", "harvest", "load_candidates", "run"]

logger = logging.getLogger(__name__)

# Which bank each register is filed in. The partition is exact — every row in
# chunks.csv is MSA, every row in egyptian.csv is Egyptian — and routing on the
# way in is what keeps it that way. Appending everything to the default bank
# would put dialect rows in the Fuṣḥā bank, where ``--section`` and the Anki
# register tag would both then misreport them.
#
# It is a parameter rather than a constant read inside the function, so a test
# can point a harvest at temporary banks. A routine that accepts bank paths and
# then writes to hardcoded ones is not testable, and writes to the real files.
BANKS: Mapping[Register, Path] = {
    Register.ENGLISH: CHUNKS_CSV,
    Register.MSA: CHUNKS_CSV,
    Register.IRAQI: CHUNKS_CSV,
    Register.EGYPTIAN: EGYPTIAN_CSV,
}


@dataclass(frozen=True, slots=True)
class Harvest:
    """What one harvest put into the banks, and what it dropped on the way."""

    by_bank: dict[Path, list[Chunk]]
    duplicates: int

    @property
    def added(self) -> list[Chunk]:
        """Every chunk written, across all banks."""
        return [chunk for chunks in self.by_bank.values() for chunk in chunks]

    @property
    def considered(self) -> int:
        """How many candidates were read before deduping."""
        return len(self.added) + self.duplicates

    def render(self, lint_report: str) -> str:
        """The run summary: what landed where, what was dropped, and the lint.

        Ends by pointing at ``git diff`` rather than declaring success — the
        rows are in the working tree and uncommitted, and whether they are
        *right* is a judgement the command cannot make.
        """
        lines = [
            f"Candidates:  {self.considered}",
            f"  duplicates skipped: {self.duplicates}",
            f"Appended:    {len(self.added)}",
        ]
        for bank, chunks in self.by_bank.items():
            lines += ["", f"  -> {bank.name} ({len(chunks)})"]
            lines += [
                f"     {c.id}  [{c.topic}/{c.priority}]  {c.arabic.text}"
                for c in chunks[:10]
            ]
            if len(chunks) > 10:
                lines.append(f"     ... and {len(chunks) - 10} more")
        lines += ["", lint_report.strip()]
        if self.added:
            banks = " ".join(bank.name for bank in self.by_bank)
            lines += ["", f"Uncommitted. Review with `git diff {banks}`, then commit."]
        return "\n".join(lines)


def load_candidates(path: Path) -> list[VocabEntry]:
    """Load vocab candidates from a CSV in ``VocabEntry.FIELDS`` order.

    Raises:
        ValueError: If the file is a bare word list rather than the candidate
            shape, naming the columns it needs.
    """
    try:
        return read_csv_rows(path, VocabEntry.from_row)
    except ValueError as exc:
        raise ValueError(
            f"{path}: {exc}. Candidates need "
            + ", ".join(VocabEntry.FIELDS[:-1])
            + " (a plain word list carries no register or topic)"
        ) from None


def harvest(candidates_path: Path, banks: Mapping[Register, Path] = BANKS) -> Harvest:
    """Dedup, id and validate candidates, then append each to its own bank.

    Dedups against **every** bank and within the batch, so a vocalized row and
    a bare re-entry of one phrase collapse to a single chunk, and a phrase
    already held in the *other* bank is not re-added here. Checking only the
    destination would let an Egyptian phrase already in egyptian.csv be
    appended again — the one-bank blindness that would also make ``prune``
    delete the other bank's audio.

    Every survivor is built through ``Chunk.from_row``, so an off-taxonomy
    candidate fails before anything is written.

    Args:
        candidates_path: The skill-written candidates CSV.
        banks: Where each register is filed. Defaults to the real banks.

    Returns:
        The ``Harvest`` describing what landed, grouped by bank.

    Raises:
        FileNotFoundError: If a bank is absent, naming it. Treating it as empty
            would dedup against nothing and append rows to a file with no
            header. A bank holding only a header is fine: that is a first
            harvest, not a missing file.
        ValueError: If a candidate is malformed or off-taxonomy, or if a row
            already in a bank is.
    """
    seen: set[str] = set()
    for bank in set(banks.values()):
        try:
            # Not ``Chunks.load``: that refuses an empty bank, which is right
            # for the commands that *render* one (empty means truncated there)
            # and wrong here, where a header-only bank is a first harvest.
            rows = read_csv_rows(bank, Chunk.from_row)
        except FileNotFoundError:
            raise FileNotFoundError(f"bank not found: {bank}") from None
        seen |= {normalize_arabic(chunk.arabic.text) for chunk in rows}

    grouped: dict[Path, list[Chunk]] = {}
    candidates = load_candidates(candidates_path)
    for entry in candidates:
        key = normalize_arabic(entry.arabic)
        if key in seen:
            continue
        seen.add(key)
        chunk = entry.to_chunk(generate_id())
        grouped.setdefault(banks[chunk.arabic.register], []).append(chunk)

    written = sum(len(chunks) for chunks in grouped.values())
    for bank, chunks in grouped.items():
        append_csv_rows(bank, (chunk.to_row() for chunk in chunks))
        logger.info("Appended %d chunks to %s", len(chunks), bank.name)
    return Harvest(by_bank=grouped, duplicates=len(candidates) - written)


def run(args: argparse.Namespace) -> str:
    """Harvest a candidates CSV into the banks, then lint what it wrote."""
    setup_logging()
    candidates = Path(args.candidates) if args.candidates else VOCAB_PAIRS_CSV
    try:
        result = harvest(candidates)
    except (FileNotFoundError, ValueError) as exc:
        sys.exit(f"Error: {exc}")

    # Lint every bank that received rows, not just the default one.
    reports: list[str] = []
    problems = 0
    for bank in result.by_bank or {CHUNKS_CSV: []}:
        report, count = lint_chunks(bank)
        reports.append(f"{bank.name}: {report.strip()}")
        problems += count

    rendered = result.render("\n".join(reports))
    if problems:
        # The rows are already appended, so say so plainly rather than implying
        # nothing happened: `git checkout` is the undo.
        banks = " ".join(bank.name for bank in result.by_bank)
        sys.exit(
            f"{rendered}\n\nA bank does not lint. The rows above are in the "
            f"working tree — `git checkout {banks}` discards them."
        )
    return rendered
