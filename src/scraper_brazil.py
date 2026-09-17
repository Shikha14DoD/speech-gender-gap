"""
Scraper for Brazil -- one leader in the 2023-2026 window:

  Luiz Inacio Lula da Silva  (President, 1 Jan 2023 -> )   Q37181

TEXT route. Brazil has no PM -- Lula is the only leader in scope.

WHY WAYBACK-FIRST
------------------
`gov.br/planalto` is a Plone CMS site sitting behind an active JS
bot-mitigation challenge (an obfuscated "TSPD" loader script -- F5/Shape
Security style). A plain `curl_cffi` fetch with Chrome impersonation gets
HTTP 200 but only the challenge shell, never the article body. The Wayback
Machine's cached snapshots, however, hold the fully rendered page --
confirmed on a real speech page (clean Portuguese transcript inside
`#content-core`). So unlike Sri Lanka (live-first, Wayback fallback),
Brazil goes Wayback-first; live is tried too in case a given snapshot is
thin, but it is not expected to work.

Speeches are published in Portuguese; kept native, translated downstream by
translate_csv.py.
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
DELAY = 0.8
CDX_TIMEOUT = 180
PAGE_TIMEOUT = 55
MAX_SNAPSHOTS = 6

LULA = ("Luiz Inacio Lula da Silva", "President")

_PREFIXES = [
    "gov.br/planalto/pt-br/acompanhe-o-planalto/discursos/*",
    "gov.br/planalto/pt-br/acompanhe-o-planalto/discursos-e-pronunciamentos/*",
]

# only keep genuine speech content pages, not listing/asset/resource paths
_SPEECH_SLUG = re.compile(r"/discurso[^/]*$", re.I)
_NOT_SPEECH = re.compile(
    r"\+\+resource\+\+|\.(png|jpe?g|gif|svg|css|js|ico|woff2?)$", re.I)

# Wayback sometimes serves the folder's LISTING view for a given snapshot
# (the specific slug 404'd that day) instead of the individual article --
# these have a generic title and/or concatenate several "Discurso do..."
# items. Also reject pre-Lula (Bolsonaro-era) content that shares similar
# URL slugs from CDX's overlapping prefix query.
_LISTING_TITLE = re.compile(r"^\s*últimos discursos", re.I)
_NOT_LULA = re.compile(r"\bjair\s+(messias\s+)?bolsonaro\b", re.I)

_MONTHS_PT = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}


def _cget(url: str, timeout: int, retries: int = 5):
    for attempt in range(1, retries + 1):
        try:
            r = curl_requests.get(url, impersonate="chrome", timeout=timeout,
                                  verify=False)
            time.sleep(DELAY)
            if r.status_code == 200:
                return r
            if r.status_code in (403, 429, 502, 503):
                time.sleep(4 * attempt)
        except Exception:
            time.sleep(3 * attempt)
    return None


# ------------------------------------------------------------------ discovery
def _cdx(pattern: str) -> List[str]:
    q = (f"{CDX}?url={pattern}&output=json&collapse=urlkey&fl=original"
         f"&filter=statuscode:200&limit=40000")
    r = _cget(q, CDX_TIMEOUT, retries=5)
    if r is None or not r.text.strip():
        print(f"  [warn] CDX failed: {pattern}")
        return []
    try:
        return [row[0] for row in json.loads(r.text)[1:]]
    except json.JSONDecodeError:
        return []


def _norm(u: str) -> str:
    u = u.split("?")[0].split("#")[0]
    u = u.replace("http://", "https://").replace("https://www.", "https://")
    return u.rstrip("/").lower()


def discover_urls() -> List[str]:
    seen: dict = {}
    for prefix in _PREFIXES:
        rows = _cdx(prefix)
        add = 0
        for u in rows:
            if _NOT_SPEECH.search(u) or not _SPEECH_SLUG.search(u):
                continue
            k = _norm(u)
            if k in seen:
                continue
            seen[k] = u.replace("http://", "https://")
            add += 1
        print(f"  CDX {prefix}: {len(rows)} rows (+{add} speech-slug, total {len(seen)})")
    return sorted(seen.values())


# ------------------------------------------------------------------ fetch
def _is_shell(html: str) -> bool:
    low = html.lower()
    if "tspd" in low and "content-core" not in low:
        return True
    if "<title>" not in low:
        return True
    return len(BeautifulSoup(html, "html.parser").get_text(strip=True)) < 400


def _snapshots(url: str) -> List[str]:
    q = (f"{CDX}?url={url}&output=json&fl=timestamp&filter=statuscode:200"
         f"&collapse=digest&limit=40")
    r = _cget(q, CDX_TIMEOUT, retries=3)
    if r is None or not r.text.strip():
        return []
    try:
        return sorted({row[0] for row in json.loads(r.text)[1:]}, reverse=True)
    except json.JSONDecodeError:
        return []


def _body_el(soup: BeautifulSoup):
    for sel in ("#content-core", ".documentContent", "article", ".text-content"):
        els = [e for e in soup.select(sel) if e.get_text(strip=True)]
        if els:
            return max(els, key=lambda e: len(e.get_text()))
    return None


def fetch(url: str) -> Tuple[Optional[BeautifulSoup], str]:
    """Wayback-first (the live site is hard bot-gated); live is still tried
    in case a given page isn't archived or the gate is inconsistent."""
    for ts in _snapshots(url)[:MAX_SNAPSHOTS]:
        r = _cget(f"{WB}/{ts}id_/{url}", PAGE_TIMEOUT, retries=2)
        if r is None or _is_shell(r.text):
            continue
        s = BeautifulSoup(r.text, "html.parser")
        b = _body_el(s)
        if b is not None and len(b.get_text(strip=True)) > 400:
            return s, f"wayback:{ts}"
    r = _cget(url, PAGE_TIMEOUT, retries=2)
    if r is not None and not _is_shell(r.text):
        s = BeautifulSoup(r.text, "html.parser")
        if _body_el(s) is not None:
            return s, "live"
    return None, ""


