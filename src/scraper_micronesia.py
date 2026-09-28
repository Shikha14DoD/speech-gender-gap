"""
Scraper for the Federated States of Micronesia (President Wesley Simina).

The official government site (gov.fm) has NO verbatim speeches -- even its
"President addresses the UN General Assembly" post is a third-person news
write-up with a few quoted lines, not the actual text. Two other official
sources fill the gap:

  1. gadebate.un.org -- the UN's own General Assembly "General Debate"
     archive. Every member state's national statement, as submitted to the
     UN, is published there as a PDF, one per session. This is a UN
     publication of the government's own verbatim text, not a third party's
     account of it.
  2. unmission.fm -- the FSM Permanent Mission to the UN's own site (WordPress,
     open REST API). Most of its "UN statement" posts are by the ambassador;
     only posts whose title names the President are kept.
  3. forumsec.org (Pacific Islands Forum Secretariat) -- publishes verbatim
     remarks by Pacific leaders at Forum-organised events. Its `/publications`
     listing has no working search or filter, so pages are found by web
     search rather than crawled; a short, hand-verified list of his own
     remarks (not joint communiques, which are collective texts) is kept
     below and re-checked by title/date before being trusted.
"""

import datetime as dt
import re
import time
from typing import List, Optional

import pymupdf
import requests
from bs4 import BeautifulSoup

from src.utils import clean_text, Speech
from src.text_processing import classify_as_speech, classify_content_type, in_date_range

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# UNGA session number -> the September it opened (session N opens in year
# 1945+N); only the sessions inside this project's date range are fetched.
_UNGA_SESSIONS = {79: 2024, 80: 2025}
_UNGA_PDF = "https://gadebate.un.org/sites/default/files/gastatements/{session}/fm_en.pdf"

# forumsec.org has no working search/filter (confirmed: `?s=` and the WP REST
# API are both no-ops there), so candidates were found via web search and are
# verified (title names Simina, date in range) before being kept, same as
# any other discovered URL. "delivers-statement-unga79" is deliberately left
# out here -- it's the same 26 Sept 2024 UNGA79 speech already covered by the
# UN's own gadebate.un.org PDF (96% word overlap, confirmed) -- that copy wins.
_FORUMSEC_CANDIDATES = [
    "https://forumsec.org/publications/remarks-fsm-president-simina-addresses-unga79-summit-future",
    "https://forumsec.org/publications/remarks-he-wesley-simina-president-fsm-small-island-states-leaders-meeting",
]


def _get(url: str, max_retries: int = 3):
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=40)
            time.sleep(1.0)
            if resp.status_code == 200:
                return resp
            print(f"  [warn] {url} status {resp.status_code} (attempt {attempt})")
        except Exception as e:
            print(f"  [warn] {url} raised {e!r} (attempt {attempt})")
        time.sleep(2 * attempt)
    print(f"  [error] giving up on {url}")
    return None


def _unga_speeches(start_date: str, end_date: str) -> List[Speech]:
    out = []
    for session, year in _UNGA_SESSIONS.items():
        url = _UNGA_PDF.format(session=session)
        resp = _get(url)
        if resp is None:
            continue
        doc = pymupdf.open(stream=resp.content, filetype="pdf")
        text = clean_text("\n".join(p.get_text() for p in doc))
        if len(text) < 400:
            continue
        m = re.search(r"New York,\s*(\d{1,2})\s+(\w+)\s+(20\d\d)", text)
        date_iso = None
        if m:
            try:
                import datetime as dt
                date_iso = dt.datetime.strptime(" ".join(m.groups()), "%d %B %Y").date().isoformat()
            except ValueError:
                pass
        date_iso = date_iso or f"{year}-09-26"   # UNGA general debate is always late Sept
        if not in_date_range(date_iso, start_date, end_date):
            continue
        out.append(Speech(
            country="Federated States of Micronesia",
            leader="Wesley Simina",
            role="President",
            date=date_iso,
            title=f"Statement by H.E. Wesley W. Simina, President of the Federated States of "
                  f"Micronesia, at the {session}th Session of the UN General Assembly General Debate",
            full_text=text,
            language="English",
            source_url=url,
            likely_speech="yes",
            content_type="Speech",
            notes=("Sourced from gadebate.un.org, the UN General Assembly's own archive of "
                   "member states' General Debate statements -- the government's verbatim "
                   "text as submitted to and published by the UN, not a news account of it."),
        ))
    return out


_MISSION_API = "https://unmission.fm/wp-json/wp/v2/posts"
_PRESIDENT_TITLE = re.compile(r"president (wesley|simina)|simina", re.I)


