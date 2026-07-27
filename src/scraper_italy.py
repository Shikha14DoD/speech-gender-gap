"""
Scraper for Italy -- Giorgia Meloni (President of the Council of Ministers),
governo.it.

Same strategy as Denmark: the site's own listing page (/en/interventi-en)
returned a bot-detection block when accessed programmatically, so instead
we discover real article URLs via the Wayback Machine CDX API, then fetch
each one LIVE from the actual site (individual article pages work fine --
only the listing page is blocked).

governo.it's /en/articolo/ path is a general government article feed,
likely shared with other ministers, not just the PM -- so results are
filtered by name-match, same principle as Denmark's multi-PM feed.

Unlike Denmark, governo.it publishes official English translations
directly (marked "[Courtesy translation]" on many pages) -- so this
country's full_text is already English, no machine translation needed
for MOST rows. Exception: some "video message" entries have NO written
transcript at all (audio-only, Italian-only) -- these are detected and
flagged in the notes column rather than silently included as if they
were real transcribed content.
"""

import re
from typing import List, Optional

from src.utils import get, soupify, clean_text, Speech
from src.text_processing import parse_date_loose, in_date_range, classify_as_speech, classify_content_type
from src.wayback_helper import get_archived_urls

CDX_PREFIX = "governo.it/en/articolo/"
MELONI_TENURE_START = "2022-10-22"


def parse_italy(leader_config: dict, start_date: str, end_date: str,
                 limit: Optional[int] = None) -> List[Speech]:
    print("== Italy ==")
    urls = get_archived_urls(CDX_PREFIX, from_date=MELONI_TENURE_START)
    print(f"  found {len(urls)} candidate URLs from Wayback CDX")

    # NOTE: an earlier version of this pre-filtered by URL keywords
    # ("speech"/"intervento" only) before fetching. That was found to be
    # far too narrow -- it missed huge numbers of real entries using
    # different words: "address", "remarks", "press statement",
    # "doorstep", "press point", "press conference", etc. So now we
    # check every candidate URL properly instead of pre-filtering blind.
    print(f"  checking all {len(urls)} candidate URLs (this will take a while)")

    speeches: List[Speech] = []
    for url in urls:
        article = _fetch_article(url, leader_config)
        if article is None:
            continue  # not Meloni, or couldn't be parsed
        # Extra safety net: even after the URL pre-filter, require the
        # content classifier to agree this is actually speech-like, not
        # just a news item that happens to have "meloni" in its slug.
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

    # h1 grabs the wrong element on this site (a generic site header).
    # The browser tab <title> tag is reliably the real article title here,
    # usually formatted as "Article Title | www.governo.it" -- strip that suffix.
    title_tag = soup.find("title")
    if title_tag:
        title = clean_text(title_tag.get_text(separator=" "))
        title = re.sub(r"\s*\|\s*www\.governo\.it\s*$", "", title)
    else:
        title = url
    page_text = soup.get_text()

    # Real pattern seen: "Wednesday, 20 September 2023" near the top.
    date_iso = None
    date_match = re.search(
        r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+(\d{4})\b",
        page_text,
    )
    if date_match:
        date_iso = parse_date_loose(date_match.group(0))

    # "Meloni" appearing anywhere on the page is too loose -- it lets
    # through institutional statements ("Statement by Palazzo Chigi"),
    # event-attendance news ("Meloni participates in..."), and pages
    # about other officials that merely mention her in passing. Require
    # her name in the TITLE specifically, which is a much stronger signal
    # this is actually about/by her.
    is_meloni = "meloni" in title.lower()
    if not is_meloni:
        return None

    content_div = soup.find("article") or soup.find("main") or soup
    paragraphs = [clean_text(p.get_text(separator=" ")) for p in content_div.find_all("p")]
    full_text = clean_text("\n\n".join(p for p in paragraphs if p))

    # Some "video message" entries have NO written transcript at all --
    # just a short English caption noting the video itself is only
    # available in Italian, with no text version of what was actually
    # said. Detect the site's own disclaimer and flag it clearly rather
    # than let these rows silently look like real transcribed content.
    text_lower = full_text.lower()
    has_no_transcript = (
        "available in italian only" in text_lower
        or ("available in" in text_lower and "only" in text_lower)
    )
    transcript_warning = (
        " \u26a0 NO ENGLISH TRANSCRIPT: this row's full_text is likely just a "
        "brief description that a video message occurred, not the actual "
        "spoken content -- the real video is Italian-only with no text "
        "version available on the page."
    ) if has_no_transcript else ""

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
        notes="Discovered via Wayback CDX API (site's listing page returns "
              "bot-detection block when scraped programmatically); fetched "
              "live, not archived. Filtered to Meloni by name-match. "
              "Official English translation direct from source -- no "
              "machine translation needed for this country."
              + transcript_warning,
    )