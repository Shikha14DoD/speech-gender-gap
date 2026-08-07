from src.utils import get, soupify, clean_text

url = "https://rollcall.com/factbase/trump/transcript/donald-trump-speech-80th-united-nations-general-assembly-september-23-2025/"

resp = get(url)
soup = soupify(resp)

title_tag = soup.find("h1")
print("Title:", title_tag.get_text(separator=" ") if title_tag else "NOT FOUND")
print()

h2_tags = soup.find_all("h2")
print(f"Found {len(h2_tags)} h2 tags. First 10:")
for h2 in h2_tags[:10]:
    print("  -", repr(h2.get_text(strip=True)))