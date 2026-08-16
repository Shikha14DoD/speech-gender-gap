"""
Pages through the Moldova archive listing until it finds entries in the
2024-06-01 to 2024-12-31 window, then prints them for comparison
against moldova.csv.

Run from your project root:
    python find_moldova_window.py
"""

import time
import requests
from bs4 import BeautifulSoup

BASE = "https://presedinte.md/eng/discursuri"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
page = 1
found_any = False

while page <= 30:
    url = BASE if page == 1 else f"{BASE}/index/page:{page}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    time.sleep(1)
    if resp.status_code != 200:
        print(f"page {page}: status {resp.status_code}")
        page += 1
        continue

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = soup.find_all("article", class_="block")
    if not articles:
        print(f"page {page}: no articles, stopping")
        break

    page_entries = []
    for art in articles:
        time_tag = art.find("time", attrs={"datetime": True})
        a_tag = art.find("a", href=True)
        h2_tag = art.find("h2")
        if not time_tag or not a_tag:
            continue
        d = time_tag["datetime"].strip()[:10]
        title = h2_tag.get_text(strip=True) if h2_tag else a_tag.get_text(strip=True)
        page_entries.append((d, title))

    if page_entries:
        print(f"page {page}: {page_entries[0][0]} to {page_entries[-1][0]}")

    in_window = [e for e in page_entries if "2024-01-01" <= e[0] <= "2024-05-31"]
    if in_window:
        found_any = True
        print(f"  --> MATCH on page {page}:")
        for d, title in in_window:
            print(f"      {d} | {title}")

    if page_entries and page_entries[-1][0] < "2024-01-01":
        print("Passed the window, stopping.")
        break

    page += 1

if not found_any:
    print("No matches found in range.")