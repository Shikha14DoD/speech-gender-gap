"""
Scraper for Slovenia -- Nataša Pirc Musar (President), predsednica-slo.si.

Unlike Denmark/Italy, this site's listing page works fine with a plain
HTTP request -- no JavaScript rendering, no bot-detection block. Clean
pagination via ?start=N (16 items per page).

IMPORTANT: this is a general news feed, not a speeches-only feed. It
mixes real remarks/speeches with routine news (ambassador credentials,
condolence messages, bilateral meeting announcements). Filtering relies
on classify_as_speech() -- expect a high proportion of "maybe" results
that need manual review, same caveat as documented for this site from
the start of the project.
"""

import re
from typing import List, Optional

from src.utils import get, soupify, clean_text, Speech
from src.text_processing import parse_date_loose, in_date_range, classify_as_speech, classify_content_type

BASE_LISTING = "https://www.predsednica-slo.si/en/news/all"
PAGE_SIZE = 16


def parse_slovenia(leader_config: dict, start_date: str, end_date: str,
                    limit: Optional[int] = None) -> List[Speech]:
    print("== Slovenia ==")
    speeches: List[Speech] = []
    start_param = 0

    while True:
        url = BASE_LISTING if start_param == 0 else f"{BASE_LISTING}?start={start_param}"
        resp = get(url)
        if resp is None:
            break
        soup = soupify(resp)

        links = sorted(set(
            a["href"] for a in soup.find_all("a", href=True)
            if "/en/news/" in a["href"]
            and "/en/news/all" not in a["href"]  # excludes listing page AND its pagination (?start=N)
            and "/en/news/rss" not in a["href"]
        ))

        if not links:
            print(f"  [info] no more articles at start={start_param}, stopping.")
            break

        print(f"  page start={start_param}: checking {len(links)} articles...")
        for href in links:
            full_url = href if href.startswith("http") else f"https://www.predsednica-slo.si{href}"
            article = _fetch_article(full_url, leader_config)
            if article is None:
                continue
            if article.likely_speech == "no":
                continue
            if in_date_range(article.date, start_date, end_date):
                speeches.append(article)
            if limit and len(speeches) >= limit:
                return speeches

        start_param += PAGE_SIZE
        if start_param > 400:  # safety guard, ~19 pages seen live
            break

    return speeches


def _fetch_article(url: str, leader_config: dict) -> Optional[Speech]:
    resp = get(url)
    if resp is None:
        return None
    soup = soupify(resp)

    title_tag = soup.find("h1")
    title = clean_text(title_tag.get_text(separator=" ")) if title_tag else url
    page_text = soup.get_text()

    # Best source: a <meta> tag carrying an ISO date directly (seen live
    # as something like meta-NewsDate: 2025-07-24T00:00:00Z) -- far more
    # reliable than parsing visible text. Fall back to the visible
    # "Publish date  <City>, DD Mon YYYY" text if no such meta tag exists.
    date_iso = None
    for meta_tag in soup.find_all("meta"):
        attr_name = (meta_tag.get("name") or meta_tag.get("property") or "").lower()
        if "date" in attr_name:
            content = meta_tag.get("content", "")
            iso_match = re.match(r"(\d{4}-\d{2}-\d{2})", content)
            if iso_match:
                date_iso = iso_match.group(1)
                break

    if date_iso is None:
        date_match = re.search(
            r"Publish date\s+\w+,\s*(\d{1,2}\s+\w{3,9}\s+\d{4})", page_text
        )
        if date_match:
            date_iso = parse_date_loose(date_match.group(1))

    content_div = soup.find("main") or soup.find("article") or soup
    paragraphs = [clean_text(p.get_text(separator=" ")) for p in content_div.find_all("p")]
    full_text = clean_text("\n\n".join(p for p in paragraphs if p))

    return Speech(
        country=leader_config["country"],
        leader=leader_config["leader"],
        role=leader_config["role"],
        date=date_iso,
        title=title,
        full_text=full_text,
        language="English",
        source_url=url,
        likely_speech=classify_as_speech(title),
        content_type=classify_content_type(title),
        notes="Feed is general news, NOT speeches-only -- likely_speech is "
              "a keyword heuristic only. Manually review 'maybe' rows and "
              "spot-check 'yes'/'no' before treating as final.",
    )