"""
Scraper for China -- Li Qiang (Premier), english.www.gov.cn.

Unlike Xi Jinping's SCIO listing page, this site's own search/listing
interface is JavaScript-rendered (returns "0 results" to a plain
request). So we discover article URLs via the Wayback Machine CDX API
instead -- BUT this site has a large historical archive (back to at
least 2014) that gets periodically re-crawled, so Wayback's from/to
filters (which filter by CRAWL date, not article date) return a
misleading mix of old and new URLs. Fix: query without date
restriction, then filter candidates ourselves by parsing the date
embedded directly in each URL's path.
"""

import re
from typing import List, Optional

from src.utils import get, soupify, clean_text, Speech
from src.text_processing import parse_date_loose, in_date_range, classify_as_speech, classify_content_type
from src.wayback_helper import get_archived_urls

CDX_PREFIX = "english.www.gov.cn/news/"

# Matches both URL date formats seen on this site:
#   /premier/news/2014/08/23/content_...   (old format, slashes)
#   /premier/news/202303/14/content_...    (newer format, YYYYMM/DD)
URL_DATE_OLD = re.compile(r"/news/(\d{4})/(\d{2})/(\d{2})/")
URL_DATE_NEW = re.compile(r"/news/(\d{4})(\d{2})/(\d{2})/")


def _url_date(url: str) -> Optional[str]:
    m = URL_DATE_OLD.search(url) or URL_DATE_NEW.search(url)
    if m:
        y, mo, d = m.groups()
        return f"{y}-{mo}-{d}"
    return None


def parse_liqiang(leader_config: dict, start_date: str, end_date: str,
                   limit: Optional[int] = None) -> List[Speech]:
    print("== China (Li Qiang) ==")
    # No from_date here -- we filter by URL-embedded date ourselves below,
    # since Wayback's own date filter is unreliable on this site.
    all_urls = get_archived_urls(CDX_PREFIX)
    print(f"  found {len(all_urls)} total candidate URLs from Wayback CDX")

    # Pre-filter by the date embedded in the URL itself, BEFORE fetching
    # anything -- avoids wasting time on years outside our target range.
    candidates = []
    for url in all_urls:
        u_date = _url_date(url)
        if u_date and in_date_range(u_date, start_date, end_date):
            candidates.append(url)
    print(f"  {len(candidates)} candidates fall within {start_date} to {end_date}")

    speeches: List[Speech] = []
    for i, url in enumerate(candidates, 1):
        if i % 25 == 0:
            print(f"  checked {i}/{len(candidates)}, {len(speeches)} kept...")
        article = _fetch_article(url, leader_config)
        if article is None:
            continue
        if article.likely_speech == "no":
            continue
        if in_date_range(article.date, start_date, end_date):
            speeches.append(article)
        if limit and len(speeches) >= limit:
            break

    return speeches


def _fetch_article(url: str, leader_config: dict) -> Optional[Speech]:
    resp = get(url)
    if resp is None:
        return None
    soup = soupify(resp)

    title = None
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = clean_text(og_title["content"])
    if not title:
        title_tag = soup.find("title")
        title = clean_text(title_tag.get_text(separator=" ")) if title_tag else url

    if "li qiang" not in title.lower() and "premier" not in title.lower():
        return None

    date_iso = None
    date_meta = soup.find("meta", attrs={"name": "publishdate"})
    if date_meta and date_meta.get("content"):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", date_meta["content"])
        if m:
            date_iso = m.group(1)

    if date_iso is None:
        date_iso = _url_date(url)

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
        notes="Discovered via Wayback CDX API (no date filter -- site's "
              "crawl-date metadata doesn't reliably correlate with "
              "article date due to periodic re-crawling of old pages). "
              "Filtered by date embedded in the URL itself instead. "
              "Fetched live, not archived. Filtered to entries "
              "mentioning Li Qiang by name in the title.",
    )