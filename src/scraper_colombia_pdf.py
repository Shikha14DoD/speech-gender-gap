"""
Colombia -- Gustavo Petro -- OFFICIAL PDF VOLUME route.

The Wayback route (`scraper_colombia.py`) only recovered ~81 speeches
because the Archive barely crawled presidencia.gov.co and the live site
is gone. This module uses a much better source:

  portalparalapaz.gov.co publishes the government's own compilation
  "Discursos del presidente Gustavo Petro en la Colombia potencia de la
  vida" as a numbered PDF volume series (Tomo/Vol 1..26), ~10-20 full
  speeches per volume, roughly one volume per month of the term.

Volume formats confirmed (Sep 2026):
  - Vol 4..26: FULL speeches. Each entry = a header line
    ("Palabras / Alocucion / Intervencion del presidente ...") next to a
    "<Ciudad>, <D> de <mes> de <YYYY>" dateline, then the complete text
    until the next entry. Clean embedded text layer, no OCR needed.
  - Vol 2 and "8.-Discursos-del-presidente.pdf": EXCERPT compilations
    ("Apartes de las palabras del presidente ...") -- these are the only
    coverage for 2022-2023, kept but every row flagged as an excerpt in
    `notes` (per the project rule on excerpts).

Content is Spanish -- run translate_csv.py --language es afterwards.

`source_url` for every row is the volume PDF URL plus a #page anchor,
so the row stays uniquely keyed and re-checkable (the manager's rule 7).
"""

import io
import re
import time
import datetime as dt
from typing import List, Optional, Tuple

import pymupdf
from curl_cffi import requests as curl_requests

from src.utils import clean_text, Speech
from src.text_processing import in_date_range

_BASE = "https://portalparalapaz.gov.co/wp-content/uploads"

# (url, is_excerpt) -- from the live /uploads/ directory listing, Sep 2026
# Full-speech volumes only. Vol 2 and "8.-Discursos-del-presidente.pdf"
# are "apartes" (excerpt) compilations for 2022-2023 with a much messier
# layout -- deliberately excluded; the 2023 gap is documented in the
# hand-off instead of filled with mangled partial text.
VOLUMES: List[Tuple[str, bool]] = [
    (f"{_BASE}/2024/07/Discursos-del-presidente_Vol.-4_BC.pdf", False),
    (f"{_BASE}/2024/08/Discursos-del-presidente_Vol.-5_BC.pdf", False),
    (f"{_BASE}/2024/09/Discursos-del-presidente_Vol.-6_Baja-calidad.pdf", False),
    (f"{_BASE}/2025/03/Discursos-del-presidente_Vol.-7_compressed.pdf", False),
    (f"{_BASE}/2025/07/20250312DiscursosPresidenteVol8-1.pdf", False),
    (f"{_BASE}/2025/08/Discursos-del-presidente_Vol.-9.pdf", False),
    (f"{_BASE}/2025/08/Discursos-del-presidente_Vol.-10.pdf", False),
    (f"{_BASE}/2025/08/Discursos-del-presidente_Vol.-11.pdf", False),
    (f"{_BASE}/2025/08/Discursos-del-presidente_Vol.-12.pdf", False),
    (f"{_BASE}/2025/08/Discursos-del-presidente_Vol.-13.pdf", False),
    (f"{_BASE}/2025/09/20250828DiscursosPresidenteVol14.pdf", False),
    (f"{_BASE}/2025/09/20250901DiscursosPresidenteVol15.pdf", False),
    (f"{_BASE}/2025/10/Discursos-del-presidente_Vol.-16.pdf", False),
    (f"{_BASE}/2025/10/Discursos-del-presidente_Vol.-17.pdf", False),
    (f"{_BASE}/2026/01/20260108DiscursosDelPresidenteVol18Octubre2025.pdf", False),
    (f"{_BASE}/2026/01/20260115DiscursosDelPresidenteVol19Noviembre2025.pdf", False),
    (f"{_BASE}/2026/03/20260311DiscursosPresidenteDic2025_Vol.-20.pdf", False),
    (f"{_BASE}/2026/03/20260312DiscursosPresidenteDic2025_Vol.-21.pdf", False),
    (f"{_BASE}/2026/03/20260316DiscursosPresidenteFeb2026_Vol.-22.pdf", False),
    (f"{_BASE}/2026/04/Discursos-del-presidente_Vol.-23.pdf", False),
    (f"{_BASE}/2026/05/20260529DiscursosPresidenteAbril_Vol.-24.pdf", False),
    (f"{_BASE}/2026/07/20260724Discursos-del-presidente_Vol.-25_compressed.pdf", False),
    (f"{_BASE}/2026/07/20260728Discursos-del-presidente_Vol.-26_compressed.pdf", False),
]

