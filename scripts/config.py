"""Kallim project paths — the canonical locations everything reads/writes."""

from pathlib import Path

__all__ = [
    "AUDIO_DIR",
    "CHUNKS_CSV",
    "OUTPUT_DIR",
    "PHRASES_TXT",
    "PROJECT_ROOT",
    "VOCAB_CHUNKS_REVIEW_CSV",
    "VOCAB_PAIRS_CSV",
    "VOICES_JSON",
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = PROJECT_ROOT / "audio"
OUTPUT_DIR = PROJECT_ROOT / "output"
CHUNKS_CSV = PROJECT_ROOT / "chunks.csv"
VOICES_JSON = PROJECT_ROOT / "voices.json"

# Vocab pipeline: extract-vocab agent writes vocab_pairs.csv (candidates) ->
# kallim ingest dedups/ids/validates -> vocab_chunks_review.csv -> chunks.csv.
PHRASES_TXT = PROJECT_ROOT / "phrases.txt"
VOCAB_PAIRS_CSV = PROJECT_ROOT / "vocab_pairs.csv"
VOCAB_CHUNKS_REVIEW_CSV = PROJECT_ROOT / "vocab_chunks_review.csv"
