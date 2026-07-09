"""Tests for the dry-run synthesis plan (cache-miss counting + char/credit totals)."""

from pathlib import Path

from scripts.cache import AudioCache
from scripts.chunks import Chunks
from scripts.model import Chunk
from scripts.plan import plan_synthesis

# (id, arabic, english, register, concept_tag) — Chunk.FIELDS order.
_ROWS = [
    ["a1", "السلام عليكم", "Hello", "egyptian", "greetings"],
    ["a2", "صباح الخير", "Good morning", "egyptian", "greetings"],
]


def _chunks() -> list[Chunk]:
    return [Chunk.from_row(row) for row in _ROWS]


def test_plan_counts_every_utterance_as_a_miss_on_empty_cache(tmp_path: Path) -> None:
    """With nothing cached, both sides of every chunk are billed.

    The seed-regen case: the content-addressed cache is empty, so a plan must
    report all 2×N utterances to synthesise and sum their characters (== credits
    at 1 credit/char). Guards the core dry-run number the user gates spend on.
    """
    chunks = _chunks()
    plan = plan_synthesis(Chunks(chunks), AudioCache(tmp_path), force=False)

    assert plan.total_utterances == len(chunks) * 2
    assert len(plan.to_synth) == len(chunks) * 2
    assert plan.reused == 0
    expected_chars = sum(len(utt.text) for c in chunks for utt in (c.english, c.arabic))
    assert plan.chars == expected_chars


def test_plan_skips_a_cached_utterance_but_force_ignores_the_cache(
    tmp_path: Path,
) -> None:
    """A present cache file drops one utterance from the plan; --force re-adds it.

    ``AudioCache.__contains__`` is existence-only, so seeding the file at an
    utterance's content-key path is enough to mark it cached. Asserts the plan
    honours that (cached: 1) and that ``force`` bills everything regardless —
    the two branches of ``cache.ensure_cached``'s synth rule.
    """
    chunks = _chunks()
    cache = AudioCache(tmp_path)
    cached_utt = chunks[0].english
    cache.path(cached_utt.key).touch()

    plan = plan_synthesis(Chunks(chunks), cache, force=False)
    assert plan.reused == 1
    assert len(plan.to_synth) == len(chunks) * 2 - 1
    assert plan.chars == sum(len(u.text) for u in plan.to_synth)

    forced = plan_synthesis(Chunks(chunks), cache, force=True)
    assert forced.reused == 0
    assert len(forced.to_synth) == len(chunks) * 2


def test_plan_bills_a_repeated_utterance_once_unless_forced(tmp_path: Path) -> None:
    """A duplicate utterance is billed once on a normal run, every time on --force.

    Two chunks share an identical English gloss (same text + ENGLISH register →
    same content key). A real non-force run synthesises the first occurrence and
    cache-hits the second, so the plan must count it once; --force re-synthesises
    every occurrence, so the plan counts both. Guards the docstring's "can't
    drift from the real run" against duplicate content keys (regression: the plan
    summed every occurrence, over-stating the credit cost).
    """
    rows = [
        ["d1", "أهلا", "Welcome", "egyptian", "greetings"],
        ["d2", "مرحبا", "Welcome", "egyptian", "greetings"],
    ]
    chunks = [Chunk.from_row(row) for row in rows]
    cache = AudioCache(tmp_path)

    plan = plan_synthesis(Chunks(chunks), cache, force=False)
    assert plan.total_utterances == 4
    # The shared "Welcome" English is billed once → 3, not 4.
    assert len(plan.to_synth) == 3
    keys = [u.key for u in plan.to_synth]
    assert len(keys) == len(set(keys)), "a non-force plan holds no duplicate keys"

    forced = plan_synthesis(Chunks(chunks), cache, force=True)
    assert len(forced.to_synth) == 4  # --force re-synthesises every occurrence
