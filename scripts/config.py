#!/usr/bin/env python3
"""Kallim project paths — the canonical locations everything reads/writes."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = PROJECT_ROOT / "audio"
OUTPUT_DIR = PROJECT_ROOT / "output"
CHUNKS_CSV = PROJECT_ROOT / "chunks.csv"
VOICES_JSON = PROJECT_ROOT / "voices.json"
