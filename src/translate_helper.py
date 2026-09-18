"""
Translates scraped speech text to English using Google Translate
(via the free deep-translator library).

Google's free translation endpoint has a per-request character limit
(~5000 characters), and our full speeches are often much longer than
that -- so this module splits long text into paragraph-based chunks
that stay under the limit, translates each chunk separately, then
rejoins them back into one continuous English text.

FIXES (after widespread failures on China's People's Daily dataset,
where many documents are extremely long, dense compilations with
single paragraphs longer than the chunk limit):
- _chunk_text now hard-splits any individual paragraph that's still
  too long on its own, instead of only splitting between paragraphs.
- translate_to_english now retries each chunk with backoff before
  giving up, since repeated failures turned out to be rate-limiting
  on Google's free endpoint under heavy volume, not permanent errors.
- Delay between requests increased.
"""

import os
import time
from typing import Optional

from deep_translator import GoogleTranslator, MyMemoryTranslator

# Default 800 (tuned for dense Chinese, where Google's free endpoint
# fails intermittently at any size -- see note below). For languages
# that translate cleanly at larger sizes (e.g. Spanish), set
# TRANSLATE_CHUNK_LIMIT in the environment to go several times faster.
CHUNK_CHAR_LIMIT = int(os.environ.get("TRANSLATE_CHUNK_LIMIT", "800"))
_CHUNK_DEFAULT = 800  # keep chunks modest, but the real fix is below --
                        # the free Google Translate endpoint fails
                        # intermittently regardless of size (confirmed via
                        # testing: 700/800/1000 succeeded, 900/1100 failed
                        # on the SAME document, no consistent threshold) --
                        # this is transient service flakiness, not a size
                        # problem, so aggressive retries matter more than
                        # chunk size tuning.
TRANSLATE_DELAY_SECONDS = 3
MAX_RETRIES = 6
RETRY_BACKOFF_SECONDS = 8


def _hard_split(text: str, limit: int) -> list:
    """Split a single oversized block of text into limit-sized pieces,
    preferring to break on sentence-ending punctuation where possible."""
    if len(text) <= limit:
        return [text]

    pieces = []
    remaining = text
    while len(remaining) > limit:
        # Try to break at the last sentence-ending punctuation before
        # the limit, so we don't cut mid-sentence when avoidable.
        window = remaining[:limit]
        break_point = max(
            window.rfind("。"), window.rfind("！"), window.rfind("？"),
            window.rfind(". "), window.rfind("! "), window.rfind("? "),
        )
        if break_point <= 0:
            break_point = limit  # no good break point found, hard cut
        else:
            break_point += 1  # include the punctuation itself
        pieces.append(remaining[:break_point])
        remaining = remaining[break_point:]
    if remaining:
        pieces.append(remaining)
    return pieces


def _chunk_text(text: str, limit: int = CHUNK_CHAR_LIMIT) -> list:
    """Split text into chunks under `limit` characters. Splits on
    paragraph boundaries (double newlines) first; any individual
    paragraph still over the limit gets hard-split further."""
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""

    for para in paragraphs:
        # If a single paragraph alone exceeds the limit, hard-split it
        # into its own pieces first.
        if len(para) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_hard_split(para, limit))
            continue

        if len(current) + len(para) + 2 > limit and current:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para

    if current:
        chunks.append(current)

    return chunks


def translate_to_english(text: str, source_language: str) -> Optional[str]:
    """
    Translate `text` from `source_language` to English.
    Returns None if translation fails entirely.
    """
    if not text or not text.strip():
        return ""

    try:
        translator = GoogleTranslator(source=source_language, target="en")
    except Exception as e:
        print(f"  [error] could not initialize translator: {e}")
        return None

    chunks = _chunk_text(text)
    translated_chunks = []

    for i, chunk in enumerate(chunks):
        translated = None
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                translated = translator.translate(chunk)
                break
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF_SECONDS * attempt)

        # Google's free endpoint failed every retry -- try a completely
        # different translation service as a fallback before giving up.
        # MyMemory's free API hard-caps requests at 500 chars, which our
        # chunk limit (tuned for Google) can exceed -- re-split for it.
        if translated is None:
            try:
                MYMEMORY_SOURCE_MAP = {
                "es": "es-ES", "da": "da-DK", "sl": "sl-SI", "it": "it-IT", "sm": "sm-WS",
                "zh-CN": "zh-CN", "zh": "zh-CN", "si": "si-LK", "ta": "ta-LK", "de": "de-DE",
                "sw": "sw-KE", "pt": "pt-BR",}
                mymemory_source = MYMEMORY_SOURCE_MAP.get(source_language, source_language)
                fallback = MyMemoryTranslator(source=mymemory_source, target="en-GB")
                sub_pieces = _hard_split(chunk, 490)
                sub_translated = [fallback.translate(p) for p in sub_pieces]
                translated = " ".join(t for t in sub_translated if t)
                print(f"  [info] chunk {i+1}/{len(chunks)} recovered via fallback translator"
                      + (f" ({len(sub_pieces)} sub-pieces)" if len(sub_pieces) > 1 else ""))
            except Exception as e2:
                last_error = e2

        if translated is not None:
            translated_chunks.append(translated)
        else:
            print(f"  [warn] translation failed on chunk {i+1}/{len(chunks)} after {MAX_RETRIES} attempts + fallback: {last_error}")
            translated_chunks.append(f"[TRANSLATION FAILED FOR THIS SECTION: {last_error}]")

        time.sleep(TRANSLATE_DELAY_SECONDS)

    return "\n\n".join(translated_chunks)