from src.wayback_helper import get_archived_urls
from src.utils import get, soupify

urls = get_archived_urls("english.www.gov.cn/premier/news/", from_date="2024-01-01")
print(f"Found {len(urls)} URLs total")
print("\nFirst 5 candidate URLs:")
for u in urls[:5]:
    print(" -", u)

print("\nChecking first candidate's actual title:")
if urls:
    resp = get(urls[0])
    if resp:
        soup = soupify(resp)
        title_tag = soup.find("title")
        print("Title:", title_tag.get_text(separator=" ") if title_tag else "(no title tag)")
    else:
        print("Fetch failed for this URL")