"""
Scraper for Colombia -- Gustavo Petro (President, 7 Aug 2022 - 7 Aug 2026).

WHY THIS IS AN ARCHIVE-ONLY SCRAPER
-----------------------------------
The incoming administration completely rebuilt `presidencia.gov.co/prensa`
(SharePoint) in Aug 2026. The live "Paginas" library now holds ~120
successor-era items; every Petro-era speech URL returns a hard 404. Same
failure mode as Samoa's 2024 rebuild, but total.

So this scraper works entirely from the Internet Archive Wayback Machine:
  1. discover Petro-era speech page URLs via the CDX API
     (`presidencia.gov.co/prensa/Paginas/*`)
  2. for each, pull the newest archived snapshot that actually contains
     real content

COMPLICATION: the site sits behind an F5/BIG-IP bot challenge ("bobcmn"
JS shell). The Archive's crawler frequently got served the challenge page
instead of the article -- those snapshots are ~4-15 KB shells with no
speech text. We skip them and fall back to older snapshots until a real
one is found. Some URLs have NO real snapshot at all -- they're reported
in the hand-off as unrecoverable, not silently dropped.

Content is Spanish -- title/full_text stay Spanish here; run
translate_csv.py --language es afterwards (same flow as Chile / Mexico).

Structure of a real archived page (confirmed Sep 2026):
  - <title> / <meta name="title"> / og:title  -> speech title
  - breadcrumb in #s4-workspace begins "Discurso  Inicio > Prensa > ..."
    ("Discurso" = the site's own category label; "Noticia" for news)
  - body: the largest <div class="ms-rtestate-field"> (SharePoint rich-
    text field); several empty ones exist, so take the longest.
    Fallback: <div class="contenidoPagina"> minus its "Contenido de la
    pagina" label.
  - dateline: "<Ciudad>, <D> de <mes> de <YYYY>" near the top of the body;
    fallback to the -YYMMDD suffix in the URL slug.
"""

import re
import time
import json
import datetime as dt
from typing import List, Optional, Tuple

from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

from src.utils import clean_text, Speech
from src.text_processing import in_date_range

CDX = "https://web.archive.org/cdx/search/cdx"
WB = "https://web.archive.org/web"
DELAY = 1.0
CDX_TIMEOUT = 180
PAGE_TIMEOUT = 60
MAX_SNAPSHOTS_TRIED = 10

_MONTHS_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

# slug prefixes that mark a speech/remarks page (vs third-person news)
_SPEECH_SLUG = re.compile(
    r"^-?(palabras|alocuci[oó]n|alocucion|intervenci[oó]n|intervencion|"
    r"discurso|declaraci[oó]n|declaracion|saludo|mensaje|brindis|"
    r"instalaci[oó]n|instalacion)",
    re.I,
)


def _cget(url: str, timeout: int, retries: int = 4) -> Optional[curl_requests.Response]:
    for attempt in range(1, retries + 1):
        try:
            r = curl_requests.get(url, impersonate="chrome", timeout=timeout)
            time.sleep(DELAY)
            if r.status_code == 200:
                return r
            if r.status_code in (403, 429, 503):
                time.sleep(5 * attempt)
            else:
                print(f"  [warn] {r.status_code} for {url[:120]} (try {attempt})")
        except Exception as e:
            print(f"  [warn] {type(e).__name__} for {url[:120]} (try {attempt})")
            time.sleep(3 * attempt)
    return None


# ---------------------------------------------------------------- discovery
def discover_urls(start_date: str, end_date: str) -> List[str]:
    """All archived presidencia.gov.co/prensa/Paginas/* URLs, year-chunked."""
    start_year = int(start_date[:4])
    end_year = int(end_date[:4])
    seen = {}
    for year in range(start_year, end_year + 1):
        for host in ("www.presidencia.gov.co", "presidencia.gov.co"):
            q = (f"{CDX}?url={host}/prensa/Paginas/*&output=json&collapse=urlkey"
                 f"&fl=original&filter=statuscode:200"
                 f"&from={year}0101&to={year}1231&limit=20000")
            r = _cget(q, CDX_TIMEOUT)
            if r is None or not r.text.strip():
                print(f"  [error] CDX failed for {host} {year}")
                continue
            try:
                rows = json.loads(r.text)[1:]
            except json.JSONDecodeError:
                print(f"  [error] bad CDX JSON for {host} {year}")
                continue
            for row in rows:
                u = row[0].split("?")[0].split("#")[0]
                key = u.lower().replace("https://www.", "https://").replace("http://www.", "https://") \
                       .replace("http://", "https://").rstrip("/")
                seen.setdefault(key, u.replace("http://", "https://"))
            print(f"  CDX {host} {year}: {len(rows)} rows (running unique {len(seen)})")
    return sorted(seen.values())


