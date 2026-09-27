"""
Scraper for Thailand: Srettha Thavisin and Anutin Charnvirakul (Prime Ministers).

Source: the Ministry of Foreign Affairs' "Speeches" category (mfa.go.th), NOT
the government's own thaigov.go.th, which serves automated requests a
Cloudflare bot-challenge page. mfa.go.th works with plain `requests` and each
listing/article page embeds its data as JSON in a `__NEXT_DATA__` script tag,
so parsing is exact rather than heuristic.

Two things this scraper has to get right that a simple keyword scrape would
miss:
  1. The listing's own pagination isn't in the page's HTML (it's rendered
     client-side); the actual page-2+ URL is `?p=<n>` on the SAME path
     (found by trial: `/page/2` and `/2` both silently return page 1's data).
  2. Many titles just say "Prime Minister" with no name -- the real speaker
     has to be resolved from Thailand's 2023-2026 PM tenure dates. Paetongtarn
     Shinawatra held the office between Srettha and Anutin but is NOT one of
     the leaders in scope for this batch, so any item that resolves to her
     tenure window is dropped rather than mis-attributed to her neighbours.
"""

import re
import time
from typing import List, Optional

import pymupdf
import requests
from bs4 import BeautifulSoup

from src.utils import clean_text, Speech
from src.text_processing import in_date_range, classify_as_speech, classify_content_type

CATEGORY = "https://www.mfa.go.th/en/content-category/5d5bcb4e15e39c3060006848"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
NEXT_DATA = re.compile(r'id="__NEXT_DATA__"\s*type="application/json">(.*?)</script>', re.S)
DELAY = 1.0

# Thailand PM tenures relevant to this project's window (2024-2026)
_TENURES = [
    ("2023-08-22", "2024-08-14", "Srettha Thavisin"),
    ("2024-08-15", "2025-08-29", None),       # Paetongtarn Shinawatra -- out of scope
    ("2025-08-30", "2025-09-06", None),       # brief caretaker gap
    ("2025-09-07", "2099-12-31", "Anutin Charnvirakul"),
]
_NAMED = [
    (re.compile(r"srettha", re.I), "Srettha Thavisin"),
    (re.compile(r"anutin", re.I), "Anutin Charnvirakul"),
    (re.compile(r"paetongtarn", re.I), None),   # explicit mention -- also out of scope
]


def _get(url: str, params: Optional[dict] = None, max_retries: int = 3):
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=40)
            time.sleep(DELAY)
            if resp.status_code == 200:
                m = NEXT_DATA.search(resp.text)
                if m:
                    import json
                    return json.loads(m.group(1))
            print(f"  [warn] {url} status {resp.status_code} (attempt {attempt})")
        except Exception as e:
            print(f"  [warn] {url} raised {e!r} (attempt {attempt})")
        time.sleep(DELAY * attempt * 2)
    print(f"  [error] giving up on {url}")
    return None


def _leader_for(title: str, date_iso: str) -> Optional[str]:
    for pat, name in _NAMED:
        if pat.search(title):
            return name
    if (re.search(r"\bprime minister\b", title, re.I)
            and not re.search(r"deputy prime minister|special envoy", title, re.I)):
        for start, end, name in _TENURES:
            if start <= date_iso <= end:
                return name
    return None


def _pdf_text(url: str) -> str:
    """Some speeches are attached only as a PDF (no inline HTML body)."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=40)
        time.sleep(DELAY)
        if resp.status_code != 200:
            return ""
        doc = pymupdf.open(stream=resp.content, filetype="pdf")
        return clean_text("\n".join(p.get_text() for p in doc))
    except Exception as e:
        print(f"    [warn] PDF fetch failed for {url}: {e!r}")
        return ""


def _discover() -> List[dict]:
    first = _get(CATEGORY, {"p": 1})
    if not first:
        return []
    page_data = first["props"]["pageProps"]["components_meta"]["page"]["data"]
    total_pages = page_data["pagination"]["total_page"]
    items = list(page_data["items"])
    print(f"  page 1/{total_pages}: {len(items)} items")
    for p in range(2, total_pages + 1):
        data = _get(CATEGORY, {"p": p})
        if not data:
            continue
        pd = data["props"]["pageProps"]["components_meta"]["page"]["data"]
        items += pd["items"]
        print(f"  page {p}/{total_pages}: {len(pd['items'])} items")
    seen, uniq = set(), []
    for it in items:
        if it["url"] not in seen:
            seen.add(it["url"])
            uniq.append(it)
    return uniq


def parse_thailand(leader_config: dict, start_date: str, end_date: str,
                   limit: Optional[int] = None) -> List[Speech]:
    print("== Thailand (Srettha / Anutin) -- mfa.go.th Speeches ==")
    items = _discover()
    print(f"  {len(items)} unique listing items")
    speeches: List[Speech] = []
    for it in items:
        date_iso = it["date"][:10]
        if not in_date_range(date_iso, start_date, end_date):
            continue
        who = _leader_for(it["title"], date_iso)
        if who is None:
            continue
        url = "https://www.mfa.go.th" + it["url"].split("?")[0]
        data = _get(url)
        if not data:
            continue
        try:
            page = data["props"]["pageProps"]["components_meta"]["page"]["data"]
        except (KeyError, TypeError):
            continue
        html = page.get("description") or ""
        soup = BeautifulSoup(html, "html.parser")
        full_text = clean_text(soup.get_text("\n", strip=True))
        from_pdf = False
        if len(full_text) < 400:
            # the body is sometimes attached only as a PDF, not inline HTML
            for doc in page.get("documents") or []:
                pdf_url = doc.get("url", "")
                if pdf_url.lower().endswith(".pdf"):
                    pdf_text = _pdf_text(pdf_url)
                    if len(pdf_text) > len(full_text):
                        full_text, from_pdf = pdf_text, True
        if len(full_text) < 400:
            continue
        title = clean_text(page.get("title") or it["title"])
        real_date = (page.get("date") or it["date"])[:10]
        if not in_date_range(real_date, start_date, end_date):
            continue
        speeches.append(Speech(
            country=leader_config["country"],
            leader=who,
            role=leader_config["role"],
            date=real_date,
            title=title,
            full_text=full_text,
            language="English",
            source_url=url,
            likely_speech=classify_as_speech(title),
            content_type=classify_content_type(title),
            notes=("Sourced from the Ministry of Foreign Affairs' Speeches section "
                   "(mfa.go.th), not the Prime Minister's own thaigov.go.th (which "
                   "blocks automated access). Speaker resolved from the name in the "
                   "title where given, else from PM tenure dates."
                   + (" Text extracted from the attached PDF (the page itself carries "
                      "only the title, no inline body)." if from_pdf else "")),
        ))
        if limit and len(speeches) >= limit:
            break
    return speeches