# ------------------------------------------------------------------ parse
def _title(soup: BeautifulSoup) -> str:
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return clean_text(og["content"])
    h = soup.select_one("h1")
    if h and h.get_text(strip=True):
        return clean_text(h.get_text(" ", strip=True))
    return ""


_DATE_IN_DESC = re.compile(
    r"em (\d{1,2}) de (" + "|".join(_MONTHS_PT) + r") de (20\d{2})", re.I)
# Planalto article pages show "publicado DD/MM/YYYY" near the top
_DATE_PUBLICADO = re.compile(r"publicado\s+(\d{1,2})/(\d{1,2})/(20\d{2})", re.I)
# some open with a dateline instead: "Brasília, 10 de abril de 2023"
_DATE_DATELINE = re.compile(
    r"^[A-ZÀ-Ú][\wÀ-ú\s]{2,25},\s*(\d{1,2})\s+de\s+(" +
    "|".join(_MONTHS_PT) + r")\s+de\s+(20\d{2})", re.I)


def _date(soup: BeautifulSoup, body_text: str = "") -> Optional[str]:
    t = soup.find("time", attrs={"datetime": True})
    if t and re.match(r"\d{4}-\d{2}-\d{2}", t["datetime"]):
        return t["datetime"][:10]
    for m in soup.find_all("meta"):
        p = (m.get("property") or m.get("name") or "").lower()
        if "published" in p:
            v = m.get("content", "")
            mm = re.match(r"(\d{4}-\d{2}-\d{2})", v)
            if mm:
                return mm.group(1)
    og = soup.find("meta", property="og:description")
    if og and og.get("content"):
        m = _DATE_IN_DESC.search(og["content"])
        if m:
            mo = _MONTHS_PT.get(m.group(2).lower())
            if mo:
                try:
                    return dt.date(int(m.group(3)), mo, int(m.group(1))).isoformat()
                except ValueError:
                    pass
    m = _DATE_PUBLICADO.search(body_text[:600])
    if m:
        try:
            return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            pass
    m = _DATE_DATELINE.match(body_text.strip()[:80])
    if m:
        mo = _MONTHS_PT.get(m.group(2).lower())
        if mo:
            try:
                return dt.date(int(m.group(3)), mo, int(m.group(1))).isoformat()
            except ValueError:
                pass
    return None


def parse_brazil(leader_config: dict, start_date: str, end_date: str,
                 limit: Optional[int] = None) -> List[Speech]:
    print("== Brazil (Lula) -- text (gov.br/planalto via Wayback) ==")
    urls = discover_urls()
    print(f"  {len(urls)} speech-slug candidate URLs")

    speeches: List[Speech] = []
    stats = {"no_page": 0, "thin": 0, "out_of_range": 0}

    for i, url in enumerate(urls, 1):
        if i % 20 == 0:
            print(f"  [{i}/{len(urls)}] kept={len(speeches)} no_page={stats['no_page']}")

        soup, src = fetch(url)
        if soup is None:
            stats["no_page"] += 1
            continue

        title = _title(soup)
        body_el = _body_el(soup)
        for tag in body_el.select("script, style, nav, footer, .discreet"):
            tag.decompose()
        body = clean_text(body_el.get_text("\n"))
        body = re.sub(r"\n\s*\n+", "\n\n", body).strip()
        date = _date(soup, body)
        # strip the "publicado DD/MM/YYYY HHhMM  Página" byline the article
        # pages open with, now that the date's been read out of it
        body = re.sub(r"^\s*publicado\s+\d{1,2}/\d{1,2}/20\d{2}\s+\d{1,2}h\d{2}"
                      r"\s*p[aá]gina\s*", "", body, flags=re.I).strip()
        body = _DATE_DATELINE.sub("", body, count=1).strip()

        if len(body) < 400 or not title:
            stats["thin"] += 1
            continue
        if _LISTING_TITLE.search(title) or _NOT_LULA.search(body[:2000]):
            stats["thin"] += 1
            continue
        if not in_date_range(date, start_date, end_date):
            stats["out_of_range"] += 1
            continue

        leader, role = LULA
        provenance = "live page" if src == "live" else \
            "recovered from Internet Archive snapshot " + src.split(":", 1)[-1]
        domain = re.sub(r"https?://", "", url).split("/")[0]

        speeches.append(Speech(
            country="Brazil",
            leader=leader,
            role=role,
            date=date,
            title=title,
            full_text=body,
            language="Portuguese",
            source_url=url,
            likely_speech=classify_as_speech(title),
            content_type=classify_content_type(title),
            notes=(f"Text transcript from Brazil's official Planalto site "
                   f"({provenance}). Domain: {domain}. Published in "
                   f"Portuguese. No translation."),
        ))
        if limit and len(speeches) >= limit:
            break

    print(f"\n  Brazil text done: {len(speeches)} kept | no_page={stats['no_page']} "
          f"thin={stats['thin']} out_of_range={stats['out_of_range']}")
    return speeches
