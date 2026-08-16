import requests
from bs4 import BeautifulSoup
import sys

url = sys.argv[1] if len(sys.argv) > 1 else input("Paste the source_url: ")

resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
soup = BeautifulSoup(resp.text, "html.parser")

print("Total <li> tags:", len(soup.find_all("li")))
print("Total <p> tags:", len(soup.find_all("p")))

print()
print("First 5 <li> tags with parent info:")
for li in soup.find_all("li")[:5]:
    print(" -", repr(li.get_text(strip=True)[:100]), "| parent:", li.parent.name, li.parent.get("class"))

# Also check the article-type container's full content, all children tag types
container = soup.find(class_="article-type")
if container:
    parent = container if container.name != "p" else container.parent
    print()
    print("Tag types inside the article container:")
    from collections import Counter
    tags_found = Counter(child.name for child in parent.find_all() if child.name)
    print(tags_found)
    print()
    print("=== RAW HTML of article container ===")
    print(str(parent)[:3000])