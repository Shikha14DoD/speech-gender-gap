from src.config_loader import load_config, get_leader_config
from src.scraper_trump import _fetch_article

config = load_config()
leader_config = get_leader_config("trump", config)

url = "https://rollcall.com/factbase/trump/transcript/donald-trump-speech-80th-united-nations-general-assembly-september-23-2025/"

article = _fetch_article(url, leader_config)
if article is None:
    print("FAILED: _fetch_article returned None")
else:
    print("SUCCESS")
    print("Title:", article.title)
    print("Date:", article.date)
    print("Text length:", len(article.full_text))
    print("First 200 chars:", article.full_text[:200])