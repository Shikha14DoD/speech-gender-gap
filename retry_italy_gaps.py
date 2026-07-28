"""
One-off: retries Wayback CDX discovery for just the two year-chunks that
failed during the main Italy scrape (2022: 503 error, 2024: timeout),
then fetches and appends any newly-found real Meloni entries directly
to italy.csv -- without re-running (and re-deleting) the full dataset.
"""

import pandas as pd

from src.config_loader import load_config, get_leader_config
from src.scraper_italy import _fetch_article
from src.text_processing import in_date_range
from src.wayback_helper import _query_chunk
from src.utils import write_csv

CDX_PREFIX = "governo.it/en/articolo/"

# The two gaps identified by compare_italy.py
GAP_CHUNKS = [
    # ("2022-10-22", "2022-12-31"),
    # ("2024-01-01", "2024-12-31"),
    # ("2025-01-01", "2025-12-31"),
    #   # found exactly 500 last time -- likely truncated at the limit
      ("2025-01-01", "2025-12-31"),
]


def main():
    config = load_config()
    leader_config = get_leader_config("Italy", config)
    start_date = config["date_range"]["start"]
    end_date = config["date_range"]["end"]

    existing_df = pd.read_csv("data/processed/italy.csv")
    existing_urls = set(existing_df["source_url"])
    print(f"Currently have {len(existing_df)} rows.")

    all_new_urls = []
    for chunk_from, chunk_to in GAP_CHUNKS:
        print(f"\nRetrying {chunk_from} to {chunk_to}...")
        urls = _query_chunk(CDX_PREFIX, chunk_from, chunk_to, limit=1000)
        print(f"  -> {len(urls)} URLs found")
        all_new_urls.extend(urls)

    print(f"\nTotal candidates from gap retry: {len(all_new_urls)}")

    new_rows = []
    for url in all_new_urls:
        # Normalize the same way compare_italy.py does, to check against
        # what we already have.
        clean_url = url.replace("https://www.", "https://")
        if clean_url in existing_urls or url in existing_urls:
            continue
        article = _fetch_article(url, leader_config)
        if article is None:
            continue
        if article.likely_speech == "no":
            continue
        if not in_date_range(article.date, start_date, end_date):
            continue
        new_rows.append(article)
        print(f"  added: {article.title}")

    if new_rows:
        write_csv(new_rows, "data/processed/italy.csv")
    print(f"\nDone. Added {len(new_rows)} new rows.")


if __name__ == "__main__":
    main()