"""Tests for the deterministic ingest tail (dedup, id, idempotent append)."""

from pathlib import Path

from scripts.ingest import append_review, build_review
from scripts.model import Chunk, Priority, VocabEntry
from scripts.utils import read_csv_rows, write_csv_rows

# The legacy 4-column candidate shape (no priority), relative to the source of
# truth so a schema change flows into these tests instead of passing stale.
_CANDIDATE_HEADER = VocabEntry.FIELDS[:-1]


def _write(path: Path, header: tuple[str, ...], rows: list[list[str]]) -> None:
    write_csv_rows(path, header, rows)


def test_build_review_should_dedup_within_batch_and_against_chunks(
    tmp_path: Path,
) -> None:
    """A batch folds vocalized/bare twins together and drops existing chunks.

    Arrange a candidates CSV with a vocalized + bare spelling of the same
    phrase (a within-batch duplicate) plus one phrase already in chunks.csv;
    act by building the review; assert only the one genuinely-new phrase
    survives. Guards the dedup contract: the build must consult both chunks.csv
    and the rows already seen in the same batch, not just chunks.csv.
    """
    chunks = tmp_path / "chunks.csv"
    _write(
        chunks,
        Chunk.FIELDS,
        [["id0", "سلام عليكم", "hello", "egyptian", "greetings", "normal"]],
    )
    candidates = tmp_path / "cand.csv"
    _write(
        candidates,
        _CANDIDATE_HEADER,
        [
            ["عايِز مَنْشَفَة", "I want a towel", "egyptian", "shopping"],
            ["عايز منشفة", "duplicate spelling", "egyptian", "shopping"],
            ["سلام عليكم", "already present", "egyptian", "greetings"],
        ],
    )
    review = tmp_path / "review.csv"

    written = build_review(candidates, chunks, review)

    assert written == 1


def test_build_review_should_carry_candidate_priority_through(tmp_path: Path) -> None:
    """A 5-column candidate keeps its priority; omitted or blank defaults normal.

    Arrange a candidates CSV mixing a high-priority frame row (5 columns), a
    plain row (4 columns, no priority), and a row with a blank priority cell;
    act by building the review; assert high/normal/normal. Guards the optional
    priority column: extraction agents may omit the column or leave a cell
    blank, and a frame's high mark must survive into the review CSV rather
    than being reset — while one blank cell must not abort the batch.
    """
    candidates = tmp_path / "cand.csv"
    _write(
        candidates,
        VocabEntry.FIELDS,
        [
            ["تَعَوَّدْتُ عَلَى...", "I became accustomed to...", "msa", "language", "high"],
            ["سلام عليكم", "hello", "egyptian", "greetings"],
            ["مع السلامة", "goodbye", "egyptian", "greetings", ""],
        ],
    )
    review = tmp_path / "review.csv"

    build_review(candidates, tmp_path / "chunks.csv", review)

    priorities = [c.priority for c in read_csv_rows(review, Chunk.from_row)]
    assert priorities == [Priority.HIGH, Priority.NORMAL, Priority.NORMAL]


def test_append_review_should_be_idempotent(tmp_path: Path) -> None:
    """Re-running --append commits the reviewed rows once, not twice.

    Arrange a chunks.csv and a reviewed CSV; act by appending twice; assert the
    second append is a no-op and chunks.csv holds each reviewed row exactly
    once. Guards against the double-append that would silently duplicate every
    chunk (and its future Anki card / audio) when the command is re-run.
    """
    chunks = tmp_path / "chunks.csv"
    _write(
        chunks,
        Chunk.FIELDS,
        [["id0", "سلام عليكم", "hello", "egyptian", "greetings", "normal"]],
    )
    review = tmp_path / "review.csv"
    _write(
        review,
        Chunk.FIELDS,
        [["id1", "شكرا جزيلا", "thank you very much", "egyptian", "greetings", "high"]],
    )

    first = append_review(review, chunks)
    second = append_review(review, chunks)

    assert (first, second) == (1, 0)
    data_rows = chunks.read_text(encoding="utf-8").splitlines()[1:]
    assert len(data_rows) == 2  # the pre-existing row + the reviewed row, once