def _mission_speeches(start_date: str, end_date: str) -> List[Speech]:
    out, page = [], 1
    while True:
        try:
            resp = requests.get(_MISSION_API, headers=HEADERS, timeout=40, params={
                "search": "President Simina", "per_page": 50, "page": page,
                "after": f"{start_date}T00:00:00", "_fields": "id,date,title,link,content"})
            time.sleep(1.0)
        except Exception as e:
            print(f"  [warn] unmission.fm request failed: {e!r}")
            break
        if resp.status_code != 200 or not resp.json():
            break
        for post in resp.json():
            title = clean_text(BeautifulSoup(post["title"]["rendered"], "html.parser").get_text(" "))
            if not _PRESIDENT_TITLE.search(title):
                continue
            body = BeautifulSoup(post["content"]["rendered"], "html.parser")
            paragraphs = [clean_text(p.get_text(" ")) for p in body.find_all(["p", "li"])
                          if p.get_text(strip=True)]
            text = clean_text("\n\n".join(paragraphs))
            text = re.sub(r"^\s*Video:\s*\S+\s*", "", text)           # drop the embedded-video line
            if len(text) < 400:
                # short statements exist (e.g. a 211-word intervention) -- keep if real text
                if len(text) < 250:
                    continue
            m = (re.search(r"New York,\s*(\d{1,2})\s+(\w+)\s+(20\d\d)", text)
                 or re.match(r"\s*(\d{1,2})\s+(\w+)\s+(20\d\d)", text))
            try:
                date_iso = dt.datetime.strptime(" ".join(m.groups()[-3:]), "%d %B %Y").date().isoformat()
            except Exception:
                date_iso = post["date"][:10]
            if not in_date_range(date_iso, start_date, end_date):
                continue
            out.append(Speech(
                country="Federated States of Micronesia", leader="Wesley Simina", role="President",
                date=date_iso, title=title, full_text=text, language="English",
                source_url=post["link"], likely_speech=classify_as_speech(title),
                content_type=classify_content_type(title),
                notes=("Sourced from unmission.fm, the FSM Permanent Mission to the UN's own site "
                       "(President's statements only; the ambassador's are not included)."),
            ))
        page += 1
    return out


def _dedupe(speeches: List[Speech]) -> List[Speech]:
    """Same speech can appear on several sources. Keep the highest-priority copy
    (UN's own PDF > the FSM UN Mission site > forumsec.org) when two rows within a
    few days share >=60% of their distinct 5+-letter words."""
    def rank(s):
        return 0 if "gadebate.un.org" in s.source_url else 1 if "unmission.fm" in s.source_url else 2
    def words(t):
        return set(re.findall(r"[a-z]{5,}", t.lower()))
    kept: List[Speech] = []
    for s in sorted(speeches, key=rank):
        ws = words(s.full_text)
        dup = False
        for k in kept:
            d = abs((dt.date.fromisoformat(s.date) - dt.date.fromisoformat(k.date)).days)
            wk = words(k.full_text)
            if d <= 4 and ws and wk and len(ws & wk) / len(ws | wk) >= 0.60:
                print(f"  [dedupe] dropping {s.source_url.split('/')[2]} copy of: {k.title[:60]}")
                dup = True
                break
        if not dup:
            kept.append(s)
    return sorted(kept, key=lambda s: s.date)


def _forumsec_speeches(start_date: str, end_date: str) -> List[Speech]:
    out = []
    for url in _FORUMSEC_CANDIDATES:
        resp = _get(url)
        if resp is None:
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        h1 = soup.find("h1")
        title = clean_text(h1.get_text(" ", strip=True)) if h1 else ""
        if "simina" not in title.lower():
            print(f"  [warn] skipping {url}: title doesn't name Simina")
            continue
        date_tag = soup.find(class_=re.compile("date", re.I))
        date_iso = None
        if date_tag:
            m = re.match(r"(\d{1,2})\s+(\w+)\s+(20\d\d)", date_tag.get_text(strip=True))
            if m:
                import datetime as dt
                try:
                    date_iso = dt.datetime.strptime(m.group(0), "%d %B %Y").date().isoformat()
                except ValueError:
                    pass
        if not date_iso or not in_date_range(date_iso, start_date, end_date):
            continue
        body = max(soup.find_all(["div"], class_=re.compile("body-copy|content", re.I)),
                   key=lambda e: len(e.get_text()), default=None)
        if body is None:
            continue
        full_text = clean_text(body.get_text("\n", strip=True))
        if len(full_text) < 400:
            continue
        out.append(Speech(
            country="Federated States of Micronesia",
            leader="Wesley Simina",
            role="President",
            date=date_iso,
            title=re.sub(r"^REMARKS:\s*", "", title, flags=re.I),
            full_text=full_text,
            language="English",
            source_url=url,
            likely_speech=classify_as_speech(title),
            content_type=classify_content_type(title),
            notes=("Sourced from forumsec.org (Pacific Islands Forum Secretariat), which "
                   "publishes verbatim remarks by Pacific leaders at Forum events. The "
                   "official gov.fm site has no verbatim speeches, only news write-ups."),
        ))
    return out


def parse_micronesia(leader_config: dict, start_date: str, end_date: str,
                     limit: Optional[int] = None) -> List[Speech]:
    print("== Federated States of Micronesia (Simina) -- UN General Debate + forumsec.org ==")
    speeches = _dedupe(_unga_speeches(start_date, end_date)
                       + _mission_speeches(start_date, end_date)
                       + _forumsec_speeches(start_date, end_date))
    print(f"  {len(speeches)} speeches")
    if limit:
        speeches = speeches[:limit]
    return speeches
