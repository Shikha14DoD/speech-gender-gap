"""
Scraper for Tanzania -- three leaders in the 2023-2026 window:

  Samia Suluhu Hassan   (President, 19 Mar 2021 -> , re-elected Oct 2025)  Q16193885  (F)
  Kassim Majaliwa       (Prime Minister, -> 13 Nov 2025)                   Q6737420
  Mwigulu Nchemba       (Prime Minister, 13 Nov 2025 -> )                  Q31752753

TEXT route.  A companion `scraper_tanzania_video.py` covers the State
House YouTube channel (@ikulutanzania255, Swahili speeches, YouTube
auto-caption English) and `merge_tanzania.py` combines the two.

SOURCE
------
State House (Ikulu) publishes curated set-piece speeches at
`ikulu.go.tz/speeches` -- a server-rendered CMS, 20 cards per page.  Each
card carries a date + a truncated title and (for ~95% of them) an
`<iframe>` to a downloadable PDF at
`ikulu.go.tz/uploads/speeches/<sw|en>-<unixts>-<name>.pdf`.  The `sw-`/
`en-` filename prefix is an unreliable language hint (English-content
speeches sometimes carry `sw-`), so language is detected from the
extracted text.  Pages 1-3 cover the whole 2023-01 -> now window
(~46 speeches); page 4+ is 2021 and earlier.

Tanzanian presidential speeches are mostly in Swahili; a minority
(addresses to foreign parliaments, global summits, award acceptances) are
in English.  Swahili rows are translated downstream by `translate_csv.py`.
"""

import re
import time
import datetime as dt
import urllib.parse
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

from src.utils import clean_text, Speech
from src.text_processing import in_date_range, classify_as_speech, classify_content_type

LISTING = "https://www.ikulu.go.tz/speeches?page={}"
DELAY = 0.7
PAGE_TIMEOUT = 60
PDF_TIMEOUT = 100
MAX_PAGES = 25

MAJALIWA_END = "2025-11-13"     # last full day of the Majaliwa premiership
SAMIA = ("Samia Suluhu Hassan", "President")

# ikulu.go.tz/speeches is entirely presidential -- PM speeches (Majaliwa,
# Nchemba) are not published here.  We still detect a PM *speaker* in case
# that ever changes, but only when the title clearly names the PM as the
# one speaking (right after the "HOTUBA YA" / "SPEECH BY" opener), not when
# a PM is merely mentioned (a retired PM's funeral, a foreign PM at a summit).
_PM_AS_SPEAKER = re.compile(
    r"^\s*(hotuba ya|speech by|statement by|remarks by|address by)\b[^,]{0,80}"
    r"\b(waziri mkuu|prime minister of the united republic|majaliwa|nchemba)\b",
    re.I)

_MONTHS_ABBR = {m[:3].lower(): i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}

def _cget(url: str, timeout: int, retries: int = 5):
    """curl_cffi GET with retry -- ikulu.go.tz has a flaky TLS stack that
    intermittently throws SSL 'UNEXPECTED_RECORD'."""
    for attempt in range(1, retries + 1):
        try:
            r = curl_requests.get(url, impersonate="chrome", timeout=timeout,
                                  verify=False)
            time.sleep(DELAY)
            if r.status_code == 200:
                return r
            if r.status_code in (403, 429, 500, 502, 503):
                time.sleep(4 * attempt)
        except Exception:
            time.sleep(3 * attempt)
    return None


# ------------------------------------------------------------------ discovery
def _card_date(txt: str) -> Optional[str]:
    m = re.search(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})", txt)
    if not m:
        return None
    mo = _MONTHS_ABBR.get(m.group(1).lower())
    if not mo:
        return None
    try:
        return dt.date(int(m.group(3)), mo, int(m.group(2))).isoformat()
    except ValueError:
        return None


