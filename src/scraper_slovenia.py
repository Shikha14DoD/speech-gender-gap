"""
Scraper for Slovenia (President Nataša Pirc Musar).

Source: predsednica-slo.si dedicated "Govori" (Speeches) category,
NOT the general news feed used previously. Found (Aug 2026) after
Ginette flagged the old source as a news feed rather than a speech
archive.

No bot detection encountered -- plain `requests` works.
Single-speaker (her own remarks) -- no multi-speaker filtering needed.
Content is in Slovenian -- translation required (see translate_csv.py).
"""

import re
import time
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from src.utils import clean_text, Speech
from src.text_processing import in_date_range, classify_as_speech, classify_content_type

BASE_LISTING = "https://www.predsednica-slo.si/sl/objave/govori"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

EXCLUDE_PATHS = {
    "/sl/objave", "/sl/objave/vse", "/sl/objave/govori",
    "/sl/objave/aktivnosti-v-sloveniji", "/sl/objave/mednarodne-aktivnosti",
    "/sl/objave/poslanice", "/sl/objave/moc-dejstev", "/sl/objave/rss",
}


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


def parse_slovenia(leader_config: dict, start_date: str, end_date: str,
                    limit: Optional[int] = None) -> List[Speech]:
    print("== Slovenia (Pirc Musar) ==")
    speeches: List[Speech] = []
    start_param = 0

    while True:
        url = BASE_LISTING if start_param == 0 else f"{BASE_LISTING}?start={start_param}"
        html = _get(url)
        if html is None:
            break
        soup = BeautifulSoup(html, "html.parser")

        list_container = soup.find("ul", class_="news-list")
        items = list_container.find_all("li") if list_container else []

        candidates = []
        for li in items:
            a_tag = li.find("a", href=True)
            time_tag = li.find("time", attrs={"datetime": True})
            if not a_tag or not time_tag:
                continue
            candidates.append((a_tag["href"], time_tag["datetime"]))

        if not candidates:
            print(f"  [info] no more articles at start={start_param}, stopping.")
            break

        if start_param % 80 == 0:
            print(f"  start={start_param}: checking {len(candidates)} candidate links...")

        stop_all = False
        for href, listing_date in candidates:
            full_url = href if href.startswith("http") else f"https://www.predsednica-slo.si{href}"
            if listing_date < start_date:
                stop_all = True
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

        start_param += 16  # site paginates in increments of 16
        if start_param > 2000:  # safety cap
            break

    return speeches


def _fetch_article(url: str, leader_config: dict, listing_date: Optional[str] = None) -> Optional[Speech]:
    html = _get(url)
    if html is None:
        return None
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("h1")
    title = clean_text(title_tag.get_text(separator=" ")) if title_tag else url

    date_iso = listing_date
    time_tag = soup.find("time", attrs={"datetime": True})
    if time_tag and time_tag.get("datetime"):
        date_iso = time_tag["datetime"][:10]
    if not date_iso:
        return None

    content_div = soup.find("div", class_="typography")
    if content_div is None:
        return None

    paragraphs = []
    for p in content_div.find_all("p"):
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
        date=date_iso,
        title=title,
        full_text=full_text,
        language="Slovenian",
        source_url=url,
        likely_speech=classify_as_speech(title),
        content_type=classify_content_type(title),
        notes="Sourced from predsednica-slo.si dedicated 'Govori' "
              "(Speeches) category, replacing the earlier general "
              "news-feed source flagged by Ginette as not a real "
              "speech archive. Single-speaker (her own remarks), no "
              "multi-speaker filtering needed. NOT YET independently "
              "validated as of Aug 2026 -- spot-check before trusting.",
    )