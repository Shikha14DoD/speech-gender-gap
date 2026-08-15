from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup

url = "https://www.gob.mx/amlo/archivo/articulos?order=DESC&page=1"
resp = curl_requests.get(url, impersonate="chrome", timeout=30)
print("Status code:", resp.status_code)
print("Response length:", len(resp.text))

soup = BeautifulSoup(resp.text, "html.parser")
print()
print("Total <article> tags:", len(soup.find_all("article")))
print("Total <time> tags:", len(soup.find_all("time")))
print("Total <a> tags with href:", len(soup.find_all("a", href=True)))

h1 = soup.find("h1")
print()
print("H1 text:", h1.get_text(strip=True) if h1 else "NOT FOUND")

print()
print("First 3 <article> blocks' raw <time> and <a> tags:")
for art in soup.find_all("article")[:3]:
    time_tag = art.find("time")
    a_tag = art.find("a", href=True)
    print(" time tag:", str(time_tag)[:200])
    print(" a tag href:", a_tag["href"] if a_tag else "NONE")
    print()