"""
Scraper for Chile -- Gabriel Boric Font (President, 11 Mar 2022 - 11 Mar 2026).

Source: prensa.presidencia.cl official "Discursos" archive
(`discursos.aspx?page=N`). This is the Press Office's speeches/remarks
feed -- one entry per presidential activity where he spoke.

Site notes (confirmed via manual inspection, Sep 2026):
  - Plain `requests` gets a TLS chain error AND the site is behind a
    filter that prefers browser-like clients -- fetched with curl_cffi
    (chrome impersonation) + verify=False, the same pattern used for
    Barbados / Mexico / parts of China in this project.
  - Page HTML is served latin-1 / cp1252, NOT utf-8 -- decoded
    explicitly, otherwise every accented character comes back mangled.
  - Listing is 6 entries per page, strictly reverse-chronological.
    Item block: <div class="bloque"> (some carry an extra "oculto"
    CSS class -- purely presentational, still scraped) with
      <h3><a href="discurso.aspx?id=N">TITLE</a></h3>
      <div class="fecha"> ... 13 MAY. 2026</div>
  - The feed is shared across administrations (Boric, his successor
    Kast, and older presidents Pinera/Bachelet further back) -- filtered
    to entries whose title names "Gabriel Boric" AND whose date is
    within his tenure.
  - Article page: title in <span id="main_ltTitulo">, date in
    <span id="main_ltFEcha"> ("30 SEPT. 2025"), body in
    <span id="main_ltContenido"> with <br><br> paragraph breaks.
  - Content is Spanish -- full_text/title stay Spanish here; run
    translate_csv.py --language es afterwards to add title_en /
    full_text_en (same flow as Mexico).

Like Slovenia / Samoa / Barbados, this is a mixed feed: genuine
addresses sit alongside entries where he only spoke briefly at a
ceremony or site visit. likely_speech / content_type flag this
(heuristic, computed from the Spanish title) -- nothing is dropped
for being ambiguous.
"""

import re
import time
import datetime as dt
from typing import List, Optional

from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

from src.utils import clean_text, Speech
from src.text_processing import in_date_range

BASE = "https://prensa.presidencia.cl"
BASE_LISTING = BASE + "/discursos.aspx"
MAX_PAGES = 220
REQUEST_DELAY_SECONDS = 1.5

_MONTHS_ES = {
    "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SEP": 9, "SEPT": 9, "OCT": 10, "NOV": 11, "DIC": 12,
}

# The source IS the Press Office's curated "Discursos" (speeches) feed,
# so every surviving entry is presidential remarks -- like Barbados, we
# default likely_speech to "yes" rather than running the English-keyword
# classifier (which mislabels Spanish "encabeza / participa" titles as
# non-speech even though the body is a full address). Genuine non-speech
# noise is filtered upstream by the minimum-length check.
def _classify_es(title: str, full_text: str):
    t = title.lower()
    likely = "yes"
    if len(full_text) < 400:
        # too short to be a real address -- flag for manual review
        likely = "maybe"

    if "entrevista" in t or "entrevist" in t:
        ctype = "Interview"
    elif any(k in t for k in ["declaraci", "punto de prensa",
                              "conferencia de prensa", "medios"]):
        ctype = "Statement"
    elif any(k in t for k in ["mensaje", "saludo", "cadena nacional"]):
        ctype = "Statement"
    else:
        ctype = "Speech"
    return likely, ctype


def _get(url: str, max_retries: int = 4, delay: float = REQUEST_DELAY_SECONDS) -> Optional[str]:
    for attempt in range(1, max_retries + 1):
        try:
            resp = curl_requests.get(url, impersonate="chrome", timeout=45, verify=False)
            time.sleep(delay)
            if resp.status_code == 200:
                txt = resp.content.decode("utf-8", errors="replace")
                if txt.count("�") > 15:
                    txt = resp.content.decode("cp1252", errors="replace")
                return txt
            print(f"  [warn] status {resp.status_code} for {url} (attempt {attempt})")
        except Exception as e:
            print(f"  [warn] request failed for {url}: {e} (attempt {attempt})")
        if attempt < max_retries:
            time.sleep(delay * attempt)
    print(f"  [error] giving up on {url}")
    return None


def _parse_es_date(text: str) -> Optional[str]:
    """'30 SEPT. 2025' / '13 MAY. 2026' -> ISO. Returns None if unparseable."""
    if not text:
        return None
    m = re.search(r"(\d{1,2})\s+([A-Za-zÁÉÍÓÚáéíóú]+)\.?\s+(\d{4})", text.strip())
    if not m:
        return None
    d, mon, y = m.groups()
    mon_key = mon.upper().replace("Á", "A").replace("É", "E").replace("Í", "I") \
                         .replace("Ó", "O").replace("Ú", "U")[:4]
    month = _MONTHS_ES.get(mon_key) or _MONTHS_ES.get(mon_key[:3])
    if not month:
        return None
    try:
        return dt.date(int(y), month, int(d)).isoformat()
    except ValueError:
        return None


