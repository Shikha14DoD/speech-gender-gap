"""
Scraper for China -- Xi Jinping (President), english.scio.gov.cn.

Uses the State Council Information Office's curated English "Speeches"
section under Xi's governance coverage. This is a clean, well-behaved
site: no JavaScript rendering, no bot detection encountered so far, and
individual article pages carry a clean, machine-readable date directly
in page metadata (meta-publishdate).

SCOPE NOTE: filtered to entries specifically framed as his PRESIDENTIAL
role ("President Xi" / "Chinese President Xi Jinping" in the title),
not his other titles (General Secretary of the CPC, Chairman of the
Central Military Commission) -- even though the source section covers
him broadly across all roles.
"""

import re
from typing import List, Optional

from src.utils import get, soupify, clean_text, Speech
from src.text_processing import parse_date_loose, in_date_range, classify_as_speech, classify_content_type

BASE_LISTING = "http://english.scio.gov.cn/featured/xigovernance/node_7253447"
MAX_PAGES = 30  # safety guard; site showed 5 pages live, generous margin


def parse_china(leader_config: dict, start_date: str, end_date: str,
                 limit: Optional[int] = None) -> List[Speech]:
    print("== China ==")
    speeches: List[Speech] = []
    page = 1

    while True:
        url = f"{BASE_LISTING}.htm" if page == 1 else f"{BASE_LISTING}_{page}.htm"
        resp = get(url)
        if resp is None:
            break
        soup = soupify(resp)

        links = sorted(set(
            a["href"] for a in soup.find_all("a", href=True)
            if "/topnews/" in a["href"] and "/content_" in a["href"]
        ))

        if not links:
            print(f"  [info] no more articles on page {page}, stopping.")
            break

        print(f"  page {page}: checking {len(links)} candidate links...")
        for href in links:
            full_url = href if href.startswith("http") else f"http://english.scio.gov.cn{href}"
            article = _fetch_article(full_url, leader_config)
            if article is None:
                continue
            if article.likely_speech == "no":
                continue
            if in_date_range(article.date, start_date, end_date):
                speeches.append(article)
            if limit and len(speeches) >= limit:
                return speeches

        page += 1
        if page > MAX_PAGES:
            break

    return speeches


def _fetch_article(url: str, leader_config: dict) -> Optional[Speech]:
    resp = get(url)
    if resp is None:
        return None
    soup = soupify(resp)

    # Prefer the clean og:title meta tag; fall back to <title> tag.
    title = None
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = clean_text(og_title["content"])
    if not title:
        title_tag = soup.find("title")
        title = clean_text(title_tag.get_text(separator=" ")) if title_tag else url
        title = re.sub(r"\s*\|\s*english\.scio\.gov\.cn\s*$", "", title)

    # Require his PRESIDENTIAL title specifically in the title text --
    # excludes content framed only under his Party/military titles.
    is_president = bool(re.search(r"\bpresident\b", title, re.IGNORECASE)) and \
                   "xi" in title.lower()
    if not is_president:
        return None

    # Best source: meta-publishdate (clean ISO date in page metadata).
    date_iso = None
    date_meta = soup.find("meta", attrs={"name": "publishdate"})
    if date_meta and date_meta.get("content"):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", date_meta["content"])
        if m:
            date_iso = m.group(1)

    if date_iso is None:
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
        notes="Scraped from english.scio.gov.cn's curated 'Speeches' "
              "section. Filtered to entries specifically framed under "
              "his PRESIDENTIAL title (not General Secretary / CMC "
              "Chairman roles), per project scope. Official English "
              "translation direct from source -- no machine "
              "translation needed. Site attributes many entries to "
              "Xinhua (state news agency) as publisher/distributor, "
              "not necessarily Xi's own office -- worth noting as a "
              "source-type difference from the other four countries.",
    )