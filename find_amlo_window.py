"""
Pages through the AMLO archive listing until it finds entries in the
2024-06-10 to 2024-06-20 window, then prints them for comparison
against mexico_amlo.csv.

Run from your project root:
    python find_amlo_window.py
"""

import time
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
import re

BASE = "https://www.gob.mx/amlo/archivo/articulos"
page = 1
found_any = False

while page <= 40:
    url = f"{BASE}?order=DESC&page={page}"
    for attempt in range(5):
        resp = curl_requests.get(url, impersonate="chrome", timeout=30)
        if resp.status_code == 200:
            break
        time.sleep(3)
    else:
        print(f"page {page}: still failing after 5 attempts, status {resp.status_code} -- SKIPPING (real gap risk)")
        page += 1
        continue
    time.sleep(1.5)

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = soup.find_all("article")
    if not articles:
        print(f"page {page}: no articles, stopping")
        break

    page_dates = []
    for art in articles:
        time_tag = art.find("time", attrs={"date": True})
        h2_tag = art.find("h2")
        a_tag = art.find("a", href=True)
        if not time_tag or not a_tag:
            continue
        m = re.match(r"(\d{4}-\d{2}-\d{2})", time_tag["date"])
        d = m.group(1) if m else None
        title = h2_tag.get_text(strip=True) if h2_tag else a_tag.get_text(strip=True)
        page_dates.append((d, title, a_tag["href"]))

    if page_dates:
        print(f"page {page}: {page_dates[0][0]} to {page_dates[-1][0]}")

    in_window = [d for d in page_dates if d[0] and "2024-06-10" <= d[0] <= "2024-06-20"]
    if in_window:
        found_any = True
        print(f"  --> MATCH on page {page}:")
        for d, title, href in in_window:
            print(f"      {d} | {title} | {href}")

    if page_dates and page_dates[-1][0] and page_dates[-1][0] < "2024-06-10":
        print("Passed the window, stopping.")
        break

    page += 1

if not found_any:
    print("No matches found in range.")