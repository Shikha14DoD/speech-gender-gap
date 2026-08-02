from src.utils import get, soupify

url = "http://english.scio.gov.cn/featured/xigovernance/2024-05/07/content_117170474.htm"

resp = get(url)
if resp is None:
    print("get() returned None -- the fetch itself failed (network/404/etc).")
else:
    print("Fetch succeeded, status:", resp.status_code)
    soup = soupify(resp)

    og_title = soup.find("meta", property="og:title")
    print("og:title tag found:", og_title)

    title_tag = soup.find("title")
    print("title tag found:", title_tag)

    date_meta = soup.find("meta", attrs={"name": "publishdate"})
    print("publishdate meta found:", date_meta)