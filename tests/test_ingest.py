"""Tests for the deterministic ingest tail (dedup, id, idempotent append)."""

from pathlib import Path

from scripts.ingest import append_review, build_review
from scripts.model import Chunk
from scripts.utils import write_csv_rows

_CANDIDATE_HEADER = ("arabic", "english", "register", "concept_tag")


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
        chunks, Chunk.FIELDS, [["id0", "سلام عليكم", "hello", "egyptian", "greetings"]]
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


def test_append_review_should_be_idempotent(tmp_path: Path) -> None:
    """Re-running --append commits the reviewed rows once, not twice.

    Arrange a chunks.csv and a reviewed CSV; act by appending twice; assert the
    second append is a no-op and chunks.csv holds each reviewed row exactly
    once. Guards against the double-append that would silently duplicate every
    chunk (and its future Anki card / audio) when the command is re-run.
    """
    chunks = tmp_path / "chunks.csv"
    _write(
        chunks, Chunk.FIELDS, [["id0", "سلام عليكم", "hello", "egyptian", "greetings"]]
    )
    review = tmp_path / "review.csv"
    _write(
        review,
        Chunk.FIELDS,
        [["id1", "شكرا جزيلا", "thank you very much", "egyptian", "greetings"]],
    )

    first = append_review(review, chunks)
    second = append_review(review, chunks)

    assert (first, second) == (1, 0)
    data_rows = chunks.read_text(encoding="utf-8").splitlines()[1:]
    assert len(data_rows) == 2  # the pre-existing row + the reviewed row, once
