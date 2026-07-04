"""Kallim project paths — the canonical locations everything reads/writes."""

from pathlib import Path

__all__ = [
    "AUDIO_DIR",
    "CHUNKS_CSV",
    "OUTPUT_DIR",
    "PHRASES_TXT",
    "PROJECT_ROOT",
    "SCRATCH_DIR",
    "VOCAB_CHUNKS_REVIEW_CSV",
    "VOCAB_PAIRS_CSV",
    "VOICES_JSON",
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = PROJECT_ROOT / "audio"
OUTPUT_DIR = PROJECT_ROOT / "output"
SCRATCH_DIR = PROJECT_ROOT / "scratch"  # gitignored; transient working files
CHUNKS_CSV = PROJECT_ROOT / "chunks.csv"
VOICES_JSON = PROJECT_ROOT / "voices.json"
PHRASES_TXT = PROJECT_ROOT / "phrases.txt"  # migrate input (a real input, not temp)

# Vocab pipeline (transient, under scratch/): extract-vocab agent writes
# vocab_pairs.csv (candidates) -> kallim ingest dedups/ids/validates ->
# vocab_chunks_review.csv -> (append) -> chunks.csv.
VOCAB_PAIRS_CSV = SCRATCH_DIR / "vocab_pairs.csv"
VOCAB_CHUNKS_REVIEW_CSV = SCRATCH_DIR / "vocab_chunks_review.csv"
