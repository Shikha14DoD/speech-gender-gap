"""
Scraper for New Zealand -- the three Prime Ministers of the 2023-2026
window, all from beehive.govt.nz (the NZ Government's official site):

  Jacinda Ardern    (F)  -> 2023-01-25   (Q3606816)
  Chris Hipkins     (M)  2023-01-25 .. 2023-11-27   (Q5106890)
  Christopher Luxon (M)  2023-11-27 ..   (Q74370310)

Native English -- no translation step.

SOURCE NOTES (confirmed Sep 2026):
  - The live `/speeches` listing only pages back to ~Dec 2023 (the
    current government) and pre-Luxon speech URLs now 404. So discovery
    is via the Wayback Machine CDX API for `beehive.govt.nz/speech/*`,
    supplemented by the live listing for recent completeness.
  - Each speech is fetched LIVE first; if the live page is gone (404 /
    no speech node) it is pulled from the newest good Wayback snapshot.
  - beehive slugs carry no date, so every candidate must be fetched to
    read its date and speaker -- there is no cheap pre-filter.
  - Article: <h1> = title; speaker in an <a href="/minister/..."> inside
    the `.node--type-speech` node (falls back to the "Rt Hon X - ..."
    prefix on the h1); date in `.field--name-field-date` (format
    "5 February 2024"); body in `.node--type-speech .field--name-body`.
"""

import re
import json
import time
import datetime as dt
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

from src.utils import clean_text, Speech
from src.text_processing import in_date_range, classify_as_speech, classify_content_type

CDX = "https://web.archive.org/cdx/search/cdx"
WB = "https://web.archive.org/web"
LIVE = "https://www.beehive.govt.nz"
DELAY = 0.8

PMS = {
    "ardern": ("Jacinda Ardern", None, "2023-01-25"),
    "hipkins": ("Chris Hipkins", "2023-01-25", "2023-11-27"),
    "luxon": ("Christopher Luxon", "2023-11-27", None),
}


def _cget(url: str, timeout: int = 45, retries: int = 4):
    for attempt in range(1, retries + 1):
        try:
            r = curl_requests.get(url, impersonate="chrome", timeout=timeout)
            time.sleep(DELAY)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 503, 502, 504):
                time.sleep(4 * attempt)
        except Exception:
            time.sleep(3 * attempt)
    return None


# ---------------------------------------------------------------- discovery
def _norm(u: str) -> str:
    u = u.split("?")[0].split("#")[0]
    u = u.replace("http://", "https://").replace("https://www.", "https://")
    u = re.sub(r"%E2%80%8B|%E2%80%8C|%E2%80%8D|%EF%BB%BF", "", u)  # zero-width junk
    return u.rstrip("/").lower()


_MINISTER_PAGES = [
    "/minister/rt-hon-jacinda-ardern",
    "/minister/rt-hon-chris-hipkins",
    "/minister/rt-hon-christopher-luxon",
]


def _listing(path: str, max_pages: int, seen: dict, label: str):
    got = 0
    for page in range(0, max_pages):
        r = _cget(f"{LIVE}{path}?page={page}", timeout=40)
        if r is None:
            break
        hrefs = re.findall(r'href="(/speech/[^"#?]+)"', r.text)
        if not hrefs and page > 0:
            break
        for h in hrefs:
            k = _norm(LIVE + h)
            if k not in seen:
                seen[k] = LIVE + h
                got += 1
    print(f"  {label}: +{got} speech URLs")


def discover_urls() -> List[str]:
    seen: dict = {}
    # 1. the whole-government speeches listing (current govt, ~Dec 2023 on)
    _listing("/speeches", 30, seen, "/speeches listing")
    # 2. each PM's own bio-page feed (all three still live)
    for mp in _MINISTER_PAGES:
        _listing(mp, 15, seen, mp)
    # 3. Wayback CDX supplement for beehive.govt.nz/speech/* in 2023 --
    #    the transition year the live listings cover worst. Most hits are
    #    other ministers (filtered out on fetch); accept the extra work
    #    for completeness of Hipkins / Ardern / early-Luxon.
    for year in (2023,):
        q = (f"{CDX}?url=beehive.govt.nz/speech/*&output=json&collapse=urlkey"
             f"&fl=original&filter=statuscode:200&from={year}0101&to={year}1231&limit=40000")
        r = _cget(q, timeout=150)
        if r is None or not r.text.strip():
            print(f"  [warn] CDX {year} failed")
            continue
        try:
            rows = json.loads(r.text)[1:]
        except json.JSONDecodeError:
            continue
        add = 0
        for row in rows:
            k = _norm(row[0])
            if k not in seen:
                seen[k] = row[0].split("?")[0].replace("http://", "https://")
                add += 1
        print(f"  CDX {year}: {len(rows)} rows (+{add} new)")
    print(f"  discovery total: {len(seen)} unique speech URLs")
    return sorted(seen.values())


