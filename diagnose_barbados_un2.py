import requests
from bs4 import BeautifulSoup

url = "https://pmo.gov.bb/2024/09/26/high-level-meeting-on-antimicrobial-resistance/"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
soup = BeautifulSoup(resp.text, "html.parser")

print("Total 'Mottley' occurrences in raw HTML text:", resp.text.count("Mottley"))

# Find the smallest tag containing "Mottley" anywhere
for tag in soup.find_all(True):
    if tag.string and "Mottley" in tag.string:
        print(f"Direct string match in <{tag.name}>:", repr(tag.string[:100]))

# Broader: any tag whose OWN text (not children) contains it
import re
for tag in soup.find_all(True):
    own_text = tag.find(string=re.compile("Mottley"))
    if own_text:
        print(f"<{tag.name}> class={tag.get('class')}: contains 'Mottley' text node: {repr(str(own_text)[:100])}")
        break