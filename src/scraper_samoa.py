"""
Scraper for Samoa -- Fiamē Naomi Mataʻafa (Prime Minister), mygov.gov.ws.

Standard WordPress category archive, clean /page/N/ pagination -- no
JavaScript rendering issues, no bot detection (unlike Denmark/Italy).

IMPORTANT: Fiamē left office 16 Sep 2025. The "PM Corner" category on
this site is shared with THREE officials over time: Fiamē herself, her
successor (a different, male PM, since 16 Sep 2025), and his Deputy PM
(a different woman). Results are filtered by BOTH a name marker in the
title AND a hard date cutoff at her last day in office -- do not relax
either check, since the Deputy PM being a woman doesn't make her the
right subject for this dataset.
"""

import re
from typing import List, Optional

from src.utils import get, soupify, clean_text, Speech
from src.text_processing import parse_date_loose, in_date_range, classify_as_speech, classify_content_type

BASE_LISTING = "https://mygov.gov.ws/category/pm-corner/"
PAGE_SIZE_SAFETY_LIMIT = 30  # site showed ~7 pages live; generous margin

FIAME_TENURE_END = "2025-09-16"
FIAME_NAME_MARKERS = ["fiame", "fiamē", "mataafa", "mata'afa", "mataʻafa"]

MONTH_DAY_YEAR_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+\d{1,2},?\s+\d{4}\b"
)


def parse_samoa(leader_config: dict, start_date: str, end_date: str,
                 limit: Optional[int] = None) -> List[Speech]:
    print("== Samoa ==")
    # Cap end_date at her actual last day in office, whichever is earlier.
    effective_end = min(end_date, FIAME_TENURE_END)

    speeches: List[Speech] = []
    page = 1

    while True:
        url = BASE_LISTING if page == 1 else f"{BASE_LISTING}page/{page}/"
        resp = get(url)
        if resp is None:
            break
        soup = soupify(resp)

        links = sorted(set(
            a["href"] for a in soup.find_all("a", href=True)
            if a["href"].startswith("https://mygov.gov.ws/")
            and a["href"].rstrip("/").count("/") >= 3
            and "/category/" not in a["href"]
            and "/author/" not in a["href"]
            and "/tag/" not in a["href"]
            and "/page/" not in a["href"]
            and "/wp-content/" not in a["href"]
            and "/directory/" not in a["href"]
            and "/services/" not in a["href"]
            and "/events/" not in a["href"]
            and "/login/" not in a["href"]
        ))

        if not links:
            print(f"  [info] no more articles on page {page}, stopping.")
            break

        print(f"  page {page}: checking {len(links)} candidate links...")
        stop_all = False
        for href in links:
            # Cheap pre-filter on URL slug before fetching the full page.
            if not any(marker in href.lower() for marker in FIAME_NAME_MARKERS):
                continue
            article = _fetch_article(href, leader_config)
            if article is None:
                continue
            if article.date and article.date > effective_end:
                continue  # published after she left office
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
        if page > PAGE_SIZE_SAFETY_LIMIT:
            break

    return speeches


def _fetch_article(url: str, leader_config: dict) -> Optional[Speech]:
    resp = get(url)
    if resp is None:
        return None
    soup = soupify(resp)

    title_tag = soup.find("h1") or soup.find("h3")
    title = clean_text(title_tag.get_text(separator=" ")) if title_tag else url

    if not any(marker in title.lower() for marker in FIAME_NAME_MARKERS):
        return None  # double-check at title level, not just URL slug

    # Article pages show "Post published: <date>" in "Month Day, Year"
    # format (e.g. "July 5, 2024") -- NOT "Day Month Year". Try a
    # <time datetime=...> tag first (most reliable), then fall back to
    # the visible text pattern.
    date_iso = None
    time_tag = soup.find("time")
    if time_tag and time_tag.get("datetime"):
        date_iso = time_tag["datetime"][:10]
    else:
        page_text = soup.get_text()
        pub_match = re.search(r"Post published:\s*" + MONTH_DAY_YEAR_RE.pattern, page_text)
        date_match = pub_match or MONTH_DAY_YEAR_RE.search(page_text)
        if date_match:
            date_iso = parse_date_loose(date_match.group(0).replace("Post published:", "").strip())

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
        language="English/Samoan (mixed -- check per article)",
        source_url=url,
        likely_speech=classify_as_speech(title),
        content_type=classify_content_type(title),
        notes="Category shared with successor PM (male) AND his Deputy PM "
              "(different woman) -- filtered by name marker in title/URL "
              "AND date cutoff (16 Sep 2025). Verify each row manually; "
              "some entries may be press releases ABOUT her rather than "
              "her own remarks (e.g. university announcements).",
    )