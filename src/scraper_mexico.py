"""
Scraper for Mexico (President Claudia Sheinbaum Pardo).

Source: gob.mx Presidencia archive (paginated blog listing).
Bot detection confirmed on this site -- uses curl_cffi with chrome
impersonation, same pattern as scraper_barbados.py.

UNTESTED FIRST DRAFT: web_fetch to this site is also blocked for the
assistant, so this has not been validated against live HTML. Expect to
need at least one debugging pass -- check especially:
  - the listing page's link selector (href pattern for article links)
  - the exact pagination query param behavior (?page=N&order=DESC)
  - the date meta tag (guessed at a few common ones; may need adjusting)
  - the speaker label variants (only 2 confirmed from search snippets --
    there may be more, e.g. accented vs. non-accented, spacing differences)
"""

import re
import time
from typing import List, Optional

from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup

from src.utils import soupify, clean_text, Speech
from src.text_processing import in_date_range, classify_as_speech, classify_content_type

BASE_LISTING = "https://www.gob.mx/presidencia/es/archivo/articulos"
MAX_PAGES = 200  # safety cap; adjust if the real archive is bigger

# Confirmed variants of Sheinbaum's own speaker label (lowercased, colon-stripped).
# Add more here if validation finds additional variants.
SPEAKER_MATCH = (
    "presidenta claudia sheinbaum pardo",
    "presidenta de méxico, claudia sheinbaum pardo",
    "presidenta de mexico, claudia sheinbaum pardo",
)

# Substrings that identify OTHER speakers to exclude (governors, cabinet
# secretaries, reporters, narrators). Substring match, not exact --
# broader net than Trump's exact-match approach since Mexico has many
# more distinct co-speakers (state governors, various secretaries).
EXCLUDE_SPEAKER_SUBSTRINGS = (
    "gobernador de",
    "gobernadora de",
    "secretari",       # catches "secretario de" / "secretaria de"
    "pregunta",
    "voz mujer",
    "voz hombre",
    "enlace videollamada",
)


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
    """
    Fallback date extractor. Titles reliably contain a pattern like
    'del 08 de agosto de 2025' or 'del 6 de noviembre de 2024'.
    Returns ISO date string or None.
    """
    months = {
        "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
        "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
        "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12",
    }
    m = re.search(
        r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        title.lower(),
    )
    if not m:
        return None
    day, month_name, year = m.groups()
    month = months.get(month_name)
    if not month:
        return None
    return f"{year}-{month}-{int(day):02d}"


def parse_mexico(leader_config: dict, start_date: str, end_date: str,
                  limit: Optional[int] = None) -> List[Speech]:
    print("== Mexico (Sheinbaum) ==")
    speeches: List[Speech] = []
    page = 1

    while True:
        url = f"{BASE_LISTING}?order=DESC&page={page}"
        html = _get(url)
        if html is None:
            break
        soup = BeautifulSoup(html, "html.parser")

        # Listing page gives date, title, and url per article directly --
        # confirmed structure: <article><time date="YYYY-MM-DD HH:MM:SS">...
        # Extracted in DOM order (reverse-chronological), NOT re-sorted,
        # since alphabetical href sorting would scramble date order.
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

        if page % 5 == 0 or page == 1:
            print(f"  page {page}: checking {len(candidates)} candidate links...")

        stop_all = False
        for href, listing_date in candidates:
            full_url = href if href.startswith("http") else f"https://www.gob.mx{href}"
            if listing_date and listing_date < start_date:
                stop_all = True  # reverse-chronological; nothing older matters
                break
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

    # Listing page's <time date="..."> is the primary, reliable source
    # (confirmed via manual HTML inspection -- NOT the "date-marque" div,
    # which turned out to be an unrelated sitewide "latest posts" widget).
    date_iso = listing_date
    if date_iso is None:
        date_iso = _parse_spanish_date_from_title(title)

    content_div = (
        soup.find("div", class_="article-body")
        or soup.find("article")
        or soup.find("main")
        or soup
    )
    sheinbaum_paragraphs = []
    current_speaker_is_sheinbaum = False
    # Matches "—000—", "―000―", "-000-" etc. (segment/scene-break marker
    # used inconsistently on this site -- sometimes wrapped in <strong>,
    # sometimes not -- so we check by text content, not just tag structure).
    section_break_re = re.compile(r"^[\s\-\u2012-\u2015_]*0{2,3}[\s\-\u2012-\u2015_]*$")

    for p in content_div.find_all("p"):
        p_text_raw = p.get_text(strip=True)
        if section_break_re.match(p_text_raw):
            current_speaker_is_sheinbaum = False
            continue

        strong = p.find(["strong", "b"])
        if strong:
            speaker = strong.get_text(strip=True).rstrip(":").lower()
            if speaker in SPEAKER_MATCH:
                current_speaker_is_sheinbaum = True
                full_p_text = clean_text(p.get_text(separator=" "))
                full_p_text = re.sub(r"^[^:]{1,60}:\s*", "", full_p_text)
            else:
                # ANY other labeled speaker (moderador, asistentes/crowd,
                # secretaries, governors, reporters, etc.) -- not her.
                # Explicit skip here is the fix: previously this branch
                # set current_speaker_is_sheinbaum=False but still fell
                # through to append the text anyway, leaking moderator/
                # crowd lines into her attributed speech.
                current_speaker_is_sheinbaum = False
                continue
        else:
            # No speaker label on this paragraph -- it continues whoever
            # was last speaking (confirmed via manual inspection: multi-
            # paragraph turns only label the first paragraph).
            if not current_speaker_is_sheinbaum:
                continue
            full_p_text = clean_text(p.get_text(separator=" "))

        if full_p_text:
            sheinbaum_paragraphs.append(full_p_text)

    full_text = clean_text("\n\n".join(sheinbaum_paragraphs))
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
              "fetched via curl_cffi chrome impersonation). Multi-speaker "
              "transcripts filtered to ONLY Sheinbaum's own paragraphs; "
              "other speakers (governors, secretaries, reporters) excluded. "
              "IMPORTANT: this is a first-draft scraper as of Aug 2026, "
              "not yet independently validated -- do not treat as fully "
              "verified until spot-checked against the live source, and "
              "watch specifically for silently-skipped speaker-label "
              "variants (this exact failure mode broke early Trump scrapes).",
    )