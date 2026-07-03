"""Kallim — Arabic language-learning content pipeline.

Re-exports the pure domain model — chunks, utterances, vocab entries, and the
register / concept-tag enums — as the package's public API. (The taxonomy
frozensets stay internal to ``model``; ``ConceptTag`` is the exported surface.)
The command modules (``generate``, ``promote``, …) and the audio layer are
imported directly by the CLI rather than re-exported here, so importing the
package stays cheap (no pydub / genanki / anthropic).
"""

from .model import (
    Chunk,
    ConceptTag,
    PlayableAudio,
    Register,
    Synthesiser,
    Utterance,
    VocabEntry,
)

__all__ = [
    "Chunk",
    "ConceptTag",
    "PlayableAudio",
    "Register",
    "Synthesiser",
    "Utterance",
    "VocabEntry",
]
