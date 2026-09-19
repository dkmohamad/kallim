#!/usr/bin/env python3
"""Nudge, once, when no lesson has been distilled for a while.

Runs as a SessionStart hook. Prints **one line** when a distil is due and
nothing at all otherwise — a hook that speaks every session stops being read.

**It cannot tell whether a lesson is actually waiting.** The Recordings
database is behind the claude.ai Notion connector, which is OAuth and reachable
only from inside a Claude session — there is no API token a shell script could
use. So this is a timer over the local ledger: it says "it has been a while",
and `/distil-due` does the real check and may well answer "nothing new". That
is the honest split, and it keeps this script free of any network call.

Exits 0 always. A broken nudge must never be able to block a session.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

LEDGER = Path.home() / ".local/state/kallim/distilled.json"

# Lessons run about twice a week, so three days is the point at which one has
# plausibly happened and gone un-distilled. Shorter and the nudge fires between
# lessons; longer and a lesson sits unprocessed for most of a week.
DUE_AFTER_DAYS = 3


def last_distilled(ledger: Path) -> date | None:
    """The most recent distil date, or None if there is no usable ledger.

    Treats every failure the same way — absent, unreadable, malformed, empty —
    because the response is identical: assume a distil is due and say so. A
    nudge is not worth distinguishing error cases for.
    """
    try:
        lessons = json.loads(ledger.read_text(encoding="utf-8"))["lessons"]
        return max(
            datetime.strptime(item["distilled_at"], "%Y-%m-%d").date()
            for item in lessons
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def nudge(today: date, last: date | None) -> str:
    """The line to print, or empty when nothing needs saying."""
    if last is None:
        return "No lesson distil on record. Run /distil-due to check for one."
    days = (today - last).days
    if days < DUE_AFTER_DAYS:
        return ""
    return (
        f"Last lesson distilled {days} days ago. "
        "Run /distil-due to check whether a new one is waiting."
    )


def main() -> int:
    line = nudge(date.today(), last_distilled(LEDGER))
    if line:
        print(line)  # noqa: T201 - a hook's output is its whole purpose
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
