import requests
from bs4 import BeautifulSoup

resp = requests.get("https://www.predsednica-slo.si/sl/objave/govori",
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
print("Status:", resp.status_code)
soup = BeautifulSoup(resp.text, "html.parser")

exclude_paths = {
    "/sl/objave", "/sl/objave/vse", "/sl/objave/govori",
    "/sl/objave/aktivnosti-v-sloveniji", "/sl/objave/mednarodne-aktivnosti",
    "/sl/objave/poslanice", "/sl/objave/moc-dejstev", "/sl/objave/rss",
}

links = []
for a in soup.find_all("a", href=True):
    href = a["href"]
    if "#" in href:
        continue
    if "/sl/objave/" not in href:
        continue
    path_only = href.split("?")[0].rstrip("/")
    # normalize to path-only (strip domain if present)
    path_only = path_only.replace("https://www.predsednica-slo.si", "")
    if path_only in exclude_paths:
        continue
    links.append(a)

print("Article links found:", len(links))
if links:
    first = links[0]
    print()
    print("First link href:", first["href"])
    print()
    print("First link's surrounding HTML:")
    print(str(first.parent.parent)[:1200])