_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

_HEADER = (r"(Apartes de las palabras|Palabras|Alocuci[oó]n|Intervenci[oó]n|"
           r"Declaraci[oó]n|Discurso|Mensaje|Saludo|Instalaci[oó]n|Palabras iniciales)"
           r"\s+del?\s+(?:se[nñ]or\s+)?[Pp]residente")
_DATELINE = (r"([A-Za-zÁÉÍÓÚÑáéíóúñ.'\- ]{2,50}?),\s*"
             r"(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚáéíóú]+)\s+de\s+(20\d{2})")
# every speech in the volumes ends with this boilerplate footer. The
# embedded presidencia.gov.co URL is often mangled across lines (soft
# hyphens rendered as U+00AC, spaces turned to hyphens) so it is not
# recovered; the footer is used purely as a hard speech boundary and
# stripped from the body. Very lenient on purpose.
_FOOTER = re.compile(
    r"\s*Fuente\s*:\s*Presidencia\s+de\s+la\s+[¬\-\s]*Rep[uú\wí]*"
    r".*?Edici[oó]n\s*:\s*Unidad\s+de\s+Implementaci[oó]n\s+del\s+Acuerdo\s+de\s+Paz\.?",
    re.I | re.S,
)
# also its translated form (appears in full_text_en only; harmless here)
_FOOTER_EN = re.compile(
    r"\s*Source\s*:\s*Presidency\s+of\s+the\s+Rep.*?"
    r"Edition\s*:\s*Peace\s+Agreement\s+Implementation\s+Unit\.?",
    re.I | re.S,
)
_PHOTO_BLOCK = re.compile(
    r"\s*(Agradecemos el apoyo de la Presidencia.*?material fotogr[aá]fico\s*:.*$)"
    r"|(\n[A-ZÁÉÍÓÚ][\wÁÉÍÓÚáéíóúñ .'\-]{2,40}\s*[-–]\s*Fot[oó]graf[oa]s?\s+[Pp]residencia.*$)"
    r"|(\s*Fot[oó]graf[oa]\s+[Pp]residencial?\s*[:.]?\s*[A-ZÁÉÍÓÚ][\wÁÉÍÓÚáéíóúñ .'\-]*$)",
    re.I | re.S,
)


def _get(url: str, retries: int = 4) -> Optional[bytes]:
    for attempt in range(1, retries + 1):
        try:
            r = curl_requests.get(url, impersonate="chrome", timeout=180, verify=False)
            if r.status_code == 200 and r.content[:4] == b"%PDF":
                return r.content
            print(f"  [warn] {r.status_code} for {url} (try {attempt})")
        except Exception as e:
            print(f"  [warn] {type(e).__name__} for {url} (try {attempt})")
        time.sleep(4 * attempt)
    return None


def _norm_month(word: str) -> Optional[int]:
    w = (word.lower().replace("á", "a").replace("é", "e").replace("í", "i")
         .replace("ó", "o").replace("ú", "u"))
    for k, v in _MONTHS.items():
        if k.replace("í", "i").replace("é", "e") == w:
            return v
    return None


