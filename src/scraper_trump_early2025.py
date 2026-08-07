"""
Supplementary scraper for USA -- Donald Trump, covering ONLY 20 Jan 2025
to ~23 May 2025 -- the window during which whitehouse.gov still posted
real text transcripts before removing them in late May 2025 (confirmed
via news reporting). This fills the gap left by the primary
Senate Democrats source, whose archive only starts around when that
transcript removal happened.

Real URL pattern confirmed via direct inspection:
whitehouse.gov/remarks/YYYY/MM/[slug]
Pagination: whitehouse.gov/remarks/page/N (NOT the ?query-10-page=N
parameter incorrectly assumed in an earlier version of this project's
Trump scraper).
"""

import re
from typing import List, Optional

from src.utils import get, soupify, clean_text, Speech
from src.text_processing import parse_date_loose, in_date_range, classify_as_speech, classify_content_type

BASE_LISTING = "https://www.whitehouse.gov/remarks/"
WINDOW_END = "2025-05-23"  # last date this window covers; primary source
                            # scraper handles everything after this
MAX_PAGES = 20


def parse_trump_early2025(leader_config: dict, start_date: str, end_date: str,
                           limit: Optional[int] = None) -> List[Speech]:
    print("== USA (Trump, early 2025 official transcripts) ==")
    effective_end = min(end_date, WINDOW_END)

    speeches: List[Speech] = []
    page = 1

    while True:
        url = BASE_LISTING if page == 1 else f"{BASE_LISTING}page/{page}"
        resp = get(url)
        if resp is None:
            break
        soup = soupify(resp)

        entries = []
        for h2 in soup.find_all("h2"):
            a = h2.find("a", href=True)
            if not a:
                continue
            if "/remarks/" not in a["href"]:
                continue
            entries.append(a["href"])

        if not entries:
            print(f"  [info] no more articles on page {page}, stopping.")
            break

        print(f"  page {page}: checking {len(entries)} candidate links...")
        print(f"  DEBUG entries found: {entries}")

        stop_all = False
        for href in entries:
            full_url = href if href.startswith("http") else f"https://www.whitehouse.gov{href}"
            article = _fetch_article(full_url, leader_config)
            if article is None:
                continue
            if article.date and article.date < start_date:
                stop_all = True  # reverse-chronological; nothing older matters
                break
            if article.likely_speech == "no":
                continue
            if in_date_range(article.date, start_date, effective_end):
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


def _fetch_article(url: str, leader_config: dict) -> Optional[Speech]:
    resp = get(url)
    if resp is None:
        return None
    soup = soupify(resp)

    title_tag = soup.find("h1")
    title = clean_text(title_tag.get_text(separator=" ")) if title_tag else url

    if "trump" not in title.lower():
        return None
    if "vance" in title.lower() and "trump" not in title.lower():
        return None

    date_iso = None
    page_text = soup.get_text()
    date_match = re.search(
        r"\b(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
        page_text,
    )
    if date_match:
        date_iso = parse_date_loose(date_match.group(0))

    content_div = soup.find("article") or soup.find("main") or soup
    paragraphs = [clean_text(p.get_text(separator=" ")) for p in content_div.find_all("p")]
    full_text = clean_text("\n\n".join(p for p in paragraphs if p))

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
        notes="Official whitehouse.gov transcript -- covers ONLY the "
              "window before the site removed text transcripts in late "
              "May 2025. Genuine primary-source government transcript, "
              "unlike the primary Trump dataset (which is sourced from "
              "a Senate Democrats archive republishing Factbase).",
    )