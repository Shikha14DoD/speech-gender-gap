"""
Scraper for Mexico (President Andrés Manuel López Obrador, AMLO).

Same source and site structure as scraper_mexico.py (Sheinbaum) --
gob.mx Presidencia archive -- just a different speaker and date range
(Jan 2024 - Sep 30 2024, end of his term).

Reuses the same extraction logic already validated for Sheinbaum:
  - date pulled from listing page's <time date="..."> attribute
  - multi-paragraph speaker tracking (only first paragraph of a turn
    is labeled with <strong>)
  - —000— section-break marker resets speaker tracking regardless of
    whether it's wrapped in <strong>
  - only paragraphs confirmed as his are appended; any other labeled
    speaker (moderator, crowd, reporters, etc.) is skipped

NOT YET VALIDATED against live source -- same caveat as scraper_mexico.py's
first draft. Test on a small batch before trusting fully. In particular,
confirm the speaker label variant below is complete (search snippets
only showed "PRESIDENTE ANDRÉS MANUEL LÓPEZ OBRADOR:" consistently, but
early-2024 pages haven't been individually checked).
"""

import re
import time
from typing import List, Optional

from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup

from src.utils import clean_text, Speech
from src.text_processing import in_date_range, classify_as_speech, classify_content_type

BASE_LISTING = "https://www.gob.mx/amlo/archivo/articulos"
MAX_PAGES = 300  # AMLO's term covered ~6 years total, but we only need Jan-Sep 2024

# Confirmed from search snippets across Jan-Sep 2024 pages.
SPEAKER_MATCH = (
    "presidente andrés manuel lópez obrador",
    "presidente andres manuel lopez obrador",  # no-accent fallback
)

def _extract_speaker_label(p_text: str):
    """
    This site template has no <strong> tags -- speaker labels are plain
    text like 'PRESIDENTE ANDRÉS MANUEL LÓPEZ OBRADOR: Buenos días...'
    or with inline notes: 'LUIZ INÁCIO LULA DA SILVA, PRESIDENTE DE
    BRASIL(interpretación del portugués al español): Lo llamo...'

    Detects a speaker label by checking whether the text before the
    first colon is all-uppercase once any parenthetical content is
    stripped out. Returns (speaker_lowercase, rest_of_text) or
    (None, original_text) if no label pattern is found.
    """
    if ":" not in p_text:
        return None, p_text
    prefix, rest = p_text.split(":", 1)
    prefix_stripped = re.sub(r"\([^)]*\)", "", prefix).strip()
    if not prefix_stripped or len(prefix_stripped) > 100:
        return None, p_text
    if not any(c.isalpha() for c in prefix_stripped):
        return None, p_text
    if prefix_stripped == prefix_stripped.upper():
        return prefix_stripped.lower(), rest.strip()
    return None, p_text


# Matches "—000—", "―000―", "-000-" etc. (segment/scene-break marker,
# same convention as scraper_mexico.py).
section_break_re = re.compile(r"^[\s\-\u2012-\u2015_]*0{2,3}[\s\-\u2012-\u2015_]*$")

# Matches stage directions like "(INICIA VIDEO)", "(TERMINA VIDEO)" --
# paragraphs that are ENTIRELY a single parenthetical with no other text.
stage_direction_re = re.compile(r"^\([^)]*\)$")


def _get(url: str, max_retries: int = 3, delay_seconds: float = 2.0) -> Optional[str]:
    for attempt in range(1, max_retries + 1):
        try:
            resp = curl_requests.get(url, impersonate="chrome", timeout=30)
            time.sleep(delay_seconds)
            if resp.status_code == 200:
                return resp.text
            print(f"  [warn] {url} returned status {resp.status_code} (attempt {attempt})")
        except Exception as e:
            print(f"  [warn] {url} raised {e!r} (attempt {attempt})")
    print(f"  [error] giving up on {url}")
    return None


