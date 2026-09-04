"""
Scraper for Australia -- Anthony Albanese (Prime Minister since 23 May
2022, in office throughout the project's 2023-2026 window).

Source: pm.gov.au/media -- the PM's official media feed. Entirely live
(no bot detection, no JS rendering, no Wayback needed): the listing
paginates all the way back to 26 May 2022, three days after he took
office.

Structure (confirmed Sep 2026):
  - Listing: `/media?page=0..N`, 12 items/page, reverse-chronological.
  - Article: <h1> title; <time datetime="2026-09-01T03:15:47Z"> for the
    ISO date; `.field--name-field-media-type` categorizes each item
    (Speech / Transcript / Media statement / Doorstop interview / Media
    release / ...); body in the largest `.field--name-body` on the page
    (a smaller decoy with the same class sits in the site header).

SCOPE DECISION: "Media release" items are excluded -- like Canada's
news-releases/readouts, these are third-person staff-written
announcements ("All Northern Territory public schools will be fully
funded...", no first-person voice), not the PM's own words. Every other
media type is kept.

MULTI-SPEAKER TRANSCRIPTS: press conferences and doorstops are
transcribed with a speaker label on the first line of each turn
("ANTHONY ALBANESE, PRIME MINISTER:", then just "PRIME MINISTER:" for
his later turns; other ministers and "JOURNALIST:" for everyone else).
Where labels are present, only his turns are kept (labels stripped);
this is noted per row. Prepared "Speech" items carry no labels at all
and are kept in full.
"""

import re
import time
import datetime as dt
from typing import List, Optional

from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

from src.utils import clean_text, Speech
from src.text_processing import in_date_range

BASE = "https://www.pm.gov.au"
DELAY = 0.6
EXCLUDE_TYPES = {"media release"}
_LABEL_RE = re.compile(r"^([A-Z][A-Z0-9 .,'’&/-]{2,80}?):\s*(.*)$", re.S)


def _get(url: str, retries: int = 4) -> Optional[str]:
    for attempt in range(1, retries + 1):
        try:
            r = curl_requests.get(url, impersonate="chrome", timeout=45)
            time.sleep(DELAY)
            if r.status_code == 200:
                return r.text
            if r.status_code in (429, 502, 503, 504):
                time.sleep(4 * attempt)
        except Exception:
            time.sleep(3 * attempt)
    return None


def discover_urls(max_pages: int = 300) -> List[str]:
    seen = {}
    for page in range(max_pages):
        html = _get(f"{BASE}/media?page={page}")
        if html is None:
            break
        hrefs = re.findall(r'"(/media/[^"?#]+)"', html)
        if not hrefs:
            break
        for h in dict.fromkeys(hrefs):
            seen.setdefault(h, BASE + h)
        if page % 25 == 0:
            print(f"  listing page {page}: {len(seen)} unique urls so far")
    print(f"  discovery total: {len(seen)} unique /media URLs")
    return sorted(seen.values())


def _body_of(soup: BeautifulSoup):
    cands = soup.select(".node__content .field--name-body") or soup.select(".field--name-body")
    if not cands:
        return None
    return max(cands, key=lambda c: len(c.get_text(strip=True)))


def _extract_pm_text(body):
    """Return (text, is_multi_speaker). text keeps only the PM's own
    paragraphs (label stripped) when the transcript is multi-speaker,
    else the whole body. text is None if nothing usable was found."""
    paras = [p.get_text(" ", strip=True) for p in body.find_all("p")]
    paras = [p for p in paras if p]
    labeled = [(p, _LABEL_RE.match(p)) for p in paras]
    has_labels = sum(1 for _, m in labeled if m) >= 2  # >=2 to avoid a stray colon false-positive

    if not has_labels:
        text = clean_text("\n\n".join(paras))
        return (text if text else None), False

    kept = []
    for p, m in labeled:
        if not m:
            continue
        label = m.group(1).strip().upper()
        if label == "PRIME MINISTER" or label.startswith("ANTHONY ALBANESE"):
            kept.append(m.group(2).strip())
    text = clean_text("\n\n".join(k for k in kept if k))
    return (text if text else None), True


def _classify(media_type: str, title: str) -> tuple:
    mt = media_type.lower()
    tl = title.lower()
    if "interview" in mt or "interview" in tl:
        ctype = "Interview"
    elif "speech" in mt:
        ctype = "Speech"
    elif "statement" in mt or "release" in mt:
        ctype = "Statement"
    elif "transcript" in mt or "doorstop" in mt or "press conference" in tl:
        ctype = "Statement"
    else:
        ctype = "Other"
    likely = "yes" if ctype in ("Speech", "Statement") else "maybe"
    return likely, ctype


def parse_australia(leader_config: dict, start_date: str, end_date: str,
                    limit: Optional[int] = None) -> List[Speech]:
    print(f"== Australia ({leader_config['leader']}) ==")
    urls = discover_urls()
    speeches: List[Speech] = []
    stats = {"no_page": 0, "excluded_type": 0, "out_of_range": 0, "no_pm_text": 0}

    for i, url in enumerate(urls, 1):
        if i % 100 == 0:
            print(f"  [{i}/{len(urls)}] kept={len(speeches)} "
                  f"excluded={stats['excluded_type']} no_pm={stats['no_pm_text']}")
        html = _get(url)
        if html is None:
            stats["no_page"] += 1
            continue
        soup = BeautifulSoup(html, "html.parser")

        h1 = soup.find("h1")
        title = clean_text(h1.get_text(" ", strip=True)) if h1 else url
        time_el = soup.find("time", attrs={"datetime": True})
        date = time_el["datetime"][:10] if time_el else None
        if not in_date_range(date, start_date, end_date):
            stats["out_of_range"] += 1
            continue

        mt_el = soup.select_one(".field--name-field-media-type")
        media_type = mt_el.get_text(" ", strip=True) if mt_el else ""
        if media_type.strip().lower() in EXCLUDE_TYPES:
            stats["excluded_type"] += 1
            continue

        body = _body_of(soup)
        if body is None:
            continue
        text, multi = _extract_pm_text(body)
        if not text or len(text) < 60:
            stats["no_pm_text"] += 1
            continue

        likely, ctype = _classify(media_type, title)

        speeches.append(Speech(
            country=leader_config["country"],
            leader=leader_config["leader"],
            role=leader_config["role"],
            date=date,
            title=title,
            full_text=text,
            language="English",
            source_url=url,
            likely_speech=likely,
            content_type=ctype,
            notes=(f"Sourced live from pm.gov.au/media (PM's official media feed). "
                   f"Site media_type: '{media_type or 'n/a'}'. "
                   + ("Multi-speaker transcript -- only the Prime Minister's own "
                      "turns kept (speaker labels stripped); other speakers "
                      "(other ministers, journalists) excluded."
                      if multi else
                      "Single-speaker item -- kept in full.")),
        ))
        if limit and len(speeches) >= limit:
            break

    print(f"\n  Australia done: {len(speeches)} kept | no_page={stats['no_page']} "
          f"excluded_type={stats['excluded_type']} out_of_range={stats['out_of_range']} "
          f"no_pm_text={stats['no_pm_text']}")
    return speeches
