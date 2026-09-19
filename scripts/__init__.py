"""Kallim — Arabic language-learning content pipeline.

Re-exports the pure domain model — chunks, utterances, vocab entries, and the
register enum — as the package's public API. (``TOPICS`` is an open
registry rather than a type, so it stays in ``model`` for the tags command.)
The command modules (``generate``, ``harvest``, …) and the audio layer are
imported directly by the CLI rather than re-exported here, so importing the
package stays cheap (no pydub / genanki / elevenlabs).
"""

from .model import (
    Chunk,
    PlayableAudio,
    Register,
    Synthesiser,
    Utterance,
    VocabEntry,
)

__all__ = [
    "Chunk",
    "PlayableAudio",
    "Register",
    "Synthesiser",
    "Utterance",
    "VocabEntry",
]
