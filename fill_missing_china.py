"""
One-off: fetches a specific known article URL using curl_cffi (browser
impersonation), since this particular page appears to serve a stripped
placeholder to non-browser-looking requests -- same category of issue
already solved for the Wayback Machine and Samoa elsewhere in this
project.
"""

import re
import pandas as pd
from curl_cffi import requests as curl_requests

from src.config_loader import load_config, get_leader_config
from src.text_processing import parse_date_loose, in_date_range, classify_as_speech, classify_content_type
from src.utils import clean_text, Speech, write_csv
from bs4 import BeautifulSoup

MISSING_URLS = [
    "http://english.scio.gov.cn/topnews/2024-05/07/content_117170444.htm",
]


def fetch_with_curl_cffi(url: str, leader_config: dict):
    resp = curl_requests.get(url, impersonate="chrome", timeout=30)
    if resp.status_code != 200:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")

    title = None
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = clean_text(og_title["content"])
    if not title:
        title_tag = soup.find("title")
        title = clean_text(title_tag.get_text(separator=" ")) if title_tag else url

    date_iso = None
    date_meta = soup.find("meta", attrs={"name": "publishdate"})
    if date_meta and date_meta.get("content"):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", date_meta["content"])
        if m:
            date_iso = m.group(1)

    content_div = soup.find("article") or soup.find("main") or soup
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
        notes="Fetched via curl_cffi (browser impersonation) -- plain "
              "requests fetch returned a stripped placeholder page "
              "for this specific article.",
    )


def main():
    config = load_config()
    leader_config = get_leader_config("China", config)
    date_range = leader_config.get("date_range", config["date_range"])

    existing_df = pd.read_csv("data/processed/china.csv")
    existing_urls = set(existing_df["source_url"])

    new_rows = []
    for url in MISSING_URLS:
        if url in existing_urls:
            print(f"  already have: {url}")
            continue
        article = fetch_with_curl_cffi(url, leader_config)
        if article is None:
            print(f"  [skip] could not fetch: {url}")
            continue
        if not in_date_range(article.date, date_range["start"], date_range["end"]):
            print(f"  [skip] outside date range ({article.date}): {url}")
            continue
        new_rows.append(article)
        print(f"  added: {article.title}")

    if new_rows:
        write_csv(new_rows, "data/processed/china.csv")
    print(f"\nDone. Added {len(new_rows)} new row(s).")


if __name__ == "__main__":
    main()