def _parse_listing(html: str) -> List[Tuple[Optional[str], str, Optional[str]]]:
    """-> [(iso_date, card_title, pdf_url|None), ...]"""
    s = BeautifulSoup(html, "html.parser")
    out = []
    for card in s.select(".post-slide7"):
        d_el = card.select_one(".post-bar li")
        t_el = card.select_one(".post-description")
        a_el = card.select_one("a.read, a[data-target]")
        date = _card_date(d_el.get_text(" ", strip=True)) if d_el else None
        title = clean_text(t_el.get_text(" ", strip=True)).rstrip(". ") if t_el else ""
        pdf = None
        tgt = (a_el.get("data-target") if a_el else "") or ""
        mid = tgt.lstrip("#")
        if mid:
            modal = s.select_one("#" + re.escape(mid)) or s.find(id=mid)
            ifr = modal.select_one("iframe[src]") if modal else None
            if ifr and ".pdf" in ifr["src"].lower():
                pdf = ifr["src"].strip()
        out.append((date, title, pdf))
    return out


def discover(start_date: str, end_date: str) -> List[Tuple[Optional[str], str, Optional[str]]]:
    items: List[Tuple[Optional[str], str, Optional[str]]] = []
    seen: set = set()
    for page in range(1, MAX_PAGES + 1):
        r = _cget(LISTING.format(page), PAGE_TIMEOUT)
        if r is None:
            print(f"  [warn] listing page {page} failed")
            break
        cards = _parse_listing(r.text)
        if not cards:
            break
        dated = [c[0] for c in cards if c[0]]
        add = 0
        margin = f"{int(start_date[:4]) - 1}-01-01"
        for date, title, pdf in cards:
            key = pdf or f"{date}|{title}"
            if key in seen:
                continue
            seen.add(key)
            if date and date < margin:      # clearly out of window -- skip
                continue
            items.append((date, title, pdf))
            add += 1
        print(f"  page {page}: {len(cards)} cards (+{add}); "
              f"newest {max(dated) if dated else '?'} oldest {min(dated) if dated else '?'}")
        # listing is reverse-chronological -- stop once a whole page is
        # older than the window
        if dated and max(dated) < start_date:
            break
    return items


# ------------------------------------------------------------------ PDF
def _pdf_bytes(url: str) -> Optional[bytes]:
    enc = urllib.parse.quote(url, safe=":/?=&%")
    r = _cget(enc, PDF_TIMEOUT, retries=6)
    if r is not None and r.content[:4] == b"%PDF":
        return r.content
    return None


# PDF artefacts that appear before / around the real speech text
_ARTEFACT = re.compile(
    r"^\s*(check against delivery|embargo(ed)?[^\n]*|\(corrected\)|corrected|"
    r"jamhuri ya muungano wa tanzania|the united republic of tanzania|"
    r"ikulu[,\s].*|state house[,\s].*|"
    r"\d{1,3}\s*(?=[A-ZÀ-ſ])|jukwaa la hotuba[^\n]*)\s*\n?", re.I)
_PAGE_FOOTER = re.compile(r"\n\s*(page\s*\d+\s*(of\s*\d+)?|\d+\s*\|\s*ukurasa)\s*\n",
                          re.I)


def _pdf_text_and_title(pdf: bytes) -> Tuple[str, str]:
    import pymupdf
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    full = clean_text("\n".join(doc[i].get_text() for i in range(doc.page_count)))
    full = re.sub(r"[ \t]*\n[ \t]*", "\n", full)
    full = _PAGE_FOOTER.sub("\n", full)
    full = re.sub(r"\n{3,}", "\n\n", full).strip()
    for _ in range(3):
        stripped = _ARTEFACT.sub("", full)
        if stripped == full:
            break
        full = stripped.strip()
    # title = the leading block of lines up to the first blank line
    title_lines = []
    for ln in full.split("\n"):
        if not ln.strip():
            break
        title_lines.append(ln.strip())
        if len(" ".join(title_lines)) > 320:
            break
    title = re.sub(r"\s+", " ", " ".join(title_lines)).strip(" .-")
    title = _ARTEFACT.sub("", title).strip(" .-")
    return full, title[:320]


