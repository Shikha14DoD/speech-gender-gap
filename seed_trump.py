"""
Seeds trump.csv with manually-identified, verified real speech URLs
from the Jan 20 - May 23, 2025 window specifically -- the gap left by
the primary Senate Democrats source (which comprehensively covers
May 24, 2025 onward) and the now-largely-video-only official
whitehouse.gov site for this early period.

Sourced from Roll Call's Factbase (rollcall.com/factbase/trump/transcript/).
Uses Factbase's own page structure (speaker name in an <h2>, with the
real paragraph text living 4 DOM levels up from that heading) -- this
is DIFFERENT from the Senate Democrats site structure used in
scraper_trump.py, so this file has its own dedicated fetch function
rather than reusing that one.
"""

import os
import re
import pandas as pd

from src.config_loader import load_config, get_leader_config
from src.text_processing import parse_date_loose, in_date_range, classify_as_speech, classify_content_type
from src.utils import get, soupify, clean_text, Speech, write_csv

KNOWN_URLS = [
    "https://rollcall.com/factbase/trump/transcript/donald-trump-speech-political-rally-washington-january-19-2025/",
    "https://rollcall.com/factbase/trump/transcript/donald-trump-speech-before-inauguration-lunch-capitol-washington-january-20-2025/",
    "https://rollcall.com/factbase/trump/transcript/donald-trump-speech-house-gop-conference-miami-january-27-2025/",
    "https://rollcall.com/factbase/trump/transcript/donald-trump-speech-governors-white-house-february-21-2025/",
    "https://rollcall.com/factbase/trump/transcript/donald-trump-speech-department-of-justice-march-14-2025/",
    "https://rollcall.com/factbase/trump/transcript/donald-trump-speech-nrcc-republican-dinner-april-8-2025/",
    "https://rollcall.com/factbase/trump/transcript/donald-trump-remarks-cabinet-meeting-april-30-2025/",
]


def _fetch_factbase_article(url: str, leader_config: dict):
    """Fetch and extract a Factbase transcript page. Real paragraph text
    lives 4 DOM levels up from each speaker's <h2> heading -- see this
    project's diagnose_trump*.py investigation for how this was found."""
    resp = get(url)
    if resp is None:
        return None
    soup = soupify(resp)

    title_tag = soup.find("h1")
    title = clean_text(title_tag.get_text(separator=" ")) if title_tag else url

    date_iso = None
    date_match = re.search(
        r"\b(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
        title,
    )
    if date_match:
        date_iso = parse_date_loose(date_match.group(0))

    trump_paragraphs = []
    for h2 in soup.find_all("h2"):
        heading_text = h2.get_text(strip=True)
        if heading_text.lower() != "donald trump":
            continue

        block = h2
        for _ in range(4):
            if block.find_parent() is None:
                break
            block = block.find_parent()

        block_text = clean_text(block.get_text(separator=" "))
        block_text = re.sub(
            r"^Donald Trump\s+\d{2}:\d{2}:\d{2}-\d{2}:\d{2}:\d{2}\s*\([^)]*\)\s*"
            r"(No StressLens|StressLens[^A-Za-z]*)?\s*",
            "",
            block_text,
            flags=re.IGNORECASE,
        )
        block_text = re.sub(
            r"^(No\s+\w+|Positive|Negative|Neutral)\s*\([\d.]+\)\s*",
            "",
            block_text,
            flags=re.IGNORECASE,
        )
        if block_text and len(block_text) > 20:
            trump_paragraphs.append(block_text)

    full_text = clean_text("\n\n".join(trump_paragraphs))
    if not full_text or len(full_text) < 100:
        return None

    return Speech(
        country=leader_config["country"],
        leader=leader_config["leader"],
        role=leader_config["role"],
        date=date_iso,
        title=title,
        full_text=full_text,
        language="English",
        source_url=url,
        likely_speech=classify_as_speech(title),
        content_type=classify_content_type(title),
        notes="Manually seeded from Roll Call Factbase to fill the "
              "Jan 20 - May 23, 2025 gap left by the primary Senate "
              "Democrats source. Multi-speaker events filtered to ONLY "
              "his own paragraphs.",
    )


def main():
    config = load_config()
    leader_config = get_leader_config("trump", config)

    out_path = "data/processed/trump.csv"
    existing_df = pd.read_csv(out_path) if os.path.exists(out_path) else pd.DataFrame(columns=["source_url"])
    existing_urls = set(existing_df["source_url"]) if len(existing_df) else set()

    new_rows = []
    for url in KNOWN_URLS:
        if url in existing_urls:
            print(f"  already have: {url}")
            continue
        article = _fetch_factbase_article(url, leader_config)
        if article is None:
            print(f"  [skip] could not fetch or filter rejected it: {url}")
            continue
        if not in_date_range(article.date, "2025-01-01", "2025-05-23"):
            print(f"  [skip] outside target window ({article.date}): {url}")
            continue
        new_rows.append(article)
        print(f"  added: {article.title}")

    if new_rows:
        write_csv(new_rows, out_path)
    print(f"\nDone. Added {len(new_rows)} row(s).")


if __name__ == "__main__":
    main()