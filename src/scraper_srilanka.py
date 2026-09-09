"""
Scraper for Sri Lanka -- three leaders in the 2023-2026 window:

  Ranil Wickremesinghe  (President, -> 22 Sep 2024)   Q983402
  Anura Kumara Dissanayake ("AKD", President, 23 Sep 2024 -> )   Q4777855
  Harini Amarasuriya    (Prime Minister, 24 Sep 2024 -> )   Q98298397  (F)

TEXT route. A companion `scraper_srilanka_video.py` covers the President's
Media Division YouTube channel (Sinhala speeches, YouTube auto-caption
English) and `merge_srilanka.py` combines the two.

WHY ARCHIVE-FIRST
-----------------
The old Wickremesinghe/Rajapaksa-era Presidential Secretariat site was a
dated WordPress at `presidentsoffice.gov.lk/index.php/YYYY/MM/DD/<slug>`
-- now 404 on the live domain (replaced with a JS-rendered Next.js SPA by
the incoming administration), but ~4,250 URLs are archived in the Wayback
Machine with the date in the slug. The current AKD-era sites
(`presidentsoffice.gov.lk`, `pmd.gov.lk`) and the PM's Office
(`pmoffice.gov.lk`) are all client-rendered SPAs with no usable static
HTML / REST API, so those too are taken from Wayback snapshots, with a
live fetch tried first where a URL still resolves.

Sri Lankan official speech pages are published in English (the sites also
carry Sinhala/Tamil versions on separate URLs) -- text rows are English,
`translated="no"`.
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
MAX_SNAPSHOTS = 8

RANIL_END = "2024-09-22"          # last full day of the Wickremesinghe presidency
AKD_START = "2024-09-23"

# Wayback discovery prefixes.  (prefix, is_old_wordpress)
_PREFIXES = [
    ("presidentsoffice.gov.lk/index.php/*", True),
    ("presidentsoffice.gov.lk/*", False),
    ("www.presidentsoffice.gov.lk/*", False),
    ("pmd.gov.lk/*", False),
    ("www.pmd.gov.lk/*", False),
    ("pmoffice.gov.lk/*", False),
    ("www.pmoffice.gov.lk/*", False),
]

# Slug / title markers of a genuine verbatim transcript page (the SL
# official sites publish mostly third-person news; real transcripts are
# a minority and are consistently titled).
_TRANSCRIPT_SLUG = re.compile(
    r"full[- ]text|"
    r"(speech|statement|address|remarks|declaration|message|lecture|"
    r"keynote)[- ](by|of|made[- ]by|delivered|to[- ]the|at[- ]the)|"
    r"(delivered|made)[- ]by[- ](his[- ]excellency|president|prime[- ]minister)|"
    r"policy[- ]statement|address[- ]to[- ]the[- ]nation|budget[- ]speech|"
    r"throne[- ]speech|inaugural[- ]address|independence[- ]day[- ](speech|address)",
    re.I,
)
# title markers of a genuine transcript (broader than the slug rx)
_TRANSCRIPT_TITLE = re.compile(
    r"full[- ]text|"
    r"\b(speech|statement|address|remarks|lecture|keynote address|"
    r"policy statement)\b\s+(by|of|made by|delivered by|to the|at the|"
    r"of (his excellency|the president|the prime minister))|"
    r"address to the nation|budget speech|throne speech|"
    r"delivered by (his excellency|president|prime minister)",
    re.I,
)


def _cget(url: str, timeout: int, retries: int = 4) -> Optional[curl_requests.Response]:
    for attempt in range(1, retries + 1):
        try:
            r = curl_requests.get(url, impersonate="chrome", timeout=timeout, verify=False)
            time.sleep(DELAY)
            if r.status_code == 200:
                return r
            if r.status_code in (403, 429, 502, 503):
                time.sleep(5 * attempt)
        except Exception:
            time.sleep(3 * attempt)
    return None


# ------------------------------------------------------------------ discovery
def _cdx(pattern: str, year: int) -> List[str]:
    q = (f"{CDX}?url={pattern}&output=json&collapse=urlkey&fl=original"
         f"&filter=statuscode:200&from={year}0101&to={year}1231&limit=40000")
    r = _cget(q, CDX_TIMEOUT, retries=5)
    if r is None or not r.text.strip():
        print(f"  [warn] CDX failed: {pattern} {year}")
        return []
    try:
        return [row[0] for row in json.loads(r.text)[1:]]
    except json.JSONDecodeError:
        return []


def _norm(u: str) -> str:
    u = u.split("?")[0].split("#")[0]
    u = u.replace("http://", "https://").replace("https://www.", "https://")
    return u.rstrip("/").lower()


def discover_urls(start_date: str, end_date: str) -> List[str]:
    """Return only URLs whose slug looks like a verbatim transcript --
    the SL sites publish thousands of news items and only a small,
    consistently-titled minority are actual speeches."""
    start_year = max(2022, int(start_date[:4]) - 1)
    end_year = min(dt.date.today().year, int(end_date[:4]))
    seen: dict = {}
    for prefix, _old in _PREFIXES:
        for year in range(start_year, end_year + 1):
            rows = _cdx(prefix, year)
            add = 0
            for u in rows:
                if "/_next/" in u or re.search(r"\.(js|css|woff2?|png|jpe?g|svg|ico)$", u, re.I):
                    continue
                slug = u.split("/")[-1] or u.split("/")[-2]
                if not (_TRANSCRIPT_SLUG.search(u) or u.lower().endswith("_en.pdf")):
                    continue
                k = _norm(u)
                if k in seen:
                    continue
                seen[k] = u.replace("http://", "https://")
                add += 1
            if rows:
                print(f"  CDX {prefix} {year}: {len(rows)} rows (+{add} transcript-slug, total {len(seen)})")
    return sorted(seen.values())


# ------------------------------------------------------------------ fetch
def _is_shell(html: str) -> bool:
    if "<title>" not in html.lower():
        return True
    low = html.lower()
    # Next.js / SPA shell with no server-rendered article
    return ("__next" in low and "entry-content" not in low
            and "article" not in low and len(BeautifulSoup(html, "html.parser")
                                              .get_text(strip=True)) < 600)


def _snapshots(url: str) -> List[str]:
    q = (f"{CDX}?url={url}&output=json&fl=timestamp&filter=statuscode:200"
         f"&collapse=digest&limit=60")
    r = _cget(q, CDX_TIMEOUT, retries=3)
    if r is None or not r.text.strip():
        return []
    try:
        return sorted({row[0] for row in json.loads(r.text)[1:]}, reverse=True)
    except json.JSONDecodeError:
        return []


def _body_el(soup: BeautifulSoup):
    for sel in (".entry-content", "article .content", ".post-content",
                ".single-content", ".td-post-content", "article"):
        els = [e for e in soup.select(sel) if e.get_text(strip=True)]
        if els:
            return max(els, key=lambda e: len(e.get_text()))
    # last resort: the largest <div> of prose
    divs = [d for d in soup.find_all("div") if len(d.get_text(strip=True)) > 500]
    return max(divs, key=lambda d: len(d.get_text()), default=None)


def fetch(url: str) -> Tuple[Optional[BeautifulSoup], str]:
    """Live first, then newest good Wayback snapshot. Returns (soup, source)."""
    r = _cget(url, PAGE_TIMEOUT, retries=2)
    if r is not None and not _is_shell(r.text):
        s = BeautifulSoup(r.text, "html.parser")
        if _body_el(s) is not None:
            return s, "live"
    for ts in _snapshots(url)[:MAX_SNAPSHOTS]:
        rr = _cget(f"{WB}/{ts}id_/{url}", PAGE_TIMEOUT, retries=2)
        if rr is None or _is_shell(rr.text):
            continue
        s = BeautifulSoup(rr.text, "html.parser")
        b = _body_el(s)
        if b is not None and len(b.get_text(strip=True)) > 400:
            return s, f"wayback:{ts}"
    return None, ""


# ------------------------------------------------------------------ parse
_MONTHS = ("january february march april may june july august september "
          "october november december").split()


def _slug_date(url: str) -> Optional[str]:
    m = re.search(r"/index\.php/(\d{4})/(\d{2})/(\d{2})/", url)
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return None


def _text_date(soup: BeautifulSoup) -> Optional[str]:
    t = soup.find("time", attrs={"datetime": True})
    if t and re.match(r"\d{4}-\d{2}-\d{2}", t["datetime"]):
        return t["datetime"][:10]
    for m in soup.find_all("meta"):
        p = (m.get("property") or m.get("name") or "").lower()
        if "published" in p or p in ("article:published_time", "date"):
            v = m.get("content", "")
            mm = re.match(r"(\d{4}-\d{2}-\d{2})", v)
            if mm:
                return mm.group(1)
    txt = soup.get_text(" ", strip=True)[:400]
    m = re.search(r"(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s+(20\d{2})", txt, re.I)
    if m:
        try:
            return dt.date(int(m.group(3)), _MONTHS.index(m.group(2).lower()) + 1,
                           int(m.group(1))).isoformat()
        except ValueError:
            pass
    return None


def _title(soup: BeautifulSoup, url: str) -> str:
    h = soup.select_one("h1.entry-title, h1")
    if h and h.get_text(strip=True):
        return clean_text(h.get_text(" ", strip=True))
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return clean_text(og["content"])
    t = soup.find("title")
    if t:
        return clean_text(re.sub(r"\s*[|–-]\s*Presiden.*$", "", t.get_text(" ", strip=True)))
    return url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")


def _which_leader(date: Optional[str], url: str, title: str) -> Optional[Tuple[str, str]]:
    tl = title.lower()
    is_pm_domain = "pmoffice.gov.lk" in url
    if is_pm_domain or "prime minister" in tl or re.search(r"\bpm\b", tl):
        if date and date >= AKD_START:
            return "Harini Amarasuriya", "Prime Minister"
        # a PM speech before Sep 2024 would be Dinesh Gunawardena -> out of scope
        return None
    # presidential
    if date and date <= RANIL_END:
        return "Ranil Wickremesinghe", "President"
    if date and date >= AKD_START:
        return "Anura Kumara Dissanayake", "President"
    if date is None:
        # undated -- guess by title
        if "wickremesinghe" in tl:
            return "Ranil Wickremesinghe", "President"
        if "dissanayake" in tl or "anura kumara" in tl:
            return "Anura Kumara Dissanayake", "President"
    return None


def _wb_pdf(url: str) -> Optional[bytes]:
    for ts in _snapshots(url)[:4]:
        r = _cget(f"{WB}/{ts}id_/{url}", PAGE_TIMEOUT, retries=2)
        if r is not None and r.content[:4] == b"%PDF":
            return r.content
    return None


def _pdf_text_and_title(pdf: bytes) -> Tuple[str, str]:
    import pymupdf
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    full = "\n".join(doc[i].get_text() for i in range(doc.page_count))
    full = clean_text(full)
    full = re.sub(r"\n\s*\n+", "\n\n", full).strip()
    first = next((l.strip() for l in full.split("\n") if len(l.strip()) > 12), "")
    return full, first[:180]


def parse_srilanka(leader_config: dict, start_date: str, end_date: str,
                   limit: Optional[int] = None) -> List[Speech]:
    print("== Sri Lanka (Wickremesinghe / Dissanayake / Amarasuriya) -- text ==")
    urls = discover_urls(start_date, end_date)
    print(f"  {len(urls)} transcript-slug candidate URLs")

    speeches: List[Speech] = []
    stats = {"no_page": 0, "not_transcript": 0, "not_leader": 0, "out_of_range": 0}
    by: dict = {}

    for i, url in enumerate(urls, 1):
        if i % 40 == 0:
            print(f"  [{i}/{len(urls)}] kept={len(speeches)} no_page={stats['no_page']} "
                  f"not_transcript={stats['not_transcript']}")

        is_pdf = url.lower().endswith(".pdf")
        if is_pdf:
            r = _cget(url, PAGE_TIMEOUT, retries=2) or _wb_pdf(url)
            if r is None:
                stats["no_page"] += 1
                continue
            body, title = _pdf_text_and_title(r if isinstance(r, bytes) else r.content)
            date = _text_date(BeautifulSoup(f"<p>{body[:400]}</p>", "html.parser"))
            src = "live/pdf"
        else:
            soup, src = fetch(url)
            if soup is None:
                stats["no_page"] += 1
                continue
            title = _title(soup, url)
            date = _slug_date(url) or _text_date(soup)
            body_el = _body_el(soup)
            for tag in body_el.select("script, style, .sharedaddy, .jp-relatedposts, "
                                      "nav, footer, .related, .social-share"):
                tag.decompose()
            body = clean_text(body_el.get_text("\n"))
            body = re.sub(r"\n\s*\n+", "\n\n", body).strip()

        # require a genuine-transcript title AND enough body
        if not (_TRANSCRIPT_TITLE.search(title) or _TRANSCRIPT_SLUG.search(url)):
            stats["not_transcript"] += 1
            continue
        if len(body) < 400:
            stats["not_transcript"] += 1
            continue

        who = _which_leader(date, url, title)
        if who is None:
            stats["not_leader"] += 1
            continue
        leader, role = who

        if not in_date_range(date, start_date, end_date):
            stats["out_of_range"] += 1
            continue

        if src.startswith("live"):
            provenance = "live page" + ("/PDF" if is_pdf else "")
        else:
            provenance = "recovered from Internet Archive snapshot " + src.split(":", 1)[-1]
        domain = re.sub(r"https?://", "", url).split("/")[0]
        speeches.append(Speech(
            country="Sri Lanka",
            leader=leader,
            role=role,
            date=date,
            title=title,
            full_text=body,
            language="English",
            source_url=url,
            likely_speech=classify_as_speech(title),
            content_type=classify_content_type(title),
            notes=(f"Text transcript from Sri Lanka's official channels "
                   f"({provenance}). Domain: {domain}. Published in English "
                   f"(SL official sites carry separate Sinhala/Tamil versions). "
                   f"No translation."),
        ))
        by[leader] = by.get(leader, 0) + 1
        if limit and len(speeches) >= limit:
            break

    print(f"\n  Sri Lanka text done: {len(speeches)} kept {by} | "
          f"no_page={stats['no_page']} not_transcript={stats['not_transcript']} "
          f"not_leader={stats['not_leader']} out_of_range={stats['out_of_range']}")
    return speeches
