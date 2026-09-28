"""
Scraper for the Marshall Islands (President David Kabua).

Kabua left office 3 January 2024, so his usable window inside this project's
2023-2026 span is only 2023. No listing/archive route exists for him:
  - the RMI Permanent Mission to the UN's own "statements_speeches" page
    (un.int/marshallislands) is abandoned -- its newest entry is from 2013.
  - the Office of the President's site (rmigov.com) has no working category
    or REST API listing, and is behind a Cloudflare check that only some
    individual post URLs pass (curl_cffi Chrome impersonation gets through
    on those, not on the homepage) -- id-range probing around known posts
    turned up meeting notices and courtesy calls, not more speeches.

Two verified sources are used, listed explicitly rather than discovered:
  1. gadebate.un.org -- the UN's own General Assembly General Debate archive
     (see scraper_micronesia.py for the same pattern): his 78th session
     (2023) statement, the government's verbatim text as published by the UN.
  2. rmigov.com -- the Office of the President's own site, one confirmed post
     (opening remarks to the Marshall Islands Mayors Association conference).

Given Ginette wants him as a comparator ("add what we can" for a thin
country), this is a small, honestly-labelled 2-row set rather than a fuller
scrape -- there is no larger archive to find.
"""

import time
from typing import List, Optional

import pymupdf
import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

from src.utils import clean_text, Speech
from src.text_processing import classify_as_speech, classify_content_type, in_date_range

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

_KNOWN_SOURCES = [
    {"kind": "un_pdf", "date": "2023-09-20",
     "url": "https://gadebate.un.org/sites/default/files/gastatements/78/mh_en.pdf",
     "title": "Statement by H.E. Mr. David Kabua, President of the Republic of the Marshall "
              "Islands, at the 78th Session of the UN General Assembly General Debate"},
    {"kind": "rmigov", "date": "2023-07-19",
     "url": "https://rmigov.com/?p=683",
     "title": None},   # taken from the page's own <title>
]


def _un_pdf_speech(src: dict, leader_config: dict) -> Optional[Speech]:
    resp = requests.get(src["url"], headers=HEADERS, timeout=40)
    if resp.status_code != 200:
        print(f"  [warn] {src['url']} status {resp.status_code}")
        return None
    doc = pymupdf.open(stream=resp.content, filetype="pdf")
    text = clean_text("\n".join(p.get_text() for p in doc))
    if len(text) < 400:
        return None
    return Speech(
        country=leader_config["country"], leader=leader_config["leader"], role=leader_config["role"],
        date=src["date"], title=src["title"], full_text=text, language="English",
        source_url=src["url"], likely_speech="yes", content_type="Speech",
        notes=("Sourced from gadebate.un.org, the UN General Assembly's own archive of "
               "member states' General Debate statements -- the government's verbatim text "
               "as submitted to and published by the UN."),
    )


def _rmigov_speech(src: dict, leader_config: dict) -> Optional[Speech]:
    # this site's Cloudflare check is intermittent -- the same URL 403s or
    # 200s from one request to the next, so retry a few times before giving up
    resp = None
    for attempt in range(4):
        resp = curl_requests.get(src["url"], impersonate="chrome", timeout=30, verify=False)
        if resp.status_code == 200:
            break
        time.sleep(3)
    if resp is None or resp.status_code != 200:
        print(f"  [warn] {src['url']} status {resp.status_code if resp else 'no response'}")
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    title = clean_text(soup.title.get_text(strip=True)) if soup.title else (src["title"] or "")
    title = title.replace(" - Office of the President & Cabinet (RMI)", "").strip()
    body = max(soup.find_all(["div", "article"]),
              key=lambda e: sum(len(p.get_text()) for p in e.find_all("p", recursive=False)), default=None)
    if body is None:
        return None
    text = clean_text("\n\n".join(p.get_text(" ") for p in body.find_all("p", recursive=False)))
    if len(text) < 400:
        return None
    return Speech(
        country=leader_config["country"], leader=leader_config["leader"], role=leader_config["role"],
        date=src["date"], title=title, full_text=text, language="English",
        source_url=src["url"], likely_speech=classify_as_speech(title), content_type=classify_content_type(title),
        notes=("Sourced from rmigov.com, the Office of the President & Cabinet's own site. "
               "No working listing/search on this site -- URL found via web search and "
               "verified (real speech content, correct date) before use."),
    )


def parse_marshallislands(leader_config: dict, start_date: str, end_date: str,
                          limit: Optional[int] = None) -> List[Speech]:
    print("== Marshall Islands (Kabua) -- UN General Debate + Office of the President ==")
    speeches: List[Speech] = []
    for src in _KNOWN_SOURCES:
        if not in_date_range(src["date"], start_date, end_date):
            continue
        fn = _un_pdf_speech if src["kind"] == "un_pdf" else _rmigov_speech
        sp = fn(src, leader_config)
        if sp is not None:
            speeches.append(sp)
        if limit and len(speeches) >= limit:
            break
    print(f"  {len(speeches)} speeches")
    return speeches
