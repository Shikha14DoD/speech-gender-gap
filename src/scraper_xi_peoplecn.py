"""
Scraper for China -- Xi Jinping, jhsjk.people.cn (People's Daily's
"Xi Jinping Series of Important Speeches Database").

Unlike the SCIO English site, this is a much larger, dedicated
database with proper filtering by content type and year, and a clean
JSON API for discovery (found via browser dev tools -- the site's own
UI is JavaScript-driven and doesn't expose filtered URLs directly).

IMPORTANT: this content is in CHINESE. Machine translation is applied
via translate_helper.py (same approach as Denmark), producing
title_en and full_text_en columns alongside the originals.
"""

import re
import json
import time
from typing import List, Optional

from src.utils import get, soupify, clean_text, Speech
from src.text_processing import parse_date_loose, in_date_range, classify_as_speech, classify_content_type

API_BASE = "https://jhsjk.people.cn/testnew/result"
ARTICLE_BASE = "https://jhsjk.people.cn/article/"


def parse_xi_peoplecn(leader_config: dict, start_date: str, end_date: str,
                       limit: Optional[int] = None) -> List[Speech]:
    print("== China (Xi Jinping, People's Daily database) ==")

    years = sorted({start_date[:4], end_date[:4], "2024", "2025", "2026"})
    year_param = ",".join(years)

    speeches: List[Speech] = []
    page = 1
    total_seen = 0

    while True:
        api_url = (
            f"{API_BASE}?keywords=&isFuzzy=0&searchArea=0"
            f"&year={year_param}&form=706&type=0&page={page}"
            f"&sortType=2&origin=all&source=2"
        )
        resp = get(api_url)
        if resp is None:
            break

        try:
            data = json.loads(resp.text)
        except json.JSONDecodeError:
            print(f"  [error] bad JSON response on page {page}")
            break

        items = data.get("list", [])
        total = data.get("total")
        if page == 1:
            print(f"  API reports {total} total matching entries")

        if not items:
            print(f"  [info] no more items on page {page}, stopping.")
            break

        for item in items:
            total_seen += 1
            article_id = item.get("article_id")
            if not article_id:
                continue

            # input_date looks like "2026-07-31 16:27:52" -- take date part.
            raw_date = item.get("input_date", "")
            date_iso = raw_date.split(" ")[0] if raw_date else None

            if date_iso and not in_date_range(date_iso, start_date, end_date):
                continue

            article = _fetch_article(article_id, leader_config, date_iso)
            if article is None:
                continue
            if article.likely_speech == "no":
                continue

            speeches.append(article)
            if limit and len(speeches) >= limit:
                return speeches

        print(f"  page {page}: {total_seen} entries checked so far, {len(speeches)} kept...")
        page += 1
        if page > 30:  # safety guard
            break

    return speeches


def _fetch_article(article_id: str, leader_config: dict, fallback_date: Optional[str]) -> Optional[Speech]:
    url = f"{ARTICLE_BASE}{article_id}"
    resp = get(url)
    if resp is None:
        return None
    soup = soupify(resp)

    title_tag = soup.find("h1")
    title = clean_text(title_tag.get_text(separator=" ")) if title_tag else url

    page_text = soup.get_text()
    date_iso = fallback_date
    date_match = re.search(r"发布时间[:：]\s*(\d{4}-\d{2}-\d{2})", page_text)
    if date_match:
        date_iso = date_match.group(1)

    # Body text: all paragraphs, excluding the copyright footer block.
    content_div = soup.find("article") or soup.find("main") or soup
    paragraphs = []
    for p in content_div.find_all("p"):
        text = clean_text(p.get_text(separator=" "))
        if not text or "版权所有" in text or "Copyright" in text:
            continue
        paragraphs.append(text)
    full_text = clean_text("\n\n".join(paragraphs))

    return Speech(
        country=leader_config["country"],
        leader=leader_config["leader"],
        role=leader_config["role"],
        date=date_iso,
        title=title,
        full_text=full_text,
        language="Chinese",
        source_url=url,
        likely_speech=classify_as_speech(title),
        content_type=classify_content_type(title),
        notes="Discovered via jhsjk.people.cn's JSON search API (site's "
              "own UI is JavaScript-driven; found the real API via "
              "browser dev tools). Filtered to 'type=0' (speech) "
              "category. Content is in Chinese -- requires machine "
              "translation (see translate_csv.py). A much larger, "
              "more comprehensive source than the English SCIO site.",
    )