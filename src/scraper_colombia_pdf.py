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


def _page_texts(pdf: bytes) -> List[str]:
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    return [doc[i].get_text() for i in range(doc.page_count)]


def _mk_title(full: str, h_start: int, t_end: int) -> str:
    title = full[h_start: min(t_end, h_start + 240)]
    title = re.split(r"\n\s*\n", title)[0]
    title = clean_text(re.sub(r"\s+", " ", title)).strip(" .,-:")
    if len(title) > 170:
        title = title[:170].rsplit(" ", 1)[0] + "…"
    return title


def _body(full: str, start: int, end: int) -> str:
    seg = full[start:end]
    seg = _FOOTER.sub("", seg)
    seg = _FOOTER_EN.sub("", seg)
    seg = _PHOTO_BLOCK.sub("", seg)
    seg = _FOOTER.sub("", seg)  # a second speech's footer can precede a merge
    lines = seg.lstrip().split("\n")
    while lines and 0 < len(lines[0].strip()) < 95 and not re.search(r"[.:;!?]$", lines[0].strip()):
        lines.pop(0)
    return _clean("\n".join(lines))


def _split_speeches(pages: List[str]):
    """Yield (title, iso_date, venue, body, start_page, orig_url).

    Boundaries: every speech ends with the "Fuente: Presidencia ...
    Edicion: Unidad de Implementacion del Acuerdo de Paz" footer, so we
    cut on that first; within each footer-delimited chunk we locate the
    header + dateline. Chunks with a header but no footer (e.g. the last
    speech of a volume, or newer volumes that dropped the footer) fall
    back to header/dateline anchors."""
    offsets, acc = [], 0
    for p in pages:
        offsets.append(acc)
        acc += len(p) + 2
    full = "\n\n".join(pages)

    header_re = re.compile(_HEADER)
    date_re = re.compile(_DATELINE)

    # footer-delimited chunk boundaries
    cuts = [0]
    for fm in _FOOTER.finditer(full):
        cuts.append(fm.end())
    cuts.append(len(full))
    chunks = [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1)]

    for c_start, c_end in chunks:
        seg = full[c_start:c_end]
        if len(seg.strip()) < 300:
            continue
        # all header/dateline anchors inside this chunk
        anchors = []
        for hm in header_re.finditer(seg):
            win = seg[max(0, hm.start() - 350): hm.end() + 350]
            dm = date_re.search(win)
            if not dm:
                continue
            d_abs = max(0, hm.start() - 350) + dm.start()
            iso = _iso(dm.group(2), dm.group(3), dm.group(4))
            venue = clean_text(dm.group(1)).strip(" .,-\n")
            content_pos = max(hm.start(), d_abs + len(dm.group(0)))
            t_end = d_abs if d_abs > hm.start() else hm.start() + 200
            anchors.append((min(hm.start(), d_abs), content_pos,
                            _mk_title(seg, hm.start(), t_end), iso, venue))
        anchors.sort()
        merged = []
        for a in anchors:
            if merged and a[0] - merged[-1][0] < 200:
                continue
            merged.append(a)
        if not merged:
            continue
        for j, (pos, content_pos, title, iso, venue) in enumerate(merged):
            seg_end = merged[j + 1][0] if j + 1 < len(merged) else len(seg)
            body = _body(seg, content_pos, seg_end)
            if len(body) < 250:
                continue
            abs_pos = c_start + pos
            start_page = max(k for k, off in enumerate(offsets) if off <= abs_pos)
            yield title, iso, venue, body, start_page + 1, ""


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
            pages = _page_texts(pdf)
        except Exception as e:
            print(f"  [warn] could not open {vol_name}: {e}")
            stats["vol_fail"].append(url)
            continue

        n_here = 0
        for title, iso, venue, body, page_no, orig_url in _split_speeches(pages):
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
