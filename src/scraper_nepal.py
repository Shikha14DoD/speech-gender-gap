"""
Scraper for Nepal: K. P. Sharma Oli, Sushila Karki, Balendra Shah (Prime Ministers).

Source: Ministry of Foreign Affairs (mofa.gov.np) statement pages, read from the
Internet Archive.  The live ministry site returned a server-side 503 outage
when we tried it, and the Archive holds copies of its 2025-2026 pages, so this
is Wayback-first like the Brazil and Sri Lanka scrapers.

How it works
  1. One Archive CDX query per year lists every archived /content/<id>/<slug>
     page (with the capture timestamp).
  2. Slugs that look like statements / addresses / remarks / briefings are kept
     as candidates (the ministry also publishes press releases and notices).
  3. Each candidate is fetched from the Archive; it is kept only if its title
     names one of the three Prime Ministers (or says "Prime Minister of Nepal"),
     which drops the Foreign Minister's and spokesperson's statements.
  4. The speaker is set from the name in the title; if the title only says
     "Prime Minister", from the tenure dates below.

Tenures (2024-2026): Oli PM 15 Jul 2024 - 9 Sep 2025; Karki (interim)
12 Sep 2025 - 26 Mar 2026; Shah from 27 Mar 2026.

This source only carries statements made abroad or to the diplomatic corps, so
coverage is thin; domestic addresses are not on it.
"""

import json
import re
import time
from typing import List, Optional

from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

from src.utils import clean_text, Speech
from src.text_processing import in_date_range, classify_as_speech, classify_content_type
from src.scraper_brazil import _cget

CDX = "https://web.archive.org/cdx/search/cdx"
WB = "https://web.archive.org/web"
PREFIX = "mofa.gov.np/content/*"
DELAY = 1.0

_CANDIDATE_SLUG = re.compile(
    r"statement|address|remarks|speech|message|keynote|intervention|greeting|briefing|diplomatic",
    re.I)

# (name pattern in title, leader as written in Ginette's table)
_LEADERS = [
    (re.compile(r"oli\b|k\.?\s*p\.?\s*sharma", re.I), "K. P. Sharma Oli"),
    (re.compile(r"karki", re.I), "Sushila Karki"),
    (re.compile(r"balen|balendra|\bshah\b", re.I), "Balendra Shah"),
]
_TENURES = [  # (start, end, leader)
    ("2024-07-15", "2025-09-11", "K. P. Sharma Oli"),
    ("2025-09-12", "2026-03-26", "Sushila Karki"),
    ("2026-03-27", "2099-12-31", "Balendra Shah"),
]
_MONTHS = ("January|February|March|April|May|June|July|August|September|October|"
           "November|December")
_TITLE_DATE = re.compile(rf"(\d{{1,2}})\s+({_MONTHS})\s+(20\d\d)", re.I)
_POST_DATE = re.compile(rf"({_MONTHS})\s+(\d{{1,2}}),\s+(20\d\d)", re.I)
_MONTH_NUM = {m.lower(): i for i, m in enumerate(_MONTHS.split("|"), 1)}


def _iso(d: int, month: str, y: int) -> str:
    return f"{y:04d}-{_MONTH_NUM[month.lower()]:02d}-{int(d):02d}"


def _discover(start_date: str) -> List[tuple]:
    seen, out = set(), []
    for year in range(int(start_date[:4]), 2027):
        q = (f"{CDX}?url={PREFIX}&output=json&collapse=urlkey&fl=original,timestamp"
             f"&filter=statuscode:200&limit=3000&from={year}0101&to={year}1231")
        resp = None
        for attempt in range(3):
            try:
                resp = curl_requests.get(q, impersonate="chrome", timeout=180)
                if resp.status_code == 200:
                    break
            except Exception as e:
                print(f"  [warn] CDX {year} raised {e!r} (attempt {attempt + 1})")
            time.sleep(5 * (attempt + 1))
        if resp is None or resp.status_code != 200 or not resp.text.strip():
            print(f"  [warn] no CDX result for {year}")
            continue
        rows = json.loads(resp.text)[1:]
        added = 0
        for url, ts in rows:
            m = re.search(r"/content/(\d+)/([^/]*)/?$", url)
            if not m or m.group(1) in seen or not _CANDIDATE_SLUG.search(m.group(2)):
                continue
            seen.add(m.group(1))
            out.append((url.replace("http://", "https://"), ts))
            added += 1
        print(f"  CDX {year}: {len(rows)} archived content pages, +{added} statement-like")
    return out


def _leader_for(title: str, date_iso: str) -> Optional[str]:
    for pat, name in _LEADERS:
        if pat.search(title):
            return name
    if re.search(r"prime minister", title, re.I):
        for start, end, name in _TENURES:
            if start <= date_iso <= end:
                return name
    return None


def parse_nepal(leader_config: dict, start_date: str, end_date: str,
                limit: Optional[int] = None) -> List[Speech]:
    print("== Nepal (Oli / Karki / Shah) -- mofa.gov.np via Wayback ==")
    cands = _discover(start_date)
    print(f"  {len(cands)} candidate pages")
    speeches: List[Speech] = []
    for n, (url, ts) in enumerate(cands, 1):
        r = _cget(f"{WB}/{ts}id_/{url}", 60, retries=2)
        time.sleep(DELAY)
        if r is None:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        title = clean_text(re.sub(r"\s*\|\s*Ministry Of Foreign Affairs\s*$", "",
                                  soup.title.get_text(strip=True))) if soup.title else ""
        body = soup.select_one("div.details__desc")
        if not title or body is None:
            continue
        post = soup.select_one("div.meta__group")
        pm = _POST_DATE.search(post.get_text(" ", strip=True)) if post else None
        post_iso = _iso(pm.group(2), pm.group(1), int(pm.group(3))) if pm else None
        tm = _TITLE_DATE.search(title)
        date_iso = _iso(tm.group(1), tm.group(2), int(tm.group(3))) if tm else post_iso
        if not date_iso or not in_date_range(date_iso, start_date, end_date):
            continue
        who = _leader_for(title, date_iso)
        if who is None:
            continue
        paragraphs = [clean_text(p.get_text(separator=" ")) for p in body.find_all(["p", "li", "div"])
                      if not p.find(["p", "li", "div"])]
        full_text = clean_text("\n\n".join(p for p in paragraphs if p)) or clean_text(body.get_text("\n"))
        if len(full_text) < 400:
            continue
        speeches.append(Speech(
            country=leader_config["country"],
            leader=who,
            role=leader_config["role"],
            date=date_iso,
            title=title,
            full_text=full_text,
            language="English",
            source_url=url,
            likely_speech=classify_as_speech(title),
            content_type=classify_content_type(title),
            notes=(f"Sourced from mofa.gov.np (Ministry of Foreign Affairs) via the Internet "
                   f"Archive capture {ts}. Date is the statement date from the title where "
                   f"given, else the ministry's posting date ({post_iso}). Speaker taken from "
                   f"the name in the title, or from Prime Ministerial tenure dates."),
        ))
        if n % 20 == 0:
            print(f"  fetched {n}/{len(cands)}, kept {len(speeches)}")
        if limit and len(speeches) >= limit:
            break
    return speeches
