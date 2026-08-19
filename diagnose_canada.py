import requests
from bs4 import BeautifulSoup

url = "https://www.pm.gc.ca/en/news/speeches/2026/07/29/prime-minister-carney-announces-new-infrastructure-agreement-alberta"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
soup = BeautifulSoup(resp.text, "html.parser")

print("Status:", resp.status_code)

# Find date meta tag
for meta in soup.find_all("meta"):
    name = meta.get("name", "")
    if "date" in name.lower() or "issued" in name.lower():
        print("Date meta tag:", meta.get("name"), "=", meta.get("content"))

h1 = soup.find("h1")
print()
print("H1:", h1.get_text(strip=True) if h1 else "NOT FOUND")
print("H1 parent chain:", [p.name for p in h1.parents][:5] if h1 else None)

# Find likely content container by looking for a div with many <p> children
print()
print("Divs with 10+ direct/nested <p> children:")
for div in soup.find_all("div"):
    p_count = len(div.find_all("p", recursive=True))
    if p_count >= 15:
        print(f" <div class={div.get('class')} id={div.get('id')}> -- {p_count} <p> tags")

ps = soup.find_all("p")
print()
print(f"Total <p> tags: {len(ps)}")
for p in ps[5:10]:
    print(" -", repr(p.get_text(strip=True)[:80]), "| parent:", p.parent.name, p.parent.get("class"), p.parent.get("id"))