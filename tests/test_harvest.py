"""Tests for the deterministic harvest tail (dedup, id, append, lint gate).

`harvest` writes straight into the bank, with no staging CSV between the two —
git is the review surface. That makes the dedup and validation here the only
things standing between a candidates file and the bank, so they are what these
tests pin down.
"""

from pathlib import Path

import pytest

from scripts.harvest import harvest, load_candidates
from scripts.model import Chunk, Priority, Register, VocabEntry
from scripts.utils import write_csv_rows

# The candidate shape without a priority column, taken from the source of truth
# so a schema change flows into these tests instead of passing stale.
_CANDIDATE_HEADER = VocabEntry.FIELDS[:-1]


def _bank(tmp_path: Path, *rows: list[str]) -> Path:
    path = tmp_path / "chunks.csv"
    write_csv_rows(path, Chunk.FIELDS, list(rows))
    return path


def _banks(msa: Path, egyptian: Path | None = None) -> dict[Register, Path]:
    """Route every register into the test's own files.

    Passed explicitly on every call: the default map points at the real banks,
    and a test that forgot it once appended nine rows to them.
    """
    egyptian = egyptian if egyptian is not None else msa.parent / "egyptian.csv"
    if not egyptian.exists():
        write_csv_rows(egyptian, Chunk.FIELDS, [])
    return {
        Register.ENGLISH: msa,
        Register.MSA: msa,
        Register.IRAQI: msa,
        Register.EGYPTIAN: egyptian,
    }


def _candidates(tmp_path: Path, header: tuple[str, ...], rows: list[list[str]]) -> Path:
    path = tmp_path / "vocab_pairs.csv"
    write_csv_rows(path, header, rows)
    return path


def test_harvest_dedups_within_the_batch_and_against_the_bank(tmp_path: Path) -> None:
    """A batch folds vocalized/bare twins together and drops rows already held.

    Dedup has to consult both the bank and the rows already seen in the same
    batch. Consulting only the bank lets a batch containing two spellings of
    one phrase put both in, and nothing downstream would catch it.
    """
    bank = _bank(tmp_path, ["id0", "سلام عليكم", "hello", "msa", "greetings", "normal"])
    candidates = _candidates(
        tmp_path,
        _CANDIDATE_HEADER,
        [
            ["أُرِيدُ مِنْشَفَة", "I want a towel", "msa", "shopping"],
            ["اريد منشفة", "duplicate spelling", "msa", "shopping"],
            ["سلام عليكم", "already present", "msa", "greetings"],
        ],
    )

    result = harvest(candidates, _banks(bank))

    assert (len(result.added), result.duplicates, result.considered) == (1, 2, 3)
    assert bank.read_text(encoding="utf-8").count("\n") == 3  # header + 2 rows


def test_harvest_appends_to_the_bank_itself(tmp_path: Path) -> None:
    """The rows land in the bank, not in a staging file beside it.

    This is the whole shape of the command: there is no second copy to review,
    because the working tree is the review surface.
    """
    bank = _bank(tmp_path, ["id0", "سلام عليكم", "hello", "msa", "greetings", "normal"])
    candidates = _candidates(
        tmp_path, _CANDIDATE_HEADER, [["شكرا", "thanks", "msa", "greetings"]]
    )

    harvest(candidates, _banks(bank))

    assert "شكرا" in bank.read_text(encoding="utf-8")
    assert not list(tmp_path.glob("*review*"))


def test_harvest_carries_candidate_priority_through(tmp_path: Path) -> None:
    """A 5-column candidate keeps its priority; omitted or blank defaults normal.

    Extraction skills may omit the column or leave a cell blank, and a frame's
    high mark has to survive into the bank rather than being reset — while one
    blank cell must not abort the batch.
    """
    bank = _bank(tmp_path)
    candidates = _candidates(
        tmp_path,
        VocabEntry.FIELDS,
        [
            ["تَعَوَّدْتُ عَلَى...", "I became accustomed to...", "msa", "language", "high"],
            ["سلام عليكم", "hello", "msa", "greetings"],
            ["مع السلامة", "goodbye", "msa", "greetings", ""],
        ],
    )

    added = harvest(candidates, _banks(bank)).added

    assert [c.priority for c in added] == [
        Priority.HIGH,
        Priority.NORMAL,
        Priority.NORMAL,
    ]


def test_harvest_is_idempotent(tmp_path: Path) -> None:
    """Re-running over the same candidates adds nothing the second time.

    Without this a repeated command silently duplicates every chunk, and with
    it every future Anki card and cached clip.
    """
    bank = _bank(tmp_path)
    candidates = _candidates(
        tmp_path,
        _CANDIDATE_HEADER,
        [["شكرا جزيلا", "thanks a lot", "msa", "greetings"]],
    )

    first = harvest(candidates, _banks(bank))
    second = harvest(candidates, _banks(bank))

    assert (len(first.added), len(second.added)) == (1, 0)
    assert bank.read_text(encoding="utf-8").count("شكرا جزيلا") == 1


