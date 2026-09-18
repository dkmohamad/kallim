"""Tests for bank validation — per-row rules and the across-row duplicate checks.

The duplicate checks are what make it safe for an agent to edit a bank directly
and let `git diff` be the review surface. Dedup used to live only inside
`ingest`, so it guarded exactly one of the several routes a row can take into
the file.
"""

from pathlib import Path

from scripts.lint import lint_chunks

HEADER = "id,arabic,english,register,topic,priority\n"


def _bank(tmp_path: Path, *rows: str) -> Path:
    path = tmp_path / "bank.csv"
    path.write_text(HEADER + "".join(r + "\n" for r in rows), encoding="utf-8")
    return path


def test_a_clean_bank_reports_no_problems(tmp_path: Path) -> None:
    """The baseline: valid, distinct rows pass."""
    path = _bank(
        tmp_path,
        "aaaaaaaa,مَرْحَبًا,Hello,msa,greetings,normal",
        "bbbbbbbb,شُكْرًا,Thank you,msa,greetings,normal",
    )
    report, problems = lint_chunks(path)
    assert problems == 0
    assert "OK: 2 chunks" in report


def test_duplicate_arabic_is_caught_across_diacritics(tmp_path: Path) -> None:
    """A vocalized row and a bare re-entry of the same phrase are one chunk.

    This is how a duplicate actually gets in: the two spellings look different
    on screen, so nothing about them reads as a repeat. Catching it needs the
    same normalization ingest dedups on.
    """
    path = _bank(
        tmp_path,
        "aaaaaaaa,عايِز مَنْشَفَة,I want a towel,egyptian,hotel,normal",
        "bbbbbbbb,عايز منشفة,I want a towel,egyptian,hotel,normal",
    )
    report, problems = lint_chunks(path)
    assert problems == 1
    assert "duplicates line 2" in report


def test_duplicate_ids_are_caught(tmp_path: Path) -> None:
    """Two rows sharing an id would collide as one Anki note.

    The note GUID is derived from the chunk id, so a duplicate id silently
    merges two cards into one and loses a row's scheduling history.
    """
    path = _bank(
        tmp_path,
        "aaaaaaaa,مَرْحَبًا,Hello,msa,greetings,normal",
        "aaaaaaaa,شُكْرًا,Thank you,msa,greetings,normal",
    )
    report, problems = lint_chunks(path)
    assert problems == 1
    assert "duplicate id" in report


def test_an_invalid_row_does_not_suppress_later_duplicate_checks(
    tmp_path: Path,
) -> None:
    """A malformed row is reported and skipped, not treated as fatal.

    Guards the `continue` after a construction failure: a single bad row must
    not stop the across-row checks, or one typo would hide every duplicate
    below it and lint would report a shrinking list of problems as it is fixed.
    """
    path = _bank(
        tmp_path,
        "aaaaaaaa,مَرْحَبًا,Hello,msa,not_a_real_topic,normal",
        "bbbbbbbb,شُكْرًا,Thank you,msa,greetings,normal",
        "cccccccc,شكرا,Thank you,msa,greetings,normal",
    )
    report, problems = lint_chunks(path)
    assert problems == 2
    assert "not_a_real_topic" in report
    assert "duplicates line 3" in report
