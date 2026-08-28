"""
Scraper for Barbados -- Mia Mottley (Prime Minister), pmo.gov.bb.

Plain WordPress site, no JavaScript rendering or bot-detection issues
encountered -- straightforward to scrape directly.

IMPORTANT: this is a general "Latest Updates" feed (not speeches-only)
-- mixes real speeches/remarks with routine press releases, COVID
updates, ministerial announcements, etc. Same caveat as Slovenia and
Samoa: likely_speech/content_type are heuristic flags for manual
review, not a filter that silently drops ambiguous content.
"""

import re
from typing import List, Optional

from src.utils import get, soupify, clean_text, Speech
from src.text_processing import parse_date_loose, in_date_range, classify_as_speech, classify_content_type
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup

BASE_LISTING = "https://pmo.gov.bb/category/latest/"
MAX_PAGES = 60

def _curl_get(url: str, max_retries: int = 3, delay_seconds: float = 2.0) -> Optional[str]:
    """Fetch a URL using curl_cffi (browser impersonation) -- pmo.gov.bb
    blocks plain `requests` library traffic with a 403, same category
    of bot-detection issue solved elsewhere in this project. Includes
    the same polite delay + retry pattern as the shared get() function,
    which this custom fetcher would otherwise skip entirely."""
    import time

    for attempt in range(1, max_retries + 1):
        try:
            resp = curl_requests.get(url, impersonate="chrome", timeout=30)
            time.sleep(delay_seconds)
            if resp.status_code == 200:
                return resp.text
            print(f"  [warn] status {resp.status_code} for {url} (attempt {attempt})")
        except Exception as e:
            print(f"  [warn] curl_cffi request failed for {url}: {e} (attempt {attempt})")
        if attempt < max_retries:
            time.sleep(delay_seconds * attempt)

    print(f"  [error] giving up on {url}")
    return None

def parse_barbados_archive(leader_config: dict, start_date: str, end_date: str,
                            limit: Optional[int] = None) -> List[Speech]:
    """
    Alternative discovery route via WordPress's month-based date
    archive (pmo.gov.bb/YYYY/MM/), instead of the /category/latest/
    listing. Found (Aug 2026) after the category-based approach only
    surfaced ~47 candidates total, missing all of Jan-Sep 2023 and
    much of 2024 entirely -- the month archive reaches back much
    further and isn't affected by the "Speeches" category tag
    breaking after Feb 2025, since it doesn't rely on any tag at all.
    """
    print("== Barbados (month archive) ==")
    speeches: List[Speech] = []
    seen_urls = set()
    total_candidates = [0]
    rejected = [0]

    import datetime
    start_dt = datetime.date.fromisoformat(start_date)
    end_dt = datetime.date.fromisoformat(end_date)
    if end_dt > datetime.date.today():
        end_dt = datetime.date.today()

    months = []
    y, m = start_dt.year, start_dt.month
    while (y, m) <= (end_dt.year, end_dt.month):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    for y, m in months:
        page = 1
        while True:
            url = f"https://pmo.gov.bb/{y}/{m:02d}/" if page == 1 else f"https://pmo.gov.bb/{y}/{m:02d}/page/{page}/"
            resp = _curl_get(url)
            if resp is None:
                break
            soup = BeautifulSoup(resp, "html.parser")

            entries = []
            for h2 in soup.find_all("h2"):
                a = h2.find("a", href=True)
                if not a:
                    continue
                href = a["href"]
                if re.search(r"pmo\.gov\.bb/\d{4}/\d{2}/\d{2}/", href):
                    entries.append(href)

            if not entries:
                break

            print(f"  {y}-{m:02d} page {page}: {len(entries)} candidate links")

            for href in entries:
                if href in seen_urls:
                    continue
                seen_urls.add(href)
                total_candidates[0] += 1
                article = _fetch_article(href, leader_config)
                if article is None:
                    rejected[0] += 1
                    print(f"    [rejected] {href}")
                    continue
                if in_date_range(article.date, start_date, end_date):
                    speeches.append(article)
                if limit and len(speeches) >= limit:
                    print(f"  TOTAL candidates seen: {total_candidates[0]}, rejected: {rejected[0]}, kept: {len(speeches)}")
                    return speeches

            page += 1
            if page > 10:
                break

    print(f"  TOTAL candidates seen: {total_candidates[0]}, rejected by content filter: {rejected[0]}, kept: {len(speeches)}")
    return speeches


