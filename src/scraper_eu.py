"""
Scraper for the European Union (Commission President Ursula von der Leyen).

Source: the European Commission Press Corner's own JSON API
(ec.europa.eu/commission/presscorner/api) -- the same one its public web page
calls.  Two endpoints:
  /search?text=...&language=en&pagesize=N&pagenumber=P   newest-first hits
  /documents?reference=SPEECH/25/2053&language=en         full HTML body

The `type` filter on /search is ignored server-side, so we search on her name,
page newest-first, stop once we pass the start date, and keep client-side only
items whose document type is SPEECH and whose title names her.  That leaves
her own speeches, remarks and statements (not other Commissioners', not press
releases).

Native English, single speaker.  Speeches at joint press conferences are her
own opening remarks; Q&A is not part of these documents.
"""

import re
import time
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from src.utils import clean_text, Speech
from src.text_processing import in_date_range, classify_as_speech, classify_content_type

API = "https://ec.europa.eu/commission/presscorner/api"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "application/json"}
PAGE_SIZE = 50
DELAY = 1.0


def _get_json(path: str, params: dict, max_retries: int = 3):
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(API + path, headers=HEADERS, params=params, timeout=40)
            time.sleep(DELAY)
            if resp.status_code == 200:
                return resp.json()
            print(f"  [warn] {path} status {resp.status_code} (attempt {attempt})")
        except Exception as e:
            print(f"  [warn] {path} raised {e!r} (attempt {attempt})")
        time.sleep(DELAY * attempt * 2)
    print(f"  [error] giving up on {path} {params}")
    return None


def _is_vdl_speech(item: dict) -> bool:
    if (item.get("docutype") or {}).get("code") != "SPEECH":
        return False
    return "von der leyen" in (item.get("title") or "").lower()


def _discover(start_date: str, end_date: str) -> List[dict]:
    found, page = [], 1
    while True:
        data = _get_json("/search", {"text": "President von der Leyen", "language": "en",
                                      "pagesize": PAGE_SIZE, "pagenumber": page})
        if not data:
            break
        items = data.get("docuLanguageListResources") or []
        if not items:
            break
        for it in items:
            if _is_vdl_speech(it) and start_date <= (it.get("eventDate") or "") <= end_date:
                found.append(it)
        oldest = min((i.get("eventDate") or "9999") for i in items)
        if page % 5 == 1:
            print(f"  search page {page}: oldest {oldest}, kept so far {len(found)}")
        if oldest < start_date:
            break
        page += 1
    # de-duplicate on the reference code (a doc can surface on several pages)
    seen, uniq = set(), []
    for it in found:
        if it["refCode"] not in seen:
            seen.add(it["refCode"])
            uniq.append(it)
    return uniq


def parse_eu(leader_config: dict, start_date: str, end_date: str,
             limit: Optional[int] = None) -> List[Speech]:
    print("== European Union (von der Leyen) ==")
    items = _discover(start_date, end_date)
    print(f"  {len(items)} candidate speeches; fetching bodies...")
    speeches: List[Speech] = []
    for n, it in enumerate(items, 1):
        ref = it["refCode"]
        doc = _get_json("/documents", {"reference": ref, "language": "en"})
        if not doc:
            continue
        html = (doc.get("docuLanguageResource") or {}).get("htmlContent") or ""
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(["script", "style", "img", "figure"]):
            tag.decompose()
        paragraphs = [clean_text(p.get_text(separator=" ")) for p in soup.find_all(["p", "li", "h2", "h3"])]
        full_text = clean_text("\n\n".join(p for p in paragraphs if p))
        if len(full_text) < 200:
            continue
        title = clean_text(it["title"])
        url = "https://ec.europa.eu/commission/presscorner/detail/en/" + ref.lower().replace("/", "_")
        speeches.append(Speech(
            country=leader_config["country"],
            leader=leader_config["leader"],
            role=leader_config["role"],
            date=it["eventDate"],
            title=title,
            full_text=full_text,
            language="English",
            source_url=url,
            likely_speech=classify_as_speech(title),
            content_type=classify_content_type(title),
            notes=f"Sourced from the European Commission Press Corner ({ref}) via its "
                  "JSON API. Date is the event date given by the Commission. "
                  "Native English, single speaker; for joint press conferences this "
                  "is her opening remarks only.",
        ))
        if n % 25 == 0:
            print(f"  fetched {n}/{len(items)}")
        if limit and len(speeches) >= limit:
            break
    return speeches
