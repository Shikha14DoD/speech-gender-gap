"""
Scraper for USA -- Donald Trump (President, 2nd term, from 20 Jan 2025),
democrats.senate.gov/newsroom/trump-transcripts.

BACKGROUND: the official whitehouse.gov site removed text transcripts
in late May 2025 (confirmed via news reporting), keeping only video/audio
going forward. Roll Call's Factbase maintains transcripts, but its own
search interface is JavaScript-rendered with no discoverable API, and
Wayback Machine discovery for that domain proved unreliable (crawl-date
mismatch, many broken/renamed archived URLs).

This site -- a Senate Democratic Caucus initiative specifically created
to preserve public access after the transcript removal -- republishes
the same Factbase transcripts, but through a fully server-rendered,
cleanly-paginated site (27+ pages, no JavaScript rendering needed).
Confirmed via direct inspection to be far more reliable than either of
the other two sources.

IMPORTANT: events can have multiple speakers (other officials,
interviewers). Extract ONLY paragraphs attributed to "President Trump"
or "Trump" specifically.
"""

import re
from typing import List, Optional

from src.utils import get, soupify, clean_text, Speech
from src.text_processing import classify_as_speech, classify_content_type, in_date_range

BASE_LISTING = "https://www.democrats.senate.gov/newsroom/trump-transcripts"
MAX_PAGES = 30  # site showed 27 pages live; safety margin


def parse_trump(leader_config: dict, start_date: str, end_date: str,
                 limit: Optional[int] = None) -> List[Speech]:
    print("== USA (Trump) ==")
    speeches: List[Speech] = []
    page = 1

    while True:
        url = BASE_LISTING if page == 1 else f"{BASE_LISTING}?pagenum_rs={page}"
        resp = get(url)
        if resp is None:
            break
        soup = soupify(resp)

        links = sorted(set(
            a["href"] for a in soup.find_all("a", href=True)
            if "/newsroom/trump-transcripts/" in a["href"]
            and a["href"].rstrip("/") != BASE_LISTING.rstrip("/")
        ))

        if not links:
            print(f"  [info] no more articles on page {page}, stopping.")
            break

        if page % 5 == 0 or page == 1:
            print(f"  page {page}: checking {len(links)} candidate links...")

        stop_all = False
        for href in links:
            full_url = href if href.startswith("http") else f"https://www.democrats.senate.gov{href}"
            article = _fetch_article(full_url, leader_config)
            if article is None:
                continue
            if article.date and article.date < start_date:
                stop_all = True  # reverse-chronological; nothing older matters
                break
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


def _fetch_article(url: str, leader_config: dict) -> Optional[Speech]:
    resp = get(url)
    if resp is None:
        return None
    soup = soupify(resp)

    title_tag = soup.find("h1")
    title = clean_text(title_tag.get_text(separator=" ")) if title_tag else url

    date_iso = None
    date_meta = soup.find("meta", attrs={"name": "date"})
    if date_meta and date_meta.get("content"):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", date_meta["content"])
        if m:
            date_iso = m.group(1)

    # Each paragraph starts with a bold speaker label, e.g.
    # "President Trump: ..." or "Trump: ...". Extract only his.
    content_div = soup.find("article") or soup.find("main") or soup
    trump_paragraphs = []
    for p in content_div.find_all("p"):
        strong = p.find(["strong", "b"])
        if not strong:
            continue
        speaker = strong.get_text(strip=True).rstrip(":").lower()
        if speaker not in ("president trump", "trump", "president donald trump", "donald trump"):
          continue
        full_p_text = clean_text(p.get_text(separator=" "))
        # Strip the leading "Speaker:" label itself from the text.
        full_p_text = re.sub(r"^[^:]{1,30}:\s*", "", full_p_text)
        if full_p_text:
            trump_paragraphs.append(full_p_text)

    full_text = clean_text("\n\n".join(trump_paragraphs))
    if not full_text or len(full_text) < 50:
        return None  # not really his content, or extraction found nothing

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
        notes="Sourced from a Senate Democratic Caucus archive created "
              "to preserve public access after whitehouse.gov removed "
              "text transcripts in late May 2025 (confirmed via news "
              "reporting). Republishes Roll Call Factbase transcripts "
              "through a reliably scrapeable, server-rendered site. "
              "Multi-speaker events filtered to ONLY his own paragraphs.",
    )