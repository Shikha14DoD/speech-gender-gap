"""
Scraper for the Bahamas (Prime Minister Philip Davis).

Source: opm.gov.bs (Office of the Prime Minister), a standard WordPress site.
We use WordPress's own public REST API (/wp-json/wp/v2/posts), which returns
each post's full rendered text as JSON -- no HTML scraping of listing pages.

Categories used:
  4  = "speeches"    (remarks, keynote addresses, national addresses)
  21 = "statements"  (formal statements; some are unsigned government notices,
                      so we keep only those that name the Prime Minister)

Native English, single speaker, no bot detection -- plain `requests` works.
"""

import html
import re
import time
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from src.utils import clean_text, Speech
from src.text_processing import in_date_range, classify_as_speech, classify_content_type

API = "https://opm.gov.bs/wp-json/wp/v2/posts"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
CATEGORIES = "4,21"
PAGE_SIZE = 50


def _get(params: dict, max_retries: int = 3, delay_seconds: float = 1.5):
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(API, headers=HEADERS, params=params, timeout=30)
            time.sleep(delay_seconds)
            if resp.status_code == 200:
                return resp
            print(f"  [warn] status {resp.status_code} (attempt {attempt})")
        except Exception as e:
            print(f"  [warn] request raised {e!r} (attempt {attempt})")
        time.sleep(delay_seconds * attempt)
    print("  [error] giving up on this page")
    return None


def _is_pm_item(title: str) -> bool:
    t = title.lower()
    # speeches by the Deputy / Acting PM (Chester Cooper) sit in the same
    # categories -- they are not Davis's own words
    if ("acting prime minister" in t or "deputy prime minister" in t) and "davis" not in t:
        return False
    # "Prime Minister Davis to Attend ..." are one-paragraph travel advisories
    if re.search(r"\bto attend\b", t):
        return False
    return "davis" in t or "prime minister" in t


def parse_bahamas(leader_config: dict, start_date: str, end_date: str,
                  limit: Optional[int] = None) -> List[Speech]:
    print("== Bahamas (Davis) ==")
    speeches: List[Speech] = []
    page = 1
    while True:
        resp = _get({
            "categories": CATEGORIES,
            "per_page": PAGE_SIZE,
            "page": page,
            "after": f"{start_date}T00:00:00",
            "before": f"{end_date}T23:59:59",
            "orderby": "date",
            "order": "desc",
        })
        if resp is None:
            break
        posts = resp.json()
        if not posts:
            break
        total_pages = int(resp.headers.get("X-WP-TotalPages", page))
        print(f"  page {page}/{total_pages}: {len(posts)} posts")

        for p in posts:
            title = clean_text(html.unescape(BeautifulSoup(p["title"]["rendered"], "html.parser").get_text()))
            if not _is_pm_item(title):
                continue
            body = BeautifulSoup(p["content"]["rendered"], "html.parser")
            paragraphs = [clean_text(x.get_text(separator=" ")) for x in body.find_all(["p", "li"])]
            full_text = clean_text("\n\n".join(x for x in paragraphs if x))
            if len(full_text) < 80:
                continue
            date_iso = p["date"][:10]
            if not in_date_range(date_iso, start_date, end_date):
                continue
            speeches.append(Speech(
                country=leader_config["country"],
                leader=leader_config["leader"],
                role=leader_config["role"],
                date=date_iso,
                title=title,
                full_text=full_text,
                language="English",
                source_url=p["link"],
                likely_speech=classify_as_speech(title),
                content_type=classify_content_type(title),
                notes="Sourced from opm.gov.bs (Office of the Prime Minister) via the "
                      "WordPress REST API, categories 'speeches' and 'statements'. "
                      "Native English, single speaker. Date is the site's publication "
                      "date, which can trail the delivery date by a day or more.",
            ))
            if limit and len(speeches) >= limit:
                return speeches

        if page >= total_pages:
            break
        page += 1
    return speeches
