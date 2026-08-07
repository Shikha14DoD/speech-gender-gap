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
    print("Found the heading. Next 5 sibling elements:")
    sibling = first_trump_h2
    count = 0
    while count < 5:
        sibling = sibling.find_next_sibling()
        if sibling is None:
            break
        print(f"  <{sibling.name}> : {sibling.get_text(strip=True)[:100]}")
        count += 1
else:
    print("Could not find a 'Donald Trump' heading at all")