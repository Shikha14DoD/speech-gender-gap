from src.utils import get, soupify

url = "https://english.www.gov.cn/news/202503/12/content_WS67d17f57c6d0868f4e8f0c0d.html"

resp = get(url)
if resp is None:
    print("get() returned None -- fetch failed.")
else:
    print("Fetch succeeded, status:", resp.status_code)
    soup = soupify(resp)

    og_title = soup.find("meta", property="og:title")
    print("og:title found:", og_title)

    title_tag = soup.find("title")
    print("title tag found:", title_tag)
    if title_tag:
        print("title text:", title_tag.get_text(separator=" "))