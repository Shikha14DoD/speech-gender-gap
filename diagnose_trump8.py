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
    # Walk up several levels, printing each ancestor's tag/class and text length
    node = first_trump_h2
    for level in range(6):
        node = node.find_parent()
        if node is None:
            break
        text = node.get_text(separator=" ", strip=True)
        print(f"Level {level+1}: <{node.name}> class={node.get('class')} -- text length: {len(text)}")
        print(f"  Preview: {text[:150]}")
        print()