# ------------------------------------------------------------------ classify
_SW_HINT = re.compile(
    r"\b(na|ya|wa|kwa|katika|ni|kwamba|hii|hizo|serikali|watu|nchi|ndugu|"
    r"waheshimiwa|mheshimiwa|zetu|yetu|hili|ambao|kufanya|maendeleo)\b", re.I)
_EN_HINT = re.compile(
    r"\b(the|and|of|to|is|are|this|that|with|for|our|we|will|have)\b", re.I)


def _detect_lang(text: str) -> str:
    sample = text[:4000].lower()
    sw = len(_SW_HINT.findall(sample))
    en = len(_EN_HINT.findall(sample))
    return "English" if en > sw else "Swahili"


def _which_leader(date: Optional[str], title: str) -> Tuple[str, str]:
    if _PM_AS_SPEAKER.search(title):
        if date and date >= MAJALIWA_END:
            return "Mwigulu Nchemba", "Prime Minister"
        return "Kassim Majaliwa", "Prime Minister"
    return SAMIA


# ------------------------------------------------------------------ main
def parse_tanzania(leader_config: dict, start_date: str, end_date: str,
                   limit: Optional[int] = None) -> List[Speech]:
    print("== Tanzania (Samia / Majaliwa / Nchemba) -- text (ikulu.go.tz PDFs) ==")
    items = discover(start_date, end_date)
    print(f"  {len(items)} speech cards discovered")

    speeches: List[Speech] = []
    stats = {"no_pdf": 0, "pdf_fail": 0, "thin": 0, "out_of_range": 0}
    by: dict = {}

    for i, (date, ctitle, pdf_url) in enumerate(items, 1):
        if i % 15 == 0:
            print(f"  [{i}/{len(items)}] kept={len(speeches)} "
                  f"no_pdf={stats['no_pdf']} pdf_fail={stats['pdf_fail']}")

        if not pdf_url:
            stats["no_pdf"] += 1
            continue
        pdf = _pdf_bytes(pdf_url)
        if pdf is None:
            stats["pdf_fail"] += 1
            continue
        body, ptitle = _pdf_text_and_title(pdf)
        if len(body) < 400:
            stats["thin"] += 1        # scanned image / empty text layer
            continue

        # the PDF's own leading block is the best title, but fall back to the
        # listing-card title when it came out generic / truncated
        generic = re.match(r"(?i)^(jamhuri ya muungano|the united republic|"
                           r"check against|\d+|hotuba)\s*\.?\s*$", ptitle)
        title = ctitle if (len(ptitle) < 20 or generic) and len(ctitle) > 15 else ptitle
        lang = _detect_lang(body)
        leader, role = _which_leader(date, title)

        if not in_date_range(date, start_date, end_date):
            stats["out_of_range"] += 1
            continue

        speeches.append(Speech(
            country="Tanzania",
            leader=leader,
            role=role,
            date=date,
            title=title,
            full_text=body,
            language=lang,
            source_url=pdf_url,
            likely_speech=classify_as_speech(title),
            content_type=classify_content_type(title),
            notes=(f"Official State House transcript PDF (ikulu.go.tz/speeches). "
                   f"{lang} original"
                   + ("" if lang == "English"
                      else " -- English in full_text is a machine translation")
                   + f". Downloaded from {pdf_url}."),
        ))
        by[leader] = by.get(leader, 0) + 1
        if limit and len(speeches) >= limit:
            break

    print(f"\n  Tanzania text done: {len(speeches)} kept {by} | "
          f"no_pdf={stats['no_pdf']} pdf_fail={stats['pdf_fail']} "
          f"thin={stats['thin']} out_of_range={stats['out_of_range']}")
    return speeches
