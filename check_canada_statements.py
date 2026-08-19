import requests
from bs4 import BeautifulSoup
import sys

urls = sys.argv[1:]
for url in urls:
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    soup = BeautifulSoup(resp.text, "html.parser")
    all_matches = soup.find_all("div", class_="field--name-body")
    print(url)
    print(f"  Total divs with class field--name-body: {len(all_matches)}")
    for i, div in enumerate(all_matches):
        p_count = len(div.find_all("p"))
        chars = len(div.get_text(strip=True))
        print(f"   [{i}] <p> count: {p_count}, chars: {chars}, snippet: {repr(div.get_text(strip=True)[:80])}")
    print()