"""
Translates scraped speech text to English using Google Translate
(via the free deep-translator library).

Google's free translation endpoint has a per-request character limit
(~5000 characters), and our full speeches are often much longer than
that -- so this module splits long text into paragraph-based chunks
that stay under the limit, translates each chunk separately, then
rejoins them back into one continuous English text.
"""

import time
from typing import Optional

from deep_translator import GoogleTranslator

CHUNK_CHAR_LIMIT = 4500  # stay safely under Google's ~5000 char limit
TRANSLATE_DELAY_SECONDS = 1.0  # be polite to the free translation endpoint


def _chunk_text(text: str, limit: int = CHUNK_CHAR_LIMIT) -> list:
    """Split text into chunks under `limit` characters, breaking on
    paragraph boundaries (double newlines) so we don't cut a sentence
    in half mid-translation."""
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""

    for para in paragraphs:
        # +2 accounts for the "\n\n" we'll rejoin with
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
    source_language should be a short code deep-translator understands,
    e.g. 'da' (Danish), 'it' (Italian), 'sl' (Slovenian), 'sm' (Samoan).
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
        try:
            translated = translator.translate(chunk)
            translated_chunks.append(translated or "")
        except Exception as e:
            print(f"  [warn] translation failed on chunk {i+1}/{len(chunks)}: {e}")
            translated_chunks.append(f"[TRANSLATION FAILED FOR THIS SECTION: {e}]")
        time.sleep(TRANSLATE_DELAY_SECONDS)

    return "\n\n".join(translated_chunks)