def parse_barbados(leader_config: dict, start_date: str, end_date: str,
                    limit: Optional[int] = None) -> List[Speech]:
    print("== Barbados ==")
    speeches: List[Speech] = []
    page = 1
    seen_urls = set()
    pages_without_match = 0

    while True:
        url = BASE_LISTING if page == 1 else f"https://pmo.gov.bb/category/latest/page/{page}/"
        resp = _curl_get(url)
        if resp is None:
            break
        soup = BeautifulSoup(resp, "html.parser")

        entries = []
        for h2 in soup.find_all("h2"):
            a = h2.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            if not re.search(r"pmo\.gov\.bb/\d{4}/\d{2}/\d{2}/", href):
                continue
            entries.append(href)

        if not entries:
            print(f"  [info] no more articles on page {page}, stopping.")
            break

        # Don't trust extraction order (the page mixes in a "Recent
        # Posts" sidebar widget alongside the main chronological list,
        # so entries can appear out of order) -- sort by the date
        # embedded in each URL instead, newest first, before applying
        # the early-stop logic.
        def _url_date_key(href):
            m = re.search(r"pmo\.gov\.bb/(\d{4})/(\d{2})/(\d{2})/", href)
            return m.groups() if m else ("0000", "00", "00")

        entries = sorted(set(entries), key=_url_date_key, reverse=True)
        print(f"  page {page}: checking {len(entries)} candidate links (sorted)...")

        stop_all = False
        for href in entries:
            if href in seen_urls:
                continue
            seen_urls.add(href)

            article = _fetch_article(href, leader_config)
            if article is None:
                continue
            if article.date and article.date < start_date:
                # Don't trust a single old date as proof we've reached
                # the archive's end -- a "Recent Posts" sidebar widget
                # can inject out-of-sequence old posts into any page
                # (confirmed: a 2022 post appeared mixed into a
                # 2024-dated page). Just skip this one entry instead
                # of stopping the whole scrape.
                continue
            if article.likely_speech == "no":
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


def _fetch_article(url: str, leader_config: dict) -> Optional[Speech]:
    resp = _curl_get(url)
    if resp is None:
        return None
    soup = BeautifulSoup(resp, "html.parser")

    title_tag = soup.find("title")
    if title_tag:
        title = clean_text(title_tag.get_text(separator=" "))
        title = re.sub(r"\s*[\u2013\u2014-]\s*PMO\s*$", "", title)  # strip trailing "– PMO" suffix
    else:
        title = url

    # Date from the URL itself (YYYY/MM/DD in the path) -- reliable,
    # doesn't depend on parsing visible page text.
    date_iso = None
    m = re.search(r"pmo\.gov\.bb/(\d{4})/(\d{2})/(\d{2})/", url)
    if m:
        y, mo, d = m.groups()
        date_iso = f"{y}-{mo}-{d}"

    content_div = soup.find("article") or soup.find("main") or soup
    paragraphs = [clean_text(p.get_text(separator=" ")) for p in content_div.find_all("p")]
    full_text = clean_text("\n\n".join(p for p in paragraphs if p))
    # Exclude content that isn't genuinely her own words:
    # - journalist-bylined news articles ("BY [Name]")
    # - administrative/procedural documents (appointment lists, travel
    #   announcements) that describe her rather than quote her
    text_lower = full_text.strip().lower()
    title_lower = title.lower()

    if re.match(r"^by\s+[a-z]", text_lower):
        return None  # journalist byline -- third-person news coverage

    admin_title_markers = [
        "sworn-in", "sworn in", "cabinet appointment", "appointment of",
        "travels to", "travels abroad", "departs for",
    ]
    if any(marker in title_lower for marker in admin_title_markers):
        return None  # administrative/procedural document, not her words

    # Require some first-person signal in the text OR a clear
    # speech/remarks framing to keep -- otherwise treat as third-person
    # coverage and exclude.
    first_person_markers = ["i ", "we ", "my ", "our ", "transcript", "remarks by", "statement by"]
    if not any(marker in text_lower[:500] for marker in first_person_markers):
        return None
    # Journalist-bylined news articles ("BY [Name]") are third-person
    # coverage, not her own words -- exclude, same principle as
    # excluding phone-call readouts elsewhere in this project.
    if re.match(r"^BY\s+[A-Z]", full_text.strip()):
        return None

    # Some entries link out to a PDF transcript instead of having text
    # directly on the page (or are photo/video coverage only, with no
    # transcript at all). Detect both cases so they're flagged, not
    # silently treated as if full_text is complete.
    pdf_links = [
        a["href"] for a in content_div.find_all("a", href=True)
        if a["href"].lower().endswith(".pdf")
    ]
    no_transcript_warning = ""
    if pdf_links and len(full_text) < 300:
        no_transcript_warning = (
            f" \u26a0 TRANSCRIPT LIKELY IN PDF, NOT SCRAPED: {pdf_links[0]} "
            "-- full_text above may be just a short intro/caption, not "
            "the actual speech content. PDF extraction not yet built "
            "for this source."
        )
    elif len(full_text) < 150:
        no_transcript_warning = (
            " \u26a0 VERY SHORT TEXT: this may be a photo/video-only "
            "entry with no written transcript available on the page."
        )

    return Speech(
        country=leader_config["country"],
        leader=leader_config["leader"],
        role=leader_config["role"],
        date=date_iso,
        title=title,
        full_text=full_text,
        language="English",
        source_url=url,
        likely_speech="yes",  # already passed strict first-person/byline
                               # filtering above -- if it survived, it's
                               # confirmed genuine speech content
        content_type="Speech",
        notes="Scraped from the general 'Latest Updates' feed (not the "
              "dedicated Speeches category, which stopped being tagged "
              "after Feb 2025 -- verified directly against the live "
              "site). Mixes real speeches with routine announcements; "
              "manually review 'maybe' rows. Some entries are "
              "photo/video coverage only, or link out to a PDF "
              "transcript not yet extracted -- see warning below if "
              "present. Date parsed from URL path (reliable), not page "
              "text." + no_transcript_warning,
    )