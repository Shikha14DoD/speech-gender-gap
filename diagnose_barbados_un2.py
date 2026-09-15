from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup

url = "https://pmo.gov.bb/2024/09/26/high-level-meeting-on-antimicrobial-resistance/"
resp = curl_requests.get(url, impersonate="chrome", timeout=30)
print("Status:", resp.status_code)
print("Total 'Mottley' occurrences:", resp.text.count("Mottley"))

soup = BeautifulSoup(resp.text, "html.parser")
for tag in soup.find_all(["p", "h1","h2","h3","h4","strong","em","div"]):
    text = tag.get_text(strip=True)
    if "Mottley" in text and len(text) < 200:
        print(f"<{tag.name}> class={tag.get('class')}:", repr(text))