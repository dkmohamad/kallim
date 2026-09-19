"""Kallim project paths and constants — the canonical settings everything shares."""

from pathlib import Path

__all__ = [
    "AUDIO_DIR",
    "BANK_CSVS",
    "CHUNKS_CSV",
    "EGYPTIAN_CSV",
    "OUTPUT_DIR",
    "PROJECT_ROOT",
    "SCRATCH_DIR",
    "SCRIPT_AUDIO_DIR",
    "TTS_MODEL_ID",
    "VOCAB_PAIRS_CSV",
]

# The ElevenLabs model every utterance is synthesised with. It bills one credit
# per character, so a plan's character total is its credit cost. Load-bearing for
# both the synthesis call (audio._tts) and the dry-run cost claim (plan), so it
# lives here once rather than as a literal in each.
TTS_MODEL_ID = "eleven_multilingual_v2"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = PROJECT_ROOT / "audio"
OUTPUT_DIR = PROJECT_ROOT / "output"
SCRATCH_DIR = PROJECT_ROOT / "scratch"  # gitignored; transient working files
CHUNKS_CSV = PROJECT_ROOT / "chunks.csv"

# The Egyptian bank, frozen and out of the default scope. Its job is reception —
# understanding songs, media, and a future trip — not production, so it is not
# drilled and not rendered by default. Reach it with ``--input egyptian.csv``.
EGYPTIAN_CSV = PROJECT_ROOT / "egyptian.csv"

# Every chunk file whose audio must stay in the cache. ``prune`` unions these:
# a key live in *any* bank is not an orphan, so freezing a register can't make
# its audio look deletable.
BANK_CSVS = (CHUNKS_CSV, EGYPTIAN_CSV)

# Script audio is cached apart from the bank audio, and this is load-bearing:
# ``prune`` deletes every file in AUDIO_DIR whose key no chunk produces, so a
# script clip living there would be read as an orphan and deleted on the next
# ``prune --apply``. A separate directory is never walked by prune.
SCRIPT_AUDIO_DIR = PROJECT_ROOT / "audio-scripts"

# Where an extraction skill drops its candidates. `kallim harvest` reads this,
# dedups, ids and validates, and appends straight into a bank — there is no
# staging CSV between the two, because git already distinguishes the rows that
# have changed from the rows that are committed.
VOCAB_PAIRS_CSV = SCRATCH_DIR / "vocab_pairs.csv"
