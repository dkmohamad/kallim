"""Kallim — Render the topic registry from the canonical source.

``TOPICS`` lives once, in ``scripts.model``. This command renders it so the
extract-vocab skill can fetch topics and their descriptions at run time instead
of carrying its own copy that could drift.
"""

import argparse

from .model import TOPICS

__all__ = ["render_tags", "run"]


def render_tags() -> str:
    """Listing of every registered topic with its description.

    Listed in registry order, which is declaration order, for a stable diff.
    """
    width = max(len(name) for name in TOPICS)
    rows = [f"  {name:<{width}}  {desc}" for name, desc in TOPICS.items()]
    return "\n".join(
        [
            "Topic — what a chunk is about. One registered slug per chunk;",
            "adding one costs a line in TOPICS (scripts/model.py).",
            "",
            *rows,
        ]
    )


def run(_args: argparse.Namespace) -> str:
    """Render the topic registry for display / the extract-vocab skill."""
    return render_tags()
