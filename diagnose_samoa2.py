import requests
from bs4 import BeautifulSoup

url = "https://mygov.gov.ws/prime-minister-fiame-today-hosted-tongas-prime-minister-and-his-delegation/"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
soup = BeautifulSoup(resp.text, "html.parser")

# Find where the known text actually lives
target_text = "Prime Minister for the Kingdom of Tonga"
found_in = []
for tag in soup.find_all(True):
    if tag.string and target_text in tag.string:
        found_in.append(tag)

print("Tags containing target text directly:", len(found_in))
for t in found_in[:3]:
    print(f" <{t.name}> class={t.get('class')} id={t.get('id')}")
    print(" parent:", t.parent.name, t.parent.get("class"))

# Broader: search get_text() containment, then narrow to smallest container
candidates = [tag for tag in soup.find_all(["div","section"]) if tag.get_text() and target_text in tag.get_text()]
candidates.sort(key=lambda t: len(t.get_text()))
if candidates:
    smallest = candidates[0]
    print()
    print("Smallest containing element:", smallest.name, smallest.get("class"), smallest.get("id"))
    print(str(smallest)[:600])