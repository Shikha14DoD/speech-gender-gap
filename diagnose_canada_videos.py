import requests
from bs4 import BeautifulSoup

resp = requests.get("https://www.pm.gc.ca/en/videos?page=0",
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
print("Status:", resp.status_code)
soup = BeautifulSoup(resp.text, "html.parser")

links = [a for a in soup.find_all("a", href=True) if "/en/videos/" in a["href"]
         and a["href"].rstrip("/") != "https://www.pm.gc.ca/en/videos"]
print("Video links found:", len(links))

if links:
    first = links[0]
    print()
    print("First link's surrounding HTML:")
    print(str(first.parent)[:800])