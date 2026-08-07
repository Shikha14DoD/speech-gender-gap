from src.wayback_helper import get_archived_urls
import re

urls = get_archived_urls("rollcall.com/factbase/trump/transcript/", from_date="2025-01-20")

cleaned = set()
for u in urls:
    m = re.match(r"(https?://rollcall\.com/factbase/trump/transcript/[^/]+)", u)
    if m:
        cleaned.add(m.group(1) + "/")

target = "https://rollcall.com/factbase/trump/transcript/donald-trump-speech-80th-united-nations-general-assembly-september-23-2025/"
print("Total candidates:", len(cleaned))
print("Target URL found:", target in cleaned)

# Show a few real September 2025 entries if any exist
sept_2025 = [u for u in cleaned if "september-2025" in u or "september-23-2025" in u]
print("September 2025 entries found:", len(sept_2025))
for u in sept_2025[:5]:
    print(" -", u)