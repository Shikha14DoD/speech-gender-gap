import re

url = "https://rollcall.com/factbase/trump/transcript/donald-trump-speech-80th-united-nations-general-assembly-september-23-2025/no/"

m = re.match(r"(https?://rollcall\.com/factbase/trump/transcript/[^/]+)", url)
if m:
    cleaned = m.group(1) + "/"
    print("Cleaned URL:", cleaned)
else:
    print("Regex did not match at all!")