# ---------------------------------------------------------------- fetch
def _fetch(url: str) -> Tuple[Optional[BeautifulSoup], str]:
    r = _cget(url, timeout=40, retries=2)
    if r is not None:
        s = BeautifulSoup(r.text, "html.parser")
        if s.select_one(".node--type-speech"):
            return s, "live"
    # wayback fallback
    q = (f"{CDX}?url={url}&output=json&fl=timestamp&filter=statuscode:200"
         f"&collapse=digest&limit=40")
    r = _cget(q, timeout=90)
    if r is None or not r.text.strip():
        return None, ""
    try:
        stamps = sorted({row[0] for row in json.loads(r.text)[1:]}, reverse=True)
    except json.JSONDecodeError:
        return None, ""
    for ts in stamps[:6]:
        rr = _cget(f"{WB}/{ts}id_/{url}", timeout=60, retries=2)
        if rr is None:
            continue
        s = BeautifulSoup(rr.text, "html.parser")
        node = s.select_one(".node--type-speech")
        if node and node.select_one(".field--name-body"):
            return s, f"wayback:{ts}"
    return None, ""


# ---------------------------------------------------------------- parse
_MONTHS = ("january february march april may june july august september "
          "october november december").split()


def _parse_date(text: str) -> Optional[str]:
    m = re.search(r"(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s+(20\d{2})", text, re.I)
    if not m:
        return None
    try:
        return dt.date(int(m.group(3)), _MONTHS.index(m.group(2).lower()) + 1,
                       int(m.group(1))).isoformat()
    except ValueError:
        return None


def _speaker(node, soup, title: str) -> str:
    a = node.select_one("a[href*='/minister/']")
    if a and a.get_text(strip=True):
        return a.get_text(strip=True)
    m = re.match(r"\s*((?:Rt Hon|Hon)\s+[A-Z][\w'’-]+(?:\s+[A-Z][\w'’-]+){0,2})\s*[-–]", title)
    if m:
        return m.group(1)
    head = node.get_text(" ", strip=True)[:400]
    for full, _s, _e in PMS.values():
        if full.split()[-1] in head and full.split()[0] in head:
            return full
    return ""


def _which_pm(speaker: str, role_text: str, date: Optional[str]) -> Optional[str]:
    sp = speaker.lower()
    for key, (full, start, end) in PMS.items():
        if full.split()[-1].lower() in sp:
            return key
    # no name match -- if it's clearly a PM speech, attribute by date
    if "prime minister" in role_text.lower() and date:
        for key, (full, start, end) in PMS.items():
            if (start is None or date >= start) and (end is None or date < end):
                return key
    return None


def parse_newzealand(leader_config: dict, start_date: str, end_date: str,
                     limit: Optional[int] = None) -> List[Speech]:
    print("== New Zealand (Ardern / Hipkins / Luxon) ==")
    urls = discover_urls()
    speeches: List[Speech] = []
    stats = {"fetched": 0, "no_page": 0, "not_pm": 0, "out_of_range": 0}

    for i, url in enumerate(urls, 1):
        if i % 50 == 0:
            print(f"  [{i}/{len(urls)}] kept={len(speeches)} "
                  f"no_page={stats['no_page']} not_pm={stats['not_pm']}")
        soup, src = _fetch(url)
        if soup is None:
            stats["no_page"] += 1
            continue
        stats["fetched"] += 1
        node = soup.select_one(".node--type-speech")
        h1 = soup.find("h1")
        title = clean_text(h1.get_text(" ", strip=True)) if h1 else url

        date_el = node.select_one(".field--name-field-date, time, .date")
        date_text = date_el.get_text(" ", strip=True) if date_el else node.get_text(" ", strip=True)[:200]
        date = _parse_date(date_text)

        speaker = _speaker(node, soup, title)
        role_text = ""
        rl = node.find(string=re.compile(r"Prime Minister", re.I))
        if rl:
            role_text = "Prime Minister"
        pm = _which_pm(speaker, role_text, date)
        if pm is None:
            stats["not_pm"] += 1
            continue

        full_name, tstart, tend = PMS[pm]
        if date:
            if tstart and date < tstart:
                stats["not_pm"] += 1
                continue
            if tend and date >= tend:
                stats["not_pm"] += 1
                continue
        if not in_date_range(date, start_date, end_date):
            stats["out_of_range"] += 1
            continue

        body_el = node.select_one(".field--name-body")
        body = clean_text(body_el.get_text("\n")) if body_el else ""
        body = re.sub(r"\n\s*\n+", "\n\n", body).strip()
        if len(body) < 60:
            continue

        speeches.append(Speech(
            country="New Zealand",
            leader=full_name,
            role="Prime Minister",
            date=date,
            title=title,
            full_text=body,
            language="English",
            source_url=url,
            likely_speech=classify_as_speech(title),
            content_type=classify_content_type(title),
            notes=(f"Sourced from beehive.govt.nz (NZ Government official site), "
                   f"{'live page' if src == 'live' else 'recovered from ' + src} "
                   f"-- the live /speeches listing drops pre-Luxon content. "
                   f"Speaker as published: '{speaker or 'n/a'}'. Native English, "
                   f"no translation."),
        ))
        if limit and len(speeches) >= limit:
            break

    by = {}
    for s in speeches:
        by[s.leader] = by.get(s.leader, 0) + 1
    print(f"\n  NZ done: {len(speeches)} PM speeches {by} | "
          f"fetched={stats['fetched']} no_page={stats['no_page']} "
          f"not_pm={stats['not_pm']} out_of_range={stats['out_of_range']}")
    return speeches