def _parse_spanish_date_from_title(title: str) -> Optional[str]:
    months = {
        "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
        "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
        "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12",
    }
    m = re.search(
        r"(\d{1,2})\s*°?\s*de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        title.lower(),
    )
    if not m:
        return None
    day, month_name, year = m.groups()
    month = months.get(month_name)
    if not month:
        return None
    return f"{year}-{month}-{int(day):02d}"


def parse_amlo(leader_config: dict, start_date: str, end_date: str,
               limit: Optional[int] = None) -> List[Speech]:
    print("== Mexico (AMLO) ==")
    speeches: List[Speech] = []
    page = 1

    while True:
        url = f"{BASE_LISTING}?order=DESC&page={page}"
        html = _get(url)
        if html is None:
            break
        soup = BeautifulSoup(html, "html.parser")

        candidates = []
        for art in soup.find_all("article"):
            a_tag = art.find("a", href=True)
            time_tag = art.find("time", attrs={"date": True})
            if not a_tag or not time_tag:
                continue
            href = a_tag["href"]
            m = re.match(r"(\d{4}-\d{2}-\d{2})", time_tag["date"])
            listing_date = m.group(1) if m else None
            candidates.append((href, listing_date))

        if not candidates:
            print(f"  [info] no more articles on page {page}, stopping.")
            break

        if page % 10 == 0 or page == 1:
            print(f"  page {page}: checking {len(candidates)} candidate links...")

        stop_all = False
        for href, listing_date in candidates:
            full_url = href if href.startswith("http") else f"https://www.gob.mx{href}"
            if listing_date and listing_date < start_date:
                stop_all = True
                break
            if listing_date and listing_date > end_date:
                # Still in Sheinbaum-era pages; skip without fetching
                # the article (saves time -- no need to fetch pages we
                # already know are out of range).
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
        if page > MAX_PAGES:
            break

    return speeches


def _fetch_article(url: str, leader_config: dict, listing_date: Optional[str] = None) -> Optional[Speech]:
    html = _get(url)
    if html is None:
        return None
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("h1")
    title = clean_text(title_tag.get_text(separator=" ")) if title_tag else url

    date_iso = listing_date
    if date_iso is None:
        date_iso = _parse_spanish_date_from_title(title)

    content_div = (
        soup.find("div", class_="article-body")
        or soup.find("article")
        or soup.find("main")
        or soup
    )
    amlo_paragraphs = []
    current_speaker_is_amlo = False

    for p in content_div.find_all("p"):
        p_text_raw = p.get_text(separator=" ", strip=True)

        if section_break_re.match(p_text_raw):
            current_speaker_is_amlo = False
            continue
        if stage_direction_re.match(p_text_raw):
            # Stage direction (e.g. "(INICIA VIDEO)") -- not content,
            # but doesn't necessarily end his turn either. Skip without
            # changing speaker state.
            continue

        speaker, rest_text = _extract_speaker_label(p_text_raw)
        if speaker is not None:
            if speaker in SPEAKER_MATCH:
                current_speaker_is_amlo = True
                full_p_text = clean_text(rest_text)
            else:
                current_speaker_is_amlo = False
                continue
        else:
            if not current_speaker_is_amlo:
                continue
            full_p_text = clean_text(p_text_raw)

        if full_p_text:
            amlo_paragraphs.append(full_p_text)

    full_text = clean_text("\n\n".join(amlo_paragraphs))
    if not full_text or len(full_text) < 50:
        return None

    return Speech(
        country=leader_config["country"],
        leader=leader_config["leader"],
        role=leader_config["role"],
        date=date_iso,
        title=title,
        full_text=full_text,
        language="Spanish",
        source_url=url,
        likely_speech=classify_as_speech(title),
        content_type=classify_content_type(title),
        notes="Sourced from gob.mx Presidencia archive (bot-protected, "
              "fetched via curl_cffi chrome impersonation). Reuses "
              "extraction logic validated for Sheinbaum (scraper_mexico.py) "
              "-- multi-speaker transcripts filtered to ONLY AMLO's own "
              "paragraphs. NOT YET independently validated for this "
              "leader specifically as of Aug 2026 -- spot-check against "
              "the live source before trusting fully.",
    )