def _snapshots(url: str) -> List[str]:
    q = (f"{CDX}?url={url}&output=json&fl=timestamp&filter=statuscode:200"
         f"&collapse=digest&limit=80")
    r = _cget(q, CDX_TIMEOUT)
    if r is None or not r.text.strip():
        return []
    try:
        rows = json.loads(r.text)[1:]
    except json.JSONDecodeError:
        return []
    return sorted({row[0] for row in rows}, reverse=True)


# ---------------------------------------------------------------- fetch page
def _is_challenge(html: str) -> bool:
    return ("bobcmn" in html or "window.SmmO" in html
            or ("<title>" not in html and "<TITLE>" not in html))


def _body_div(soup: BeautifulSoup):
    fields = soup.select("div.ms-rtestate-field")
    fields = [f for f in fields if f.get_text(strip=True)]
    if fields:
        return max(fields, key=lambda f: len(f.get_text()))
    cp = soup.select_one("div.contenidoPagina")
    return cp


def fetch_real(url: str) -> Tuple[Optional[str], Optional[BeautifulSoup], Optional[object]]:
    for ts in _snapshots(url)[:MAX_SNAPSHOTS_TRIED]:
        r = _cget(f"{WB}/{ts}id_/{url}", PAGE_TIMEOUT, retries=2)
        if r is None:
            continue
        html = r.text
        if _is_challenge(html):
            continue
        soup = BeautifulSoup(html, "html.parser")
        body = _body_div(soup)
        if body and len(body.get_text(strip=True)) > 400:
            return ts, soup, body
    return None, None, None


# ---------------------------------------------------------------- extraction
def _breadcrumb_category(soup: BeautifulSoup) -> str:
    ws = soup.select_one("#s4-workspace") or soup
    txt = re.sub(r"\s+", " ", ws.get_text(" ", strip=True))
    m = re.match(r"\s*([A-Za-zÁÉÍÓÚáéíóúñ]+)\s+Inicio\s*>", txt)
    return m.group(1) if m else ""


def _slug_date(url: str) -> Optional[str]:
    m = re.search(r"-(\d{2})(\d{2})(\d{2})\.aspx$", url)
    if not m:
        return None
    yy, mm, dd = m.groups()
    try:
        return dt.date(2000 + int(yy), int(mm), int(dd)).isoformat()
    except ValueError:
        return None