def _iso(day: str, mon_word: str, year: str) -> Optional[str]:
    m = _norm_month(mon_word)
    if not m:
        return None
    try:
        return dt.date(int(year), m, int(day)).isoformat()
    except ValueError:
        return None


def _pdf_lines(pdf: bytes):
    """Return [(text, is_big, page_no)] in reading order, where is_big
    marks a line whose font is materially larger than the body font
    (titles, datelines, epigraphs and section sub-headings are all set
    larger/bold than the speech text in these volumes)."""
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    raw, sizes = [], {}
    for pno in range(doc.page_count):
        d = doc[pno].get_text("dict", sort=True)
        for b in d["blocks"]:
            for ln in b.get("lines", []):
                spans = ln.get("spans", [])
                txt = "".join(s["text"] for s in spans).strip()
                if not txt:
                    continue
                sz = max((s["size"] for s in spans), default=0)
                raw.append((txt, sz, pno + 1))
                sizes[round(sz)] = sizes.get(round(sz), 0) + len(txt)
    if not sizes:
        return []
    body_sz = max(sizes, key=sizes.get)
    return [(t, sz > body_sz + 1.0, p) for t, sz, p in raw]


_BOILER = re.compile(
    r"^\s*(Fuente\s*:\s*Presidencia|Source\s*:\s*Presidency|Edici[oó]n\s*:\s*Unidad|"
    r"Edition\s*:\s*Peace|https?://|[¬-]?[\wÁÉÍÓÚáéíóúñ¬]+(-[\wÁÉÍÓÚáéíóúñ¬]+)+-?\d{6}\.aspx|"
    r"Agradecemos el apoyo|"
    r"[A-ZÁÉÍÓÚ][\wÁÉÍÓÚáéíóúñ .'\-]{2,40}\s*[-–]\s*Fot[oó]graf[oa]|"
    r"Ideas vivas, ideas solidarias|los discursos del presidente\s*$|"
    r"Gustavo Petro en la Colombia\s*$|potencia de la vida\.?\s*$|"
    r"en la Colombia\s*$|Tomo \d+\s*$|Cartilla\s*(No\.?\s*)?\d*\s*$)", re.I)


def _split_speeches(pages_pdf: bytes):
    """Yield (title, iso_date, venue, body, start_page, orig_url).

    A speech begins at a run of large-font lines that contains both a
    "<header> del presidente ..." line and a "<Ciudad>, <D> de <mes> de
    <YYYY>" dateline. The whole large run becomes the title (any epigraph
    is folded in -- harmless); the body is every line after the run,
    small or large, up to the next such run. Boilerplate footer / photo
    lines are dropped."""
    lines = [ln for ln in _pdf_lines(pages_pdf) if not _BOILER.search(ln[0])]
    hdr = re.compile(_HEADER)
    dl = re.compile(_DATELINE)
    n = len(lines)

    cur = None  # (title, iso, venue, page, [body lines])

    def finish(c):
        if not c:
            return None
        body = _clean("\n".join(c[4]))
        if len(body) >= 250:
            return (c[0], c[1], c[2], body, c[3], "")
        return None

    i = 0
    while i < n:
        txt, big, page = lines[i]
        if big and hdr.search(txt):
            j0 = i
            while j0 > 0 and lines[j0 - 1][1]:
                j0 -= 1
            j1 = i
            while j1 + 1 < n and lines[j1 + 1][1]:
                j1 += 1
            run = lines[j0:j1 + 1]
            run_txt = " ".join(r[0] for r in run)
            dm = dl.search(run_txt)
            if dm:
                done = finish(cur)
                if done:
                    yield done
                iso = _iso(dm.group(2), dm.group(3), dm.group(4))
                venue = clean_text(dm.group(1)).strip(" .,-\n")
                title_txt = dl.sub("", run_txt)
                title_txt = re.sub(r"\s+", " ", title_txt).strip(" .,-:")
                if len(title_txt) > 200:
                    title_txt = title_txt[:200].rsplit(" ", 1)[0] + "…"
                cur = (title_txt, iso, venue, run[0][2], [])
                i = j1 + 1
                continue
        if cur is not None:
            cur[4].append(txt)
        i += 1

    done = finish(cur)
    if done:
        yield done


