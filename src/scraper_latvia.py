"""
Scraper for Latvia (Prime Minister Andris Kulbergs).

Source: mk.gov.lv/en/articles, the Cabinet of Ministers' own English news
feed. This is a press-office feed, not a speech archive: his predecessor
Evika Siliņa had occasional dedicated "Address by .../ Speech by ..." pages
with verbatim first-person text, but Kulbergs (PM only since 28 May 2026)
has none yet -- every item about him so far is a third-person write-up
("Prime Minister Andris Kulbergs paid a working visit to Paris...") that
embeds one or more direct-quote paragraphs in his own words. Kept as
doc_type_audit=press_summary_of_speech (a dictionary category for exactly
this: a write-up ABOUT a speech/statement that quotes it, not the full text).
If a genuine "Address by"/"Speech by ... Kulbergs" page appears later, it
is picked up automatically and classed delivered_speech instead.

No dedicated listing exists for one person -- pages are read newest-first and
kept only when the title itself names him or opens with "Prime Minister"
(safe once we only look at dates from his own tenure onward).
"""

import re
import time
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from src.utils import clean_text, Speech
from src.text_processing import classify_as_speech, classify_content_type, in_date_range

BASE = "https://www.mk.gov.lv"
LIST_URL = BASE + "/en/articles"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
DELAY = 1.5
MAX_PAGES = 20

_ABOUT_HIM = re.compile(r"kulbergs|^prime minister", re.I)
_DELIVERED_SPEECH = re.compile(r"^(address|speech) by", re.I)

_MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}
# these press releases open with a dateline like "On Thursday, 20 August, ..."
# or "During a working visit to Kyiv on Monday, 24 August, ..." -- the actual
# event date, which can be weeks before the listing's publish date (this site
# republished a backlog of items under one date). Year is usually omitted;
# infer from the publish date's year, stepping back one year if that would
# put the event after publication (shouldn't happen here, but a safe guard).
_DATELINE = re.compile(
    r"on\s+(?:\w+day[,]?\s+)?(\d{1,2})\s*[-–]?\s*(?:\d{1,2})?\s+(" +
    "|".join(_MONTHS) + r")(?:,?\s+(\d{4}))?", re.I)


def _event_date(text: str, publish_date: str) -> str:
    m = _DATELINE.search(text[:200])
    if not m:
        return publish_date
    day, month, year = m.group(1), m.group(2), m.group(3)
    year = int(year) if year else int(publish_date[:4])
    try:
        import datetime as dt
        d = dt.date(year, _MONTHS[month.lower()], int(day))
    except ValueError:
        return publish_date
    if d.isoformat() > publish_date:
        d = d.replace(year=d.year - 1)
    return d.isoformat()


def _get(url: str, params: Optional[dict] = None, max_retries: int = 3):
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
            time.sleep(DELAY)
            if resp.status_code == 200:
                return resp
            print(f"  [warn] {url} status {resp.status_code} (attempt {attempt})")
        except Exception as e:
            print(f"  [warn] {url} raised {e!r} (attempt {attempt})")
        time.sleep(DELAY * attempt)
    return None


def _discover(start_date: str, end_date: str) -> List[dict]:
    items, page = [], 0
    while page < MAX_PAGES:
        resp = _get(LIST_URL, {"page": page})
        if resp is None:
            break
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("div.views-row")
        if not rows:
            break
        oldest_on_page = None
        for row in rows:
            a = row.select_one(".title a")
            t = row.select_one(".date time")
            if not a or not t:
                continue
            date_iso = t["datetime"][:10]
            oldest_on_page = date_iso if oldest_on_page is None else min(oldest_on_page, date_iso)
            title = clean_text(a.get_text(" "))
            if date_iso < start_date or date_iso > end_date or not _ABOUT_HIM.search(title):
                continue
            items.append({"url": BASE + a["href"], "title": title, "date": date_iso})
        print(f"  page {page}: {len(rows)} items, {len(items)} kept so far")
        if oldest_on_page and oldest_on_page < start_date:
            break
        page += 1
    return items


def parse_latvia(leader_config: dict, start_date: str, end_date: str,
                 limit: Optional[int] = None) -> List[Speech]:
    print("== Latvia (Kulbergs) -- mk.gov.lv press feed ==")
    items = _discover(start_date, end_date)
    print(f"  {len(items)} candidate items")
    speeches: List[Speech] = []
    for it in items:
        resp = _get(it["url"])
        if resp is None:
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        body = soup.select_one("div.cke_editable, div.text__text-content")
        if body is None:
            continue
        full_text = clean_text(body.get_text("\n", strip=True))
        if len(full_text) < 300:
            continue
        h1 = soup.find("h1")
        title = clean_text(h1.get_text(" ", strip=True)) if h1 else it["title"]
        is_verbatim = bool(_DELIVERED_SPEECH.match(title))
        event_date = _event_date(full_text, it["date"])
        if not in_date_range(event_date, start_date, end_date):
            continue
        note = (f"Sourced from mk.gov.lv (Cabinet of Ministers), English news feed. "
                f"Site published this on {it['date']}; date here is the event date given "
                f"in the article's own opening line, not the (later) publish date. " +
               ("Delivered speech, verbatim." if is_verbatim else
                "Third-person press write-up that embeds direct-quote paragraphs in his "
                "own words -- not a full verbatim transcript; no dedicated speech "
                "archive exists yet for this Prime Minister."))
        speeches.append(Speech(
            country=leader_config["country"], leader=leader_config["leader"], role=leader_config["role"],
            date=event_date, title=title, full_text=full_text, language="English",
            source_url=it["url"], likely_speech=classify_as_speech(title), content_type=classify_content_type(title),
            notes=note,
        ))
        if limit and len(speeches) >= limit:
            break
    return speeches
