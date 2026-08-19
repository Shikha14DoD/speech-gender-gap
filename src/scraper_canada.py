"""
Scraper for Canada (PM Justin Trudeau through 2025-03-14, PM Mark
Carney after). Source: pm.gc.ca official site.

UNUSUAL APPROACH: this site's listing/index pages are JavaScript-
rendered (confirmed via manual testing -- static HTML has an empty
content section even though the browser shows articles). No working
API endpoint was found via dev tools either. Individual article pages,
however, are fully server-rendered and scrapeable directly.

Workaround: historical article URLs were discovered via the Wayback
Machine CDX API (see find_canada_urls_cdx.py), which lists every
archived URL under /en/news/{speeches,statements,news-releases,
readouts}/ regardless of whether the live listing page would surface
it. Per project lessons learned, CDX *crawl* dates are unreliable, so
filtering to 2024-2026 was done via the URL's own embedded date
(/category/YYYY/MM/DD/slug), not the crawl timestamp. This produced
canada_urls_from_cdx.txt, which this scraper reads and processes --
it does NOT paginate a live listing page like other scrapers.

Scope decision (Aug 2026): only "speeches" and "statements" categories
are included. "news-releases" and "readouts" were excluded after
testing showed they frequently include quotes from OTHER officials
(ministers, mayors, foreign leaders) mixed into the same content --
correctly attributing only the PM's own words there would need much
more careful per-quote speaker detection. Speeches and statements are
the PM's own first-person words throughout, matching this project's
existing single-speaker-source pattern (e.g. Moldova).

Content is native English -- no translation needed. Single-speaker
(PM's own remarks/statements) -- no multi-speaker filtering needed,
unlike Mexico/Trump/Biden's press conference transcripts.
"""

import re
import time
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from src.utils import clean_text, Speech
from src.text_processing import in_date_range, classify_as_speech, classify_content_type

URL_LIST_PATH = "canada_urls_from_cdx.txt"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _get(url: str, max_retries: int = 3, delay_seconds: float = 1.0) -> Optional[str]:
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


def parse_canada(leader_config: dict, start_date: str, end_date: str,
                  limit: Optional[int] = None) -> List[Speech]:
    print(f"== Canada ({leader_config['leader']}) ==")
    speeches: List[Speech] = []

    try:
        with open(URL_LIST_PATH, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"  [error] {URL_LIST_PATH} not found. Run find_canada_urls_cdx.py first.")
        return speeches

    print(f"  {len(urls)} candidate URLs loaded from {URL_LIST_PATH}")

    for i, url in enumerate(urls):
        # Quick pre-filter using the URL's own embedded date, before
        # even fetching the page, to save time on obviously out-of-
        # range articles.
        m = re.search(r"/news/[a-z-]+/(\d{4})/(\d{2})/(\d{2})/", url)
        if m:
            url_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            if not in_date_range(url_date, start_date, end_date):
                continue

        if (i + 1) % 100 == 0:
            print(f"  ...checked {i + 1}/{len(urls)} candidates, {len(speeches)} matched so far")

        article = _fetch_article(url, leader_config)
        if article is None:
            continue
        if not in_date_range(article.date, start_date, end_date):
            continue
        speeches.append(article)
        if limit and len(speeches) >= limit:
            break

    return speeches


def parse_canada_videos(leader_config: dict, start_date: str, end_date: str,
                         limit: Optional[int] = None) -> List[Speech]:
    """
    Separate discovery path for the /en/videos/ category -- unlike
    /en/news/speeches and /en/news/statements, this listing page IS
    server-rendered and can be paginated directly, no CDX workaround
    needed. Found (Aug 2026) to contain substantial full speech
    transcripts not present in speeches/statements at all (e.g. UN
    General Assembly remarks, National Day for Truth and
    Reconciliation remarks).
    """
    print(f"== Canada Videos ({leader_config['leader']}) ==")
    speeches: List[Speech] = []
    page = 0  # site uses 0-indexed ?page= param

    while True:
        url = f"https://www.pm.gc.ca/en/videos?page={page}"
        html = _get(url)
        if html is None:
            break
        soup = BeautifulSoup(html, "html.parser")

        # Links directly under the listing, each followed by "Date YYYY-MM-DD"
        candidates = []
        for a in soup.find_all("a", href=True):
            if "/en/videos/" in a["href"] and a["href"].rstrip("/") != "https://www.pm.gc.ca/en/videos":
                time_tag = a.find_next("time", attrs={"datetime": True})
                if time_tag:
                    listing_date = time_tag["datetime"][:10]
                    candidates.append((a["href"], listing_date))

        if not candidates:
            print(f"  [info] no more videos on page {page}, stopping.")
            break

        if page % 5 == 0:
            print(f"  page {page}: checking {len(candidates)} candidate links...")

        stop_all = False
        for href, listing_date in candidates:
            full_url = href if href.startswith("http") else f"https://www.pm.gc.ca{href}"
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

        page += 1
        if page > 100:  # safety cap
            break

    return speeches


def _fetch_article(url: str, leader_config: dict, listing_date: Optional[str] = None) -> Optional[Speech]:
    html = _get(url)
    if html is None:
        return None
    soup = BeautifulSoup(html, "html.parser")

    date_meta = soup.find("meta", attrs={"name": "dcterms.issued"})
    if date_meta and date_meta.get("content"):
        date_iso = date_meta["content"].strip()[:10]
    elif listing_date:
        date_iso = listing_date
    else:
        return None

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else url
    title = re.sub(r"\s*\|\s*Prime Minister of Canada\s*$", "", title).strip()

    all_body_divs = soup.find_all("div", class_="field--name-body")
    if not all_body_divs:
        return None
    # The page has multiple divs sharing this class (e.g. a search
    # widget) -- the real article body is the one with the most
    # actual paragraph content, not necessarily the first match.
    content_div = max(all_body_divs, key=lambda d: len(d.get_text(strip=True)))

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
        language="English",
        source_url=url,
        likely_speech=classify_as_speech(title),
        content_type=classify_content_type(title),
        notes="Sourced from pm.gc.ca. Native English, no translation "
              "needed. Single-speaker (PM's own remarks), no multi-"
              "speaker filtering needed. Article URLs discovered via "
              "Wayback Machine CDX API since the live listing page is "
              "JavaScript-rendered and has no working static or API "
              "fallback found -- see find_canada_urls_cdx.py and the "
              "module docstring for details. NOT YET independently "
              "validated as of Aug 2026 -- spot-check before trusting.",
    )
