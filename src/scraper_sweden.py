"""
Scraper for Sweden (Prime Minister Ulf Kristersson), 2024-2026.

Source: regeringen.se/tal -- the Government Offices' official speech archive,
in Swedish.  The site's own filter page loads its results from a small JSON
endpoint, /Filter/GetFilteredItems?lang=sv, which returns
{"TotalCount": n, "Message": "<ul>...html...</ul>"}.  We ask it for speeches
(category 1338) tagged with Kristersson's person id (2605) from the start date
and page through the results, then fetch each speech page for its full text.

Swedish original; translation to English happens in a later pipeline step.
The excerpt line under each title ("Sergels torg, Stockholm, den 24 augusti
2026. Det talade ordet gäller.") gives the delivery place and date, which we
keep in `notes`.
"""

import html
import re
import time
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from src.utils import clean_text, Speech
from src.text_processing import in_date_range, classify_as_speech, classify_content_type

BASE = "https://www.regeringen.se"
LIST_URL = BASE + "/Filter/GetFilteredItems"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
SPEECH_CATEGORY = 1338
PERSON_ID = 2605          # Ulf Kristersson
PAGE_SIZE = 10
DELAY = 3.0


def _get(url: str, params: Optional[dict] = None, max_retries: int = 3):
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=40)
            time.sleep(DELAY)
            if resp.status_code == 200:
                return resp
            print(f"  [warn] {url} status {resp.status_code} (attempt {attempt})")
        except Exception as e:
            print(f"  [warn] {url} raised {e!r} (attempt {attempt})")
        time.sleep(DELAY * attempt * 3)
    print(f"  [error] giving up on {url}")
    return None


def _discover(start_date: str, end_date: str) -> List[dict]:
    items, page = [], 1
    while True:
        resp = _get(LIST_URL, {
            "lang": "sv", "filterType": "Taxonomy", "filterByType": "FilterablePageBase",
            "rootPageReference": 0, "pageSize": PAGE_SIZE, "preFilteredCategories": SPEECH_CATEGORY,
            "page": page, "fromDate": start_date, "toDate": end_date,
            "filteredPublisherCategories": PERSON_ID,
        })
        if resp is None:
            break
        data = resp.json()
        total = data.get("TotalCount", 0)
        soup = BeautifulSoup(data.get("Message", ""), "html.parser")
        rows = soup.select("div.sortcompact")
        if not rows:
            break
        for r in rows:
            a = r.find("a", href=True)
            t = r.find("time", attrs={"datetime": True})
            ex = r.select_one("p.sortextended__excerpt")
            if not a or not t:
                continue
            items.append({
                "url": BASE + a["href"],
                "title": clean_text(a.get_text(separator=" ")),
                "date": t["datetime"][:10],
                "excerpt": clean_text(ex.get_text(separator=" ")) if ex else "",
            })
        print(f"  list page {page}: {len(rows)} items (total {total})")
        if page * PAGE_SIZE >= total:
            break
        page += 1
    return items


def parse_sweden(leader_config: dict, start_date: str, end_date: str,
                 limit: Optional[int] = None) -> List[Speech]:
    print("== Sweden (Kristersson) ==")
    items = _discover(start_date, end_date)
    speeches: List[Speech] = []
    for it in items:
        resp = _get(it["url"])
        if resp is None:
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        body = soup.select_one("div.has-wordExplanation")
        if body is None:
            continue
        paragraphs = [clean_text(p.get_text(separator=" ")) for p in body.find_all(["p", "li", "h2", "h3"])]
        full_text = clean_text("\n\n".join(p for p in paragraphs if p))
        if len(full_text) < 150 or not in_date_range(it["date"], start_date, end_date):
            continue
        h1 = soup.find("h1")
        title = clean_text(h1.get_text(separator=" ")) if h1 else it["title"]
        notes = ("Sourced from regeringen.se/tal (Government Offices of Sweden), Swedish original. "
                 "Single speaker (person tag: Ulf Kristersson). Date is the site's publication date.")
        if it["excerpt"]:
            notes += f" Delivery line from the site: \"{it['excerpt']}\""
        speeches.append(Speech(
            country=leader_config["country"],
            leader=leader_config["leader"],
            role=leader_config["role"],
            date=it["date"],
            title=title,
            full_text=full_text,
            language="Swedish",
            source_url=it["url"],
            likely_speech=classify_as_speech(title),
            content_type=classify_content_type(title),
            notes=notes,
        ))
        if limit and len(speeches) >= limit:
            break
    return speeches
