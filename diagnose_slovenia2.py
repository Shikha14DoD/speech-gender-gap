import requests
from bs4 import BeautifulSoup

resp = requests.get("https://www.predsednica-slo.si/sl/objave/govori",
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
soup = BeautifulSoup(resp.text, "html.parser")

exclude_paths = {
    "/sl/objave", "/sl/objave/vse", "/sl/objave/govori",
    "/sl/objave/aktivnosti-v-sloveniji", "/sl/objave/mednarodne-aktivnosti",
    "/sl/objave/poslanice", "/sl/objave/moc-dejstev", "/sl/objave/rss",
}

links = []
for a in soup.find_all("a", href=True):
    href = a["href"]
    if "#" in href or "/sl/objave/" not in href:
        continue
    path_only = href.split("?")[0].rstrip("/").replace("https://www.predsednica-slo.si", "")
    if path_only in exclude_paths:
        continue
    links.append(a)

print("LINKS FOUND:", len(links))
print("FIRST HREF:", links[0]["href"])

article_url = "https://www.predsednica-slo.si" + links[0]["href"]
article_resp = requests.get(article_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
article_soup = BeautifulSoup(article_resp.text, "html.parser")

h1 = article_soup.find("h1")
print("ARTICLE H1:", h1.get_text(strip=True) if h1 else "NOT FOUND")

time_tag = article_soup.find("time", attrs={"datetime": True})
print("ARTICLE TIME TAG:", time_tag)

best_div, best_count = None, 0
for div in article_soup.find_all("div"):
    count = len(div.find_all("p", recursive=False))
    if count > best_count:
        best_count = count
        best_div = div
print("BEST CONTENT DIV CLASS:", best_div.get("class") if best_div is not None else None)
print("BEST DIV P COUNT:", best_count)