def _dateline(body_text: str) -> Tuple[Optional[str], str]:
    """Return (iso_date, venue_city) from a 'Ciudad, D de mes de YYYY' line."""
    head = body_text[:600]
    m = re.search(
        r"([A-ZÁÉÍÓÚ][A-Za-zÁÉÍÓÚáéíóúñ .()/-]{2,40}?),\s*"
        r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(20\d{2})",
        head,
    )
    if not m:
        m2 = re.search(r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(20\d{2})", head)
        if not m2:
            return None, ""
        d, mon, y = m2.groups()
        month = _MONTHS_ES.get(mon.lower())
        if not month:
            return None, ""
        try:
            return dt.date(int(y), month, int(d)).isoformat(), ""
        except ValueError:
            return None, ""
    city, d, mon, y = m.groups()
    month = _MONTHS_ES.get(mon.lower())
    if not month:
        return None, city.strip()
    try:
        return dt.date(int(y), month, int(d)).isoformat(), city.strip()
    except ValueError:
        return None, city.strip()


def _title(soup: BeautifulSoup, url: str) -> str:
    for sel in [("meta", {"name": "title"}), ("meta", {"property": "og:title"})]:
        el = soup.find(*sel)
        if el and el.get("content"):
            return clean_text(el["content"])
    t = soup.find("title")
    if t:
        return clean_text(t.get_text(" ", strip=True))
    return url.split("/Paginas/")[-1].replace(".aspx", "").replace("-", " ")


def _strip_zw(s: str) -> str:
    return s.translate({0x200b: None, 0x200c: None, 0x200d: None,
                        0xfeff: None, 0x00ad: None})


_FOOTER = re.compile(
    r"\s*Fuente\s*:\s*Presidencia\s+de\s+la\s+[¬\-\s]*Rep[uú\wí]*"
    r".*?Edici[oó]n\s*:\s*Unidad\s+de\s+Implementaci[oó]n\s+del\s+Acuerdo\s+de\s+Paz\.?",
    re.I | re.S)


def _clean_body(body) -> str:
    for tag in body.select("script, style"):
        tag.decompose()
    text = body.get_text("\n")
    text = text.translate({0x200b: None, 0x200c: None, 0x200d: None,
                           0xfeff: None, 0x00ad: None, 0x00ac: None})
    text = re.sub(r"^\s*Contenido de la p[aá]gina\s*", "", text, flags=re.I)
    text = _FOOTER.sub("", text)  # editorial provenance footer, not speech
    text = clean_text(text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def parse_colombia(leader_config: dict, start_date: str, end_date: str,
                   limit: Optional[int] = None) -> List[Speech]:
    print(f"== Colombia ({leader_config['leader']}) -- Wayback archive route ==")
    all_urls = discover_urls(start_date, end_date)
    speech_urls = [u for u in all_urls
                   if _SPEECH_SLUG.match(u.split("/Paginas/")[-1])]
    print(f"  {len(all_urls)} archived prensa pages -> {len(speech_urls)} speech-slug pages")

    speeches: List[Speech] = []
    stats = {"no_snapshot": [], "not_discurso": 0, "out_of_range": 0, "kept": 0}

    for i, url in enumerate(speech_urls, 1):
        if i % 25 == 0:
            print(f"  [{i}/{len(speech_urls)}] kept={stats['kept']} "
                  f"no_snapshot={len(stats['no_snapshot'])}")
        ts, soup, body = fetch_real(url)
        if soup is None:
            stats["no_snapshot"].append(url)
            continue

        title = _strip_zw(_title(soup, url))
        category = _breadcrumb_category(soup)
        body_text = _clean_body(body)

        # keep if the site itself filed it as a "Discurso", OR the title
        # opens with a speech word (some real speeches lose the breadcrumb
        # in older archived templates)
        title_is_speech = bool(re.match(
            r"\s*(palabras|alocuci|intervenci|discurso|declaraci|saludo|"
            r"mensaje|instalaci)", title, re.I))
        if category.lower() != "discurso" and not title_is_speech:
            stats["not_discurso"] += 1
            continue

        iso_date, city = _dateline(body_text)
        date = iso_date or _slug_date(url)
        if not in_date_range(date, start_date, end_date):
            stats["out_of_range"] += 1
            continue

        note_type = ""
        tl = title.lower()
        if "entrevista" in tl:
            note_type = " Row is an INTERVIEW (may include interviewer questions)."
        elif "declaraci" in tl and "conjunta" in tl:
            note_type = " Row is a JOINT DECLARATION -- not solely the leader's words."
        elif "declaraci" in tl:
            note_type = " Row is a press DECLARATION rather than a prepared address."

        speeches.append(Speech(
            country=leader_config["country"],
            leader=leader_config["leader"],
            role=leader_config["role"],
            date=date,
            title=title,
            full_text=body_text,
            language="Spanish",
            source_url=url,
            likely_speech="yes",
            content_type="Speech",
            notes=(f"Recovered from Internet Archive Wayback snapshot {ts} "
                   f"(live page 404s -- presidencia.gov.co/prensa was rebuilt "
                   f"by the incoming administration Aug 2026). Site category: "
                   f"'{category or 'n/a'}'. Dateline city: {city or 'n/a'}. "
                   f"full_text/title are Spanish -- run translate_csv.py "
                   f"--language es." + note_type),
        ))
        stats["kept"] += 1
        if limit and stats["kept"] >= limit:
            break

    print(f"\n  Colombia done: kept {stats['kept']}, "
          f"no real snapshot {len(stats['no_snapshot'])}, "
          f"not a discurso {stats['not_discurso']}, "
          f"out of range {stats['out_of_range']}")
    if stats["no_snapshot"]:
        import pathlib
        p = pathlib.Path("data/processed/colombia_unrecoverable_urls.txt")
        p.write_text("\n".join(stats["no_snapshot"]), encoding="utf-8")
        print(f"  wrote {len(stats['no_snapshot'])} unrecoverable URLs -> {p}")
    return speeches
