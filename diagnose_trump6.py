from src.utils import get, soupify

url = "https://rollcall.com/factbase/trump/transcript/donald-trump-speech-80th-united-nations-general-assembly-september-23-2025/"

resp = get(url)
soup = soupify(resp)

h2_tags = soup.find_all("h2")
first_trump_h2 = None
for h2 in h2_tags:
    if h2.get_text(strip=True) == "Donald Trump":
        first_trump_h2 = h2
        break

if first_trump_h2:
    parent = first_trump_h2.find_parent()
    print("Parent tag:", parent.name, "class:", parent.get("class"))
    print()
    print("Parent's full text (first 500 chars):")
    print(parent.get_text(separator=" | ", strip=True)[:500])