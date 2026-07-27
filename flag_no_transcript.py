"""
One-off: flags existing rows in italy.csv whose full_text is just a
caption noting a video message exists, with no actual transcript
(Italian-only video, no English text version available).
"""

import pandas as pd

df = pd.read_csv("data/processed/italy.csv")

def has_no_transcript(text):
    t = str(text).lower()
    return "available in italian only" in t or ("available in" in t and "only" in t)

mask = df["full_text"].apply(has_no_transcript)
print("Rows with no real transcript (video-only, Italian-only):", mask.sum())

warning = (
    " [WARNING] NO ENGLISH TRANSCRIPT: this row's full_text is likely just a "
    "brief description that a video message occurred, not the actual "
    "spoken content -- the real video is Italian-only with no text "
    "version available on the page."
)

df.loc[mask, "notes"] = df.loc[mask, "notes"].astype(str) + warning
df.to_csv("data/processed/italy.csv", index=False, encoding="utf-8-sig")
print("Done. Notes updated in place.")