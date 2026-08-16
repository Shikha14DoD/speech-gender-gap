"""
Scraper for Moldova (President Maia Sandu).

Source: presedinte.md official "Speeches and Messages" archive,
English section (already in English -- no translation step needed).

No bot detection on this site -- plain `requests` works fine.
Single-speaker content (her own curated speeches), so no speaker-label
filtering needed, unlike Mexico/Trump's multi-speaker press conference
transcripts.

Structure confirmed via manual HTML inspection (Aug 2026):
  - Listing: <article class="block"><time datetime="YYYY-MM-DD">...
    </time><a href="..."><h2>title</h2>...</a></article>
  - Article body: <p> tags with parent class "article-type"
"""

import re
import time
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from src.utils import clean_text, Speech
from src.text_processing import in_date_range, classify_as_speech, classify_content_type

BASE_LISTING = "https://presedinte.md/eng/discursuri"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
MAX_PAGES = 50


def _get(url: str, max_retries: int = 3, delay_seconds: float = 1.5) -> Optional[str]:
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            time.sleep(delay_seconds)
            if resp.status_code == 200:
                return resp.text
            print(f"  [warn] {url} returned status {resp.status_code} (attempt {attempt})")
        except Exception as e:
            print(f"  [warn] {url} raised {e!r} (attempt {attempt})")
    print(f"  [error] giving up on {url}")
    return None


def parse_moldova(leader_config: dict, start_date: str, end_date: str,
                   limit: Optional[int] = None) -> List[Speech]:
    print("== Moldova (Sandu) ==")
    speeches: List[Speech] = []
    page = 1

    while True:
        url = BASE_LISTING if page == 1 else f"{BASE_LISTING}/index/page:{page}"
        html = _get(url)
        if html is None:
            break
        soup = BeautifulSoup(html, "html.parser")

        candidates = []
        for art in soup.find_all("article", class_="block"):
            time_tag = art.find("time", attrs={"datetime": True})
            a_tag = art.find("a", href=True)
            if not time_tag or not a_tag:
                continue
            date_iso = time_tag["datetime"].strip()[:10]
            candidates.append((a_tag["href"], date_iso))

        if not candidates:
            print(f"  [info] no more articles on page {page}, stopping.")
            break

        if page % 5 == 0 or page == 1:
            print(f"  page {page}: checking {len(candidates)} candidate links...")

        stop_all = False
        for href, listing_date in candidates:
            full_url = href if href.startswith("http") else f"https://presedinte.md{href}"
            if listing_date < start_date:
                stop_all = True  # reverse-chronological; nothing older matters
                break
            if listing_date > end_date:
                continue
            article = _fetch_article(full_url, leader_config, listing_date)
            if article is None:
                continue
            if in_date_range(article.date, start_date, end_date):
                speeches.append(article)
            if limit and len(speeches) >= limit:
                stop_all = True
                break

        if stop_all:
            break

        page += 1
        if page > MAX_PAGES:
            break

    return speeches


def _fetch_article(url: str, leader_config: dict, listing_date: str) -> Optional[Speech]:
    html = _get(url)
    if html is None:
        return None
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("h1")
    title = clean_text(title_tag.get_text(separator=" ")) if title_tag else url

    paragraphs = []
    for p in soup.find_all("p"):
        if p.find_parent(class_="article-type") is not None:
            text = clean_text(p.get_text(separator=" "))
            if text:
                paragraphs.append(text)

    full_text = clean_text("\n\n".join(paragraphs))
    if not full_text or len(full_text) < 50:
        return None

    return Speech(
        country=leader_config["country"],
        leader=leader_config["leader"],
        role=leader_config["role"],
        date=listing_date,
        title=title,
        full_text=full_text,
        language="English",
        source_url=url,
        likely_speech=classify_as_speech(title),
        content_type=classify_content_type(title),
        notes="Sourced from presedinte.md official 'Speeches and "
              "Messages' archive, English section (native English "
              "content, no translation needed). Single-speaker curated "
              "speeches -- no multi-speaker filtering required, unlike "
              "Mexico/Trump/Biden sources. No bot detection encountered.",
    )