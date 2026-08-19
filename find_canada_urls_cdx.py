"""
Queries the Wayback Machine CDX API to find historical URLs under
pm.gc.ca/en/news/speeches/ and pm.gc.ca/en/news/statements/ (and other
news categories), since the site's own listing page is JavaScript-
rendered and can't be scraped directly, but individual article pages
are fully scrapeable once we have their URLs.

Run from your project root:
    python find_canada_urls_cdx.py
"""

import requests
import json

CATEGORIES = ["speeches", "statements", "videos"]  # news-releases/readouts excluded --
                                          # see scraper_canada.py docstring. "videos" added
                                          # to cover Trudeau-era content, since the live
                                          # /en/videos listing only shows the current
                                          # government's era (same issue as /en/news/).

all_urls = set()

for category in CATEGORIES:
    print(f"Querying CDX for category: {category}")
    if category == "videos":
        cdx_path = "pm.gc.ca/en/videos/"
    else:
        cdx_path = f"pm.gc.ca/en/news/{category}/"

    cdx_url = (
        "http://web.archive.org/cdx/search/cdx"
        f"?url={cdx_path}"
        "&matchType=prefix"
        "&output=json"
        "&filter=statuscode:200"
        "&collapse=urlkey"
        "&limit=10000"
    )
    try:
        resp = requests.get(cdx_url, timeout=60)
        print(f"  Status: {resp.status_code}, response length: {len(resp.text)}")
        if len(resp.text.strip()) < 5:
            print(f"  Empty response. URL queried: {cdx_url}")
            continue
        data = resp.json()
        if len(data) <= 1:
            print(f"  No results for {category}")
            continue
        header = data[0]
        url_idx = header.index("original")
        for row in data[1:]:
            url = row[url_idx]
            all_urls.add(url)
        print(f"  Found {len(data) - 1} entries")
    except Exception as e:
        print(f"  [error] {e}")

print()
print(f"Total unique URLs found: {len(all_urls)}")

import re
date_pattern = re.compile(r"/(news/[a-z-]+|videos)/(2024|2025|2026)/\d{2}/\d{2}/")
filtered_urls = set(u for u in all_urls if date_pattern.search(u))
print(f"URLs matching 2024-2026 with a real date+slug pattern: {len(filtered_urls)}")

# Supplement with the live RSS feed's most recent items -- CDX/Wayback
# lags behind "today" by some unpredictable amount (can be days to
# weeks), so very recent articles may not be crawled yet and would be
# silently missing otherwise. RSS reflects the site in real time.
print()
print("Supplementing with live RSS feed for recency gap...")
try:
    import xml.etree.ElementTree as ET
    rss_resp = requests.get("https://www.pm.gc.ca/en/news.rss",
                             headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    root = ET.fromstring(rss_resp.text)
    rss_added = 0
    for item in root.findall(".//item"):
        link_el = item.find("link")
        if link_el is None or link_el.text is None:
            continue
        link = link_el.text.split("?")[0]
        if ("/speeches/" in link or "/statements/" in link) and link not in filtered_urls:
            filtered_urls.add(link)
            rss_added += 1
    print(f"  Added {rss_added} additional URL(s) from RSS not yet in Wayback")
except Exception as e:
    print(f"  [warn] RSS supplement failed: {e}")

filtered_urls = sorted(filtered_urls)

with open("canada_urls_from_cdx.txt", "w", encoding="utf-8") as f:
    for url in filtered_urls:
        f.write(url + "\n")

print("Saved to canada_urls_from_cdx.txt")