def test_harvest_raises_when_the_bank_is_absent(tmp_path: Path) -> None:
    """A missing bank is an error, never an empty one.

    Treating it as empty would append rows to a file with no header and dedup
    them against nothing — the same failure `prune` guards one layer up.
    """
    candidates = _candidates(
        tmp_path, _CANDIDATE_HEADER, [["شكرا", "thanks", "msa", "greetings"]]
    )

    with pytest.raises(FileNotFoundError, match="bank not found"):
        harvest(candidates, _banks(tmp_path / "nope.csv"))


def test_harvest_rejects_an_off_taxonomy_candidate_before_writing(
    tmp_path: Path,
) -> None:
    """An unregistered topic stops the batch with the bank untouched.

    Validation has to happen before the append, or a bad row lands in the bank
    and the only evidence is a lint failure afterwards.
    """
    bank = _bank(
        tmp_path, ["id0", "سلام عليكم", "hello", "egyptian", "greetings", "normal"]
    )
    before = bank.read_text(encoding="utf-8")
    candidates = _candidates(
        tmp_path, _CANDIDATE_HEADER, [["شكرا", "thanks", "msa", "not_a_topic"]]
    )

    with pytest.raises(ValueError, match="not_a_topic"):
        harvest(candidates, _banks(bank))

    assert bank.read_text(encoding="utf-8") == before


def test_load_candidates_explains_a_bare_word_list(tmp_path: Path) -> None:
    """A word list names the columns it is missing rather than failing opaquely.

    It is the likeliest wrong input, and the error is what tells the skill it
    needs to assign a register and a topic rather than dump vocabulary.
    """
    path = tmp_path / "words.csv"
    path.write_text("arabic\nشكرا\n", encoding="utf-8")

    with pytest.raises(ValueError, match="register"):
        load_candidates(path)


def test_render_points_at_the_diff_rather_than_declaring_success(
    tmp_path: Path,
) -> None:
    """The summary ends at `git diff`, because the rows are not yet judged.

    Whether a harvested row is *right* is a judgement the command cannot make,
    so it reports what it did and hands over rather than saying "done".
    """
    bank = _bank(tmp_path)
    candidates = _candidates(
        tmp_path, _CANDIDATE_HEADER, [["شكرا", "thanks", "msa", "greetings"]]
    )

    report = harvest(candidates, _banks(bank)).render("OK: 1 chunks, no problems.")

    assert "git diff" in report
    assert "Uncommitted" in report


def test_a_candidate_is_routed_to_the_bank_for_its_register(tmp_path: Path) -> None:
    """Egyptian lands in the Egyptian bank, MSA in chunks.csv.

    The banks are register-partitioned exactly — every row in chunks.csv is
    MSA, every row in egyptian.csv is Egyptian. Appending both to one bank puts
    dialect rows in the Fusha bank, where `--section` and the Anki register tag
    would then both misreport them.
    """
    msa, egy = _bank(tmp_path), tmp_path / "egyptian.csv"
    candidates = _candidates(
        tmp_path,
        _CANDIDATE_HEADER,
        [
            ["مَرْحَبًا", "hello", "msa", "greetings"],
            ["عايز منشفة", "I want a towel", "egyptian", "hotel"],
        ],
    )

    result = harvest(candidates, _banks(msa, egy))

    assert {b.name: len(c) for b, c in result.by_bank.items()} == {
        "chunks.csv": 1,
        "egyptian.csv": 1,
    }
    assert "عايز منشفة" in egy.read_text(encoding="utf-8")
    assert "عايز منشفة" not in msa.read_text(encoding="utf-8")


def test_dedup_consults_every_bank_not_just_the_destination(tmp_path: Path) -> None:
    """A phrase already held in the other bank is not appended again.

    Checking only the destination lets an Egyptian phrase already in
    egyptian.csv be re-added — the same one-bank blindness that would make
    `prune` delete the other bank's audio.
    """
    msa = tmp_path / "chunks.csv"
    write_csv_rows(
        msa, Chunk.FIELDS, [["id0", "مَرْحَبًا", "hello", "msa", "greetings", "normal"]]
    )
    egy = tmp_path / "egyptian.csv"
    write_csv_rows(
        egy,
        Chunk.FIELDS,
        [["id1", "عايز منشفة", "I want a towel", "egyptian", "hotel", "normal"]],
    )
    candidates = _candidates(
        tmp_path,
        _CANDIDATE_HEADER,
        [["عايِز مَنْشَفَة", "I want a towel", "egyptian", "hotel"]],
    )

    result = harvest(candidates, _banks(msa, egy))

    assert (len(result.added), result.duplicates) == (0, 1)
