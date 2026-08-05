"""
Scraper for USA -- Joe Biden (President, through 20 Jan 2025),
bidenwhitehouse.archives.gov.

This is a frozen, archived site (no longer updated) covering his full
term. Plain server-rendered HTML, clean /page/N/ pagination -- no
JavaScript rendering or bot-detection issues.

IMPORTANT: the "Speeches and Remarks" feed mixes multiple speakers --
the President, Vice President, First Lady, and staff all post here.
Filtered to entries specifically attributed to "President Biden" in
the title.
"""

import re
from typing import List, Optional

from src.utils import get, soupify, clean_text, Speech
from src.text_processing import parse_date_loose, in_date_range, classify_as_speech, classify_content_type

BASE_LISTING = "https://bidenwhitehouse.archives.gov/briefing-room/speeches-remarks/"
BIDEN_TENURE_END = "2025-01-20"
MAX_PAGES = 300  # site showed 275 pages live; safety margin


def parse_biden(leader_config: dict, start_date: str, end_date: str,
                 limit: Optional[int] = None) -> List[Speech]:
    print("== USA (Biden) ==")
    effective_end = min(end_date, BIDEN_TENURE_END)

    speeches: List[Speech] = []
    page = 1

    while True:
        url = BASE_LISTING if page == 1 else f"{BASE_LISTING}page/{page}/"
        resp = get(url)
        if resp is None:
            break
        soup = soupify(resp)

        entries = []
        for h2 in soup.find_all("h2"):
            a = h2.find("a", href=True)
            if not a:
                continue
            if "/briefing-room/speeches-remarks/" not in a["href"]:
                continue
            if a["href"].rstrip("/") == BASE_LISTING.rstrip("/"):
                continue
            entries.append(a["href"])

        if not entries:
            print(f"  [info] no more articles on page {page}, stopping.")
            break

        if page % 10 == 0 or page == 1:
            print(f"  page {page}: checking {len(entries)} candidate links...")

        stop_all = False
        for href in entries:
            article = _fetch_article(href, leader_config)
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

    if "president biden" not in title.lower() and "biden" not in title.lower():
        return None
    if "jill biden" in title.lower() and "president biden" not in title.lower():
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
        notes="Frozen archived site (bidenwhitehouse.archives.gov), no "
              "longer updated. Feed shared with VP, First Lady, and "
              "staff -- filtered to entries attributed to President "
              "Biden specifically. Tenure ends 20 Jan 2025.",
    )