def _leader_marker(leader_config: dict) -> str:
    # "Gabriel Boric Font" -> match on "boric"
    parts = leader_config["leader"].split()
    return parts[1].lower() if len(parts) > 1 else parts[0].lower()


def parse_chile(leader_config: dict, start_date: str, end_date: str,
                limit: Optional[int] = None) -> List[Speech]:
    print(f"== Chile ({leader_config['leader']}) ==")
    marker = _leader_marker(leader_config)
    speeches: List[Speech] = []
    seen_ids = set()
    page = 1
    consecutive_too_old = 0

    while page <= MAX_PAGES:
        url = BASE_LISTING if page == 1 else f"{BASE_LISTING}?page={page}"
        html = _get(url)
        if html is None:
            break
        soup = BeautifulSoup(html, "html.parser")
        blocks = soup.select("div.bloque")
        # drop non-item helper divs (fin-bloque etc. won't match, but guard anyway)
        blocks = [b for b in blocks if b.find("h3")]
        if not blocks:
            print(f"  [info] no item blocks on page {page}, stopping.")
            break

        page_dates = []
        page_hits = 0
        for b in blocks:
            a = b.select_one("h3 a[href*='discurso.aspx']")
            if not a:
                continue
            m = re.search(r"id=(\d+)", a["href"])
            if not m:
                continue
            art_id = m.group(1)
            list_title = clean_text(a.get_text(" ", strip=True))
            fecha_el = b.select_one("div.fecha")
            list_date = _parse_es_date(fecha_el.get_text(" ", strip=True)) if fecha_el else None
            if list_date:
                page_dates.append(list_date)

            if marker not in list_title.lower():
                continue
            if list_date and not (start_date <= list_date <= end_date):
                continue
            if art_id in seen_ids:
                continue
            seen_ids.add(art_id)

            art = _fetch_article(f"{BASE}/discurso.aspx?id={art_id}", leader_config, list_date)
            if art is None:
                continue
            if in_date_range(art.date, start_date, end_date):
                speeches.append(art)
                page_hits += 1
            if limit and len(speeches) >= limit:
                print(f"  reached limit ({limit}).")
                return speeches

        # Early stop: once a whole page is older than our window, and the
        # feed is strictly reverse-chronological, we're done. Require two
        # consecutive such pages as a guard against any stray old item.
        if page_dates and all(d < start_date for d in page_dates):
            consecutive_too_old += 1
            if consecutive_too_old >= 2:
                print(f"  [info] page {page} fully older than {start_date}, stopping.")
                break
        else:
            consecutive_too_old = 0

        if page % 10 == 0 or page == 1:
            newest = max(page_dates) if page_dates else "?"
            oldest = min(page_dates) if page_dates else "?"
            print(f"  page {page}: {len(blocks)} items ({oldest}..{newest}), "
                  f"kept {len(speeches)} so far")
        page += 1

    print(f"  done: {len(speeches)} speeches kept.")
    return speeches


def _fetch_article(url: str, leader_config: dict, list_date: Optional[str]) -> Optional[Speech]:
    html = _get(url)
    if html is None:
        return None
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.find("span", id="main_ltTitulo")
    if title_el:
        title = clean_text(title_el.get_text(" ", strip=True))
    else:
        og = soup.find("meta", property="og:title")
        title = clean_text(og["content"]) if og and og.get("content") else url

    fecha_el = soup.find("span", id="main_ltFEcha")
    art_date = _parse_es_date(fecha_el.get_text(" ", strip=True)) if fecha_el else None
    date_iso = art_date or list_date

    body_el = soup.find("span", id="main_ltContenido")
    if body_el is None:
        return None
    for br in body_el.find_all("br"):
        br.replace_with("\n")
    full_text = clean_text(body_el.get_text())
    # collapse the <br><br> runs into real paragraph breaks
    full_text = re.sub(r"\n\s*\n+", "\n\n", full_text)
    full_text = re.sub(r"(?<!\n)\n(?!\n)", "\n\n", full_text)

    if not full_text or len(full_text) < 60:
        return None

    likely, ctype = _classify_es(title, full_text)

    return Speech(
        country=leader_config["country"],
        leader=leader_config["leader"],
        role=leader_config["role"],
        date=date_iso,
        title=title,
        full_text=full_text,
        language="Spanish",
        source_url=url,
        likely_speech=likely,
        content_type=ctype,
        notes="Scraped from prensa.presidencia.cl official 'Discursos' "
              "archive (Press Office speeches/remarks feed). Site served "
              "as cp1252 and behind a browser-client filter -- fetched "
              "via curl_cffi. Source is the Press Office's curated "
              "'Discursos' feed, so likely_speech defaults to 'yes' "
              "('maybe' only when the transcript is suspiciously short) "
              "rather than using the project's English-keyword classifier, "
              "which mislabels Spanish 'encabeza/participa' titles. "
              "content_type is a rough guess from the Spanish title. "
              "full_text/title are Spanish; run translate_csv.py "
              "--language es to add English columns.",
    )
