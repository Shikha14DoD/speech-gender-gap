"""
Standalone test: validates _fetch_article extraction logic for AMLO
on one known article URL, without going through full pagination.

Run from your project root:
    python test_amlo_single.py
"""

from src.scraper_amlo import _fetch_article

TEST_URL = "https://www.gob.mx/amlo/articulos/version-estenografica-conferencia-de-prensa-del-presidente-andres-manuel-lopez-obrador-del-10-de-abril-de-2024"

leader_config = {
    "country": "Mexico",
    "leader": "Andrés Manuel López Obrador",
    "role": "President",
}

article = _fetch_article(TEST_URL, leader_config, listing_date="2024-04-10")

if article is None:
    print("FAILED: extraction returned None (text too short or empty).")
else:
    print("SUCCESS")
    print("Date:", article.date)
    print("Title:", article.title)
    print("Text length:", len(article.full_text))
    print()
    print("First 500 chars:")
    print(article.full_text[:500])
    print()
    print("Last 300 chars:")
    print(article.full_text[-300:])