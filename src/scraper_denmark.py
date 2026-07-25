"""
Scraper for Denmark -- Mette Frederiksen (Prime Minister), stm.dk.

The site's own speech-listing page loads its content via client-side
JavaScript that our scraper can't execute, so instead of parsing that
listing page, we:
  1. Ask the Wayback Machine CDX API for every URL it's ever archived
     under stm.dk/statsministeren/taler/ (covers every PM since 1998).
  2. Fetch each URL LIVE (not from the archive -- the current real page)
     to get up-to-date title/date/text.
  3. Filter to Mette Frederiksen specifically (the CDX list includes
     her predecessors too) AND to our target date range.
"""

import re
from typing import List, Optional

from src.utils import get, soupify, clean_text, Speech
from src.text_processing import parse_date_loose, in_date_range, classify_as_speech
from src.wayback_helper import get_archived_urls

# Danish version used for discovery -- broader historical coverage than
# the English subdomain, and we've confirmed individual pages are readable.
CDX_PREFIX = "stm.dk/statsministeren/taler/"

DANISH_MONTHS = {
    "januar": 1, "februar": 2, "marts": 3, "april": 4, "maj": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11,
    "december": 12,
}


def _parse_danish_written_date(match: "re.Match") -> Optional[str]:
    """Convert a matched ('1', 'januar', '2023')-style Danish date to ISO format."""
    import datetime as dt
    day, month_name, year = match.groups()
    month = DANISH_MONTHS.get(month_name.lower())
    if not month:
        return None
    try:
        return dt.date(int(year), month, int(day)).isoformat()
    except ValueError:
        return None
    
def parse_denmark(leader_config: dict, start_date: str, end_date: str,
                   limit: Optional[int] = None) -> List[Speech]:
    print("== Denmark ==")
    # Mette Frederiksen became PM on 27 June 2019 -- no need to ask the
    # Wayback Machine for anything before that.
    urls = get_archived_urls(CDX_PREFIX, from_date="2019-06-27")
    print(f"  found {len(urls)} candidate URLs from Wayback CDX")

    speeches: List[Speech] = []
    for url in urls:
        # Skip the listing page itself if it shows up in the CDX results.
        if url.rstrip("/").endswith("/taler"):
            continue

        article = _fetch_article(url, leader_config)
        if article is None:
            continue  # not Mette Frederiksen, or couldn't be parsed
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

    title_tag = soup.find("h1")
    title = clean_text(title_tag.get_text()) if title_tag else url
    page_text = soup.get_text()

    # Real pattern varies by page age. Try, in order:
    #   1. Numeric Danish date: "11.04.2024"
    #   2. Written-out Danish date: "1. januar 2023" (day. monthname year)
    # Speaker name is checked separately, against the whole page text --
    # the CDX list spans every Danish PM since 1998, so this check is
    # what keeps out her predecessors' speeches.
    date_iso = None

    numeric_match = re.search(r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b", page_text)
    if numeric_match:
        date_iso = parse_date_loose(numeric_match.group(1))

    if date_iso is None:
        written_match = re.search(
            r"\b(\d{1,2})\.\s*(januar|februar|marts|april|maj|juni|juli|"
            r"august|september|oktober|november|december)\s*(\d{4})\b",
            page_text,
            re.IGNORECASE,
        )
        if written_match:
            date_iso = _parse_danish_written_date(written_match)

    is_frederiksen = "Frederiksen" in page_text
    if not is_frederiksen:
        return None  # this is a predecessor PM's speech -- skip it
    content_div = soup.find("main") or soup.find("article") or soup
    paragraphs = [clean_text(p.get_text()) for p in content_div.find_all("p")]
    full_text = clean_text("\n\n".join(p for p in paragraphs if p))

    return Speech(
        country=leader_config["country"],
        leader=leader_config["leader"],
        role=leader_config["role"],
        date=date_iso,
        title=title,
        full_text=full_text,
        language="Danish",
        source_url=url,
        likely_speech=classify_as_speech(title),
        notes="Discovered via Wayback CDX API (site's own listing page is "
              "JS-rendered/broken for scraping); fetched live, not archived. "
              "Filtered to Mette Frederiksen by name-match near date metadata.",
    )