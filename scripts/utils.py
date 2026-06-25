#!/usr/bin/env python3
"""Cross-cutting helpers: content hashing, run directories, logging setup."""

import hashlib
import logging
import sys
from datetime import datetime
from pathlib import Path

from scripts.config import OUTPUT_DIR


def content_hash(text: str) -> str:
    """Short, stable (cross-process) content hash for cache invalidation.

    Uses SHA-256, deliberately NOT Python's ``hash()`` / ``__hash__`` — string
    hashing is randomized per process (PYTHONHASHSEED), so it can't be persisted
    and compared across runs.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def make_run_dir() -> Path:
    """Create a timestamped run directory under output/."""
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def setup_logging(run_dir: Path) -> None:
    """Configure the 'kallim' logger to write to run_dir/generate.log and stderr."""
    logger = logging.getLogger("kallim")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    fh = logging.FileHandler(run_dir / "generate.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
