"""Tests for the environment-backed voice map.

Voice ids are read from ``ELEVENLABS_VOICE_<MEMBER>`` for both voice axes —
``Register`` for the chunk banks, ``Speaker`` for scripts. The contract that
matters is that a missing one is caught before anything is billed.
"""

import pytest

from scripts.audio import voice_map
from scripts.model import Register, Speaker


def _set(monkeypatch: pytest.MonkeyPatch, **ids: str) -> None:
    for name, value in ids.items():
        monkeypatch.setenv(f"ELEVENLABS_VOICE_{name.upper()}", value)


def test_voice_map_reads_each_member_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every Speaker resolves to the id set under its own variable."""
    _set(monkeypatch, teacher="v-teacher", david="v-david")
    assert voice_map(Speaker) == {"teacher": "v-teacher", "david": "v-david"}


def test_one_convention_covers_both_voice_axes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Registers and Speakers use the same lookup, so there is one place to set.

    Guards against the two axes drifting back into separate config files, which
    is what this replaced: two files doing one job.
    """
    _set(
        monkeypatch,
        english="v-en",
        egyptian="v-eg",
        msa="v-msa",
        iraqi="v-iq",
        teacher="v-t",
        david="v-d",
    )
    assert voice_map(Register)["msa"] == "v-msa"
    assert voice_map(Speaker)["teacher"] == "v-t"


def test_a_missing_voice_is_reported_up_front_by_variable_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unset voice fails before synthesis, naming the variable to set.

    Discovering it lazily — on the first utterance needing that voice — means a
    run that is already part-synthesised and part-billed when it dies, and a
    bare KeyError naming the enum member rather than the variable to fix.
    """
    _set(monkeypatch, teacher="v-teacher")
    monkeypatch.delenv("ELEVENLABS_VOICE_DAVID", raising=False)
    with pytest.raises(ValueError, match="ELEVENLABS_VOICE_DAVID"):
        voice_map(Speaker)


def test_an_empty_voice_counts_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A blank variable is unset, not a valid id.

    `.env.example` ships every name with an empty value, so copying it and
    filling in only some is the likeliest way to arrive here.
    """
    _set(monkeypatch, teacher="v-teacher", david="")
    with pytest.raises(ValueError, match="ELEVENLABS_VOICE_DAVID"):
        voice_map(Speaker)
