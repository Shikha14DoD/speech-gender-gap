"""
Fetches the live pm.gc.ca RSS feed (most recent ~10-15 items) and
checks whether each one is present in canada_carney.csv -- an
independent cross-check against our CDX-based URL discovery.

Run from your project root:
    python check_canada_rss.py
"""

import requests
import xml.etree.ElementTree as ET
import pandas as pd

resp = requests.get("https://www.pm.gc.ca/en/news.rss",
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
print("RSS fetch status:", resp.status_code)

root = ET.fromstring(resp.text)
items = root.findall(".//item")
print(f"RSS items found: {len(items)}")

df = pd.read_csv("data/processed/canada_carney.csv")
csv_urls = set(df["source_url"].str.rstrip("/"))

print()
print("Checking each RSS item against canada_carney.csv:")
for item in items:
    title = item.find("title").text
    link = item.find("link").text.rstrip("/") if item.find("link") is not None else None
    pubdate = item.find("pubDate").text if item.find("pubDate") is not None else "?"
    in_csv = link in csv_urls
    status = "FOUND" if in_csv else "MISSING"
    print(f"  [{status}] {pubdate} | {title[:70]} | {link}")