"""
One-off: computes content_type for Denmark's existing rows, since that
classifier was added after Denmark was originally scraped.
"""

import pandas as pd

from src.text_processing import classify_content_type

df = pd.read_csv("data/processed/denmark.csv")
df["content_type"] = df["title_en"].apply(classify_content_type)

df.to_csv("data/processed/denmark.csv", index=False, encoding="utf-8-sig")
print("Done. content_type distribution:")
print(df["content_type"].value_counts())