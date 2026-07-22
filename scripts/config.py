"""Kallim project paths and constants — the canonical settings everything shares."""

from pathlib import Path

__all__ = [
    "AUDIO_DIR",
    "CHUNKS_CSV",
    "OUTPUT_DIR",
    "PROJECT_ROOT",
    "SCRATCH_DIR",
    "TTS_MODEL_ID",
    "VOCAB_CHUNKS_REVIEW_CSV",
    "VOCAB_PAIRS_CSV",
    "VOICES_JSON",
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
VOICES_JSON = PROJECT_ROOT / "voices.json"

# Vocab pipeline (transient, under scratch/): extract-vocab agent writes
# vocab_pairs.csv (candidates) -> kallim ingest dedups/ids/validates ->
# vocab_chunks_review.csv -> (append) -> chunks.csv.
VOCAB_PAIRS_CSV = SCRATCH_DIR / "vocab_pairs.csv"
VOCAB_CHUNKS_REVIEW_CSV = SCRATCH_DIR / "vocab_chunks_review.csv"