def _clean(text: str) -> str:
    text = text.translate({0x200b: None, 0x200c: None, 0x200d: None,
                           0xfeff: None, 0x00ad: None, 0x00ac: None})
    # de-hyphenate words split across line breaks
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_colombia_pdf(leader_config: dict, start_date: str, end_date: str,
                       limit: Optional[int] = None) -> List[Speech]:
    print(f"== Colombia ({leader_config['leader']}) -- official PDF volumes ==")
    speeches: List[Speech] = []
    seen = set()
    stats = {"vols": 0, "vol_fail": [], "entries": 0, "out_of_range": 0, "dup": 0}

    for url, is_excerpt in VOLUMES:
        pdf = _get(url)
        if pdf is None:
            stats["vol_fail"].append(url)
            continue
        stats["vols"] += 1
        vol_name = url.rsplit("/", 1)[-1]
        try:
            entries = list(_split_speeches(pdf))
        except Exception as e:
            print(f"  [warn] could not open {vol_name}: {e}")
            stats["vol_fail"].append(url)
            continue

        n_here = 0
        for title, iso, venue, body, page_no, orig_url in entries:
            stats["entries"] += 1
            if not body or len(body) < 250:
                continue
            if not in_date_range(iso, start_date, end_date):
                stats["out_of_range"] += 1
                continue
            key = (iso, re.sub(r"[^a-z0-9]", "", (title or "").lower())[:70])
            if key in seen:
                stats["dup"] += 1
                continue
            seen.add(key)

            tl = (title or "").lower()
            kind = ""
            if "entrevista" in tl:
                kind = " Row is an INTERVIEW (may include interviewer questions)."
            elif "declaraci" in tl and "conjunta" in tl:
                kind = " Row is a JOINT DECLARATION -- not solely the leader's words."
            elif "declaraci" in tl:
                kind = " Row is a press DECLARATION rather than a prepared address."

            excerpt_note = ""
            if is_excerpt or tl.startswith("apartes"):
                excerpt_note = (" EXCERPT: this volume publishes 'apartes' "
                                "(portions) of the speech, not the full text -- "
                                "the delivered speech is longer than what is here.")

            # prefer the original presidencia.gov.co URL recovered from
            # the speech's footer; fall back to a #page anchor into the
            # volume PDF
            src = orig_url if orig_url.startswith("http") else f"{url}#page={page_no}"
            speeches.append(Speech(
                country=leader_config["country"],
                leader=leader_config["leader"],
                role=leader_config["role"],
                date=iso,
                title=title,
                full_text=body,
                language="Spanish",
                source_url=src,
                likely_speech="yes",
                content_type="Speech",
                notes=(f"From the Colombian government's official compilation "
                       f"'Discursos del presidente Gustavo Petro' ({vol_name} "
                       f"page {page_no}), published at portalparalapaz.gov.co. "
                       f"Dateline venue: {venue or 'n/a'}. full_text/title are "
                       f"Spanish -- run translate_csv.py --language es."
                       + excerpt_note + kind),
            ))
            n_here += 1
            if limit and len(speeches) >= limit:
                print(f"  {vol_name}: +{n_here} (limit hit)")
                return speeches
        print(f"  {vol_name}: +{n_here} speeches in range")

    print(f"\n  PDF volumes: {stats['vols']} read, {len(stats['vol_fail'])} failed, "
          f"{stats['entries']} raw entries -> {len(speeches)} kept "
          f"({stats['out_of_range']} out of range, {stats['dup']} dup)")
    if stats["vol_fail"]:
        for u in stats["vol_fail"]:
            print(f"    FAILED VOLUME: {u}")
    return speeches
