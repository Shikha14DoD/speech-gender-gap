"""
Diagnostic: fetches one Moldova listing page and one article page,
prints the actual HTML structure so we can write accurate selectors.

No bot detection on this site -- plain `requests` works fine, no
curl_cffi needed.

Run from your project root:
    python diagnose_moldova.py
"""

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

print("=== LISTING PAGE ===")
resp = requests.get("https://presedinte.md/eng/discursuri", headers=HEADERS, timeout=30)
print("Status:", resp.status_code)
soup = BeautifulSoup(resp.text, "html.parser")

# Try to find the main content container -- print candidates
for tag_name, attrs in [("div", {"class": "content"}), ("div", {"id": "content"}),
                          ("div", {"class": "news"}), ("ul", {}), ("div", {"class": "list"})]:
    found = soup.find(tag_name, attrs) if attrs else None
    if found:
        print(f"Found <{tag_name} {attrs}>")

# Print all <a> tags that link to /eng/discursuri/ (article links) with surrounding context
print()
print("Article links found (first 5):")
links = [a for a in soup.find_all("a", href=True) if "/eng/discursuri/" in a["href"]
         and a["href"].rstrip("/") != "https://presedinte.md/eng/discursuri"
         and "index/page" not in a["href"]]
for a in links[:5]:
    print(" href:", a["href"])
    print(" parent tag:", a.parent.name, "class:", a.parent.get("class"))
    print(" grandparent tag:", a.parent.parent.name, "class:", a.parent.parent.get("class"))
    print()

print()
print("Full HTML of first article block (to find date tag):")
first_article = soup.find("article", class_="block")
print(str(first_article)[:800] if first_article else "NOT FOUND")
resp2 = requests.get(
    "https://presedinte.md/eng/discursuri/president-maia-sandus-message-on-the-day-of-ukrainian-statehood",
    headers=HEADERS, timeout=30
)
print("Status:", resp2.status_code)
soup2 = BeautifulSoup(resp2.text, "html.parser")

h1 = soup2.find("h1")
print("H1:", h1.get_text(strip=True) if h1 else "NOT FOUND")
print("H1 parent:", h1.parent.name, "class:", h1.parent.get("class") if h1 else None)

# Look for date near the h1
if h1:
    prev = h1.find_previous(string=True)
    print("Text immediately before H1:", repr(prev.strip()) if prev else None)

# Print paragraph count and first few
ps = soup2.find_all("p")
print()
print(f"Total <p> tags: {len(ps)}")
for p in ps[:5]:
    print(" -", repr(p.get_text(strip=True)[:100]), "| class:", p.get("class"), "| parent class:", p.parent.get("class"))