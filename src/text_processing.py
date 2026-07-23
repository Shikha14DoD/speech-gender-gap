"""
Date parsing and speech-classification helpers.

Every government site formats dates differently (e.g. Denmark uses
5/14/2024, Italy uses "23 September 2023", Samoa uses "July 5, 2024").
This module normalizes all of them into one consistent format (ISO
YYYY-MM-DD), and provides a rough heuristic for flagging whether a
scraped item is actually a speech vs. routine news (credentials
ceremonies, condolence messages, etc.) -- several of our source sites
mix both into the same feed.
"""

import datetime as dt
import re
from typing import Optional


def parse_date_loose(text: str) -> Optional[str]:
    """Try a handful of common date formats and return ISO YYYY-MM-DD, else None."""
    text = text.strip()
    formats = [
        "%m/%d/%Y",       # Denmark: 5/14/2024
        "%d.%m.%Y",
        "%d %B %Y",       # Italy: 23 September 2023
        "%B %d, %Y",      # Samoa: July 5, 2024
        "%d-%m-%Y",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return dt.datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue

    # Slovenia-style "24. 3. 2026"
    m = re.match(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", text)
    if m:
        d, mo, y = map(int, m.groups())
        try:
            return dt.date(y, mo, d).isoformat()
        except ValueError:
            pass

    return None


def in_date_range(iso_date: Optional[str], start: str, end: str) -> bool:
    """If date couldn't be parsed, default to KEEPING it (flagged, not dropped) --
    better to manually review an unparsed date than silently lose a real speech."""
    if not iso_date:
        return True
    return start <= iso_date <= end


SPEECH_KEYWORDS = [
    "speech", "address", "remarks", "statement", "keynote", "opening address",
    "new year", "message", "intervention", "declaration", "podcast",
]
NON_SPEECH_KEYWORDS = [
    "credentials", "condolence", "meets", "meeting with", "visit to", "visits",
    "hosts", "bilateral meeting", "photo", "appoint", "welcomes", "receives",
]


def classify_as_speech(title: str) -> str:
    """
    Heuristic only -- ALWAYS spot-check, never trust blindly. Several of our
    source feeds (e.g. Slovenia, Samoa) mix real speeches with routine news.
    Returns 'yes', 'maybe', or 'no'.
    """
    t = title.lower()
    has_speech_kw = any(k in t for k in SPEECH_KEYWORDS)
    has_non_speech_kw = any(k in t for k in NON_SPEECH_KEYWORDS)
    if has_speech_kw and not has_non_speech_kw:
        return "yes"
    if has_non_speech_kw and not has_speech_kw:
        return "no"
    return "maybe"