"""Kallim — dry-run report: what a generate/anki run *would* synthesize + cost.

Read-only, mirrors ``prune``'s dry-run-by-default shape. Given the loaded chunks
and the audio cache, it works out which utterances are cache misses (or all of
them, with ``force``) via ``cache.needs_synth`` — the same rule the real run
applies — and sums their characters, which equal ElevenLabs credits on the TTS
model (1 credit/char). No synthesis, no run dir, no TTS call; the live quota (if
any) is passed in.
"""

from __future__ import annotations

from dataclasses import dataclass

from .audio import Quota
from .cache import AudioCache, needs_synth
from .chunks import Section, group_sections
from .config import TTS_MODEL_ID
from .model import Chunk, Utterance

__all__ = ["SectionPlan", "SynthPlan", "plan_synthesis", "report"]


@dataclass(frozen=True, slots=True)
class SectionPlan:
    """One section's contribution to a synthesis plan."""

    section: Section
    to_synth_count: int
    chars: int

    @property
    def label(self) -> str:
        """The section's human label (delegated to the section)."""
        return self.section.label


@dataclass(frozen=True, slots=True)
class SynthPlan:
    """What a (non-dry) generate/anki run would synthesise, and its cost."""

    total_utterances: int
    to_synth: list[Utterance]
    by_section: list[SectionPlan]

    @property
    def reused(self) -> int:
        """Utterances a real run won't synthesise: already cached, or a repeat.

        A repeat is a duplicate content key (e.g. two chunks sharing an English
        gloss) whose audio a single synthesis this run already produces.
        """
        return self.total_utterances - len(self.to_synth)

    @property
    def chars(self) -> int:
        """Characters to synthesise == credits billed (1 credit/char)."""
        return sum(len(utt.text) for utt in self.to_synth)


def plan_synthesis(chunks: list[Chunk], cache: AudioCache, *, force: bool) -> SynthPlan:
    """Compute which utterances a run would synthesise, without synthesising.

    Uses ``cache.needs_synth`` per utterance — the same cache-miss/``force`` rule
    ``cache.ensure_cached`` applies — so the plan can't drift from the real run.
    """
    total = 0
    to_synth: list[Utterance] = []
    planned: set[str] = set()
    by_section: list[SectionPlan] = []
    for section in group_sections(chunks):
        sec_count = 0
        sec_chars = 0
        for chunk in section.chunks:
            for utt in chunk.utterances:
                total += 1
                # A real (non-force) run writes each key to the cache as it
                # synthesises, so a later duplicate utterance is a cache hit —
                # billed once. Track keys already planned this run to mirror that;
                # --force re-synthesises every occurrence, so it skips the dedup.
                if needs_synth(utt, cache, force=force) and (
                    force or utt.key not in planned
                ):
                    planned.add(utt.key)
                    to_synth.append(utt)
                    sec_count += 1
                    sec_chars += len(utt.text)
        by_section.append(SectionPlan(section, sec_count, sec_chars))
    return SynthPlan(total, to_synth, by_section)


def report(
    *,
    command: str,
    section: str | None,
    force: bool,
    chunks: list[Chunk],
    cache: AudioCache,
    quota: Quota | None,
    audio_enabled: bool = True,
) -> None:
    """Print the dry-run report for a ``generate``/``anki`` invocation."""
    scope = section or "all"
    print(
        f"Dry run — kallim {command}  "
        f"(section: {scope}, force: {'yes' if force else 'no'})"
    )

    if not audio_enabled:
        print(
            f"{len(chunks)} chunks in scope · text-only (--no-audio): "
            "0 utterances to synthesize."
        )
        print("\nNothing was generated. Drop --dry-run to run for real.")
        return

    plan = plan_synthesis(chunks, cache, force=force)
    print(f"{len(chunks)} chunks in scope · {plan.total_utterances} utterances\n")
    print(f"To synthesize: {len(plan.to_synth):,}  (reused: {plan.reused:,})")
    print(
        f"Characters:    {plan.chars:,}   "
        f"≈ {plan.chars:,} credits ({TTS_MODEL_ID}, 1 credit/char)"
    )

    _print_quota(quota, plan.chars)

    print("\nBy section (utterances → chars):")
    for sec in plan.by_section:
        print(f"  {sec.label:<28} {sec.to_synth_count:>4} → {sec.chars:,}")

    print("\nNothing was generated. Drop --dry-run to run for real.")


def _print_quota(quota: Quota | None, needed: int) -> None:
    """Print the live-quota line (or an unavailable note), plus an over-quota warn."""
    if quota is None:
        print("\nQuota: unavailable (offline / no API key)")
        return
    print(
        f"\nQuota: {quota.used:,} / {quota.limit:,} used — "
        f"{quota.remaining:,} remaining ({quota.tier})"
    )
    if not quota.covers(needed):
        print(
            f"⚠ this run needs {needed:,} characters and would exceed "
            f"the {quota.remaining:,} remaining in quota."
        )
