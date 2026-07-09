"""Kallim — Render the concept_tag taxonomy from the canonical source.

The taxonomy lives once, in ``scripts.model`` (``ConceptTag`` + ``_TAXONOMY``).
This command renders it so the extract-vocab skill can fetch tags and their
descriptions at run time instead of carrying its own copy that could drift.
"""

import argparse

from .model import ConceptTag, Scheme, tags_for

__all__ = ["render_tags", "run"]

# Presentation only — the heading per scheme. The tag membership itself comes
# from the model (``tags_for``), so it can't drift from the taxonomy.
_HEADINGS = {
    Scheme.SITUATIONAL: "Situational — for `egyptian` (travel-phrasebook situations)",
    Scheme.TOPICAL: "Topical — for `msa` / `iraqi` (conversation topics)",
}


def render_tags(scheme: Scheme | None = None) -> str:
    """Markdown-ish listing of each tag and its description, grouped by scheme.

    With ``scheme`` given, only that scheme's tags are shown; otherwise both.
    Tags are listed in ``ConceptTag`` declaration order for a stable diff.
    """
    schemes = list(_HEADINGS) if scheme is None else [scheme]
    blocks: list[str] = []
    for sch in schemes:
        tags = tags_for(sch)
        width = max(len(tag.value) for tag in tags)
        rows = [
            f"  {tag.value:<{width}}  {tag.description}"
            for tag in ConceptTag
            if tag in tags
        ]
        blocks.append("\n".join([f"{_HEADINGS[sch]}:", *rows]))
    return "\n\n".join(blocks)


def run(args: argparse.Namespace) -> str:
    """Render the taxonomy (optionally one scheme) for display / the skill."""
    scheme = None if args.scheme is None else Scheme(args.scheme)
    return render_tags(scheme)
