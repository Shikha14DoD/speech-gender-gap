import time
import requests
from bs4 import BeautifulSoup

BASE = "https://www.predsednica-slo.si/sl/objave/govori"
HEADERS = {"User-Agent": "Mozilla/5.0"}
start = 0
found_any = False

while start <= 400:
    url = BASE if start == 0 else f"{BASE}?start={start}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    time.sleep(1)
    soup = BeautifulSoup(resp.text, "html.parser")
    list_container = soup.find("ul", class_="news-list")
    items = list_container.find_all("li") if list_container else []

    entries = []
    for li in items:
        a_tag = li.find("a", href=True)
        time_tag = li.find("time", attrs={"datetime": True})
        h2_tag = li.find("h2")
        if not a_tag or not time_tag:
            continue
        title = h2_tag.get_text(strip=True) if h2_tag else a_tag.get_text(strip=True)
        entries.append((time_tag["datetime"], title))

    if not entries:
        print(f"start={start}: no entries, stopping")
        break

    print(f"start={start}: {entries[0][0]} to {entries[-1][0]}")

    in_window = [e for e in entries if "2025-06-01" <= e[0] <= "2025-06-30"]
    if in_window:
        found_any = True
        print("  --> MATCH:")
        for d, t in in_window:
            print(f"      {d} | {t}")

    if entries[-1][0] < "2025-06-01":
        print("Passed the window, stopping.")
        break

    start += 16

if not found_any:
    print("No matches found in range.")