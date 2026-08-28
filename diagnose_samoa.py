import requests
from bs4 import BeautifulSoup

url = "https://mygov.gov.ws/prime-minister-fiame-today-hosted-tongas-prime-minister-and-his-delegation/"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
print("Status:", resp.status_code)
soup = BeautifulSoup(resp.text, "html.parser")

print("Has <article>:", soup.find("article") is not None)
print("Has <main>:", soup.find("main") is not None)
print("Total <p> tags on page:", len(soup.find_all("p")))

# Print any <p> tags found, to see if they exist but get excluded somehow
for i, p in enumerate(soup.find_all("p")[:8]):
    print(f" p[{i}] class={p.get('class')}:", repr(p.get_text(strip=True)[:80]))