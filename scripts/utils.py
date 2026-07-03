"""Cross-cutting helpers: ids, content hashing, CSV writing, run dirs, logging."""

import csv
import hashlib
import logging
import sys
import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path

from .config import OUTPUT_DIR

__all__ = [
    "content_hash",
    "generate_id",
    "make_run_dir",
    "setup_logging",
    "write_csv_rows",
]


def generate_id() -> str:
    """A short random id for a new chunk (8 hex chars)."""
    return uuid.uuid4().hex[:8]


def write_csv_rows(
    path: Path, header: Sequence[str], rows: Iterable[Sequence[str]]
) -> None:
    """Write a CSV file: a header row followed by the data rows.

    Args:
        path: Destination CSV path (overwritten).
        header: Column names for the first row (e.g. a model's ``FIELDS``).
        rows: The data rows, each already serialised (e.g. via ``to_row``).
    """
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


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


def setup_logging(run_dir: Path | None = None) -> None:
    """Configure the 'kallim' logger to write to stderr.

    If ``run_dir`` is given, also write a DEBUG-level run_dir/generate.log;
    commands without a run directory (e.g. promote) just pass nothing.
    """
    logger = logging.getLogger("kallim")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    if run_dir is not None:
        fh = logging.FileHandler(run_dir / "generate.log")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
