"""
Removes confirmed exact duplicate rows (same date + title + identical
full_text) from trump.csv, keeping the first occurrence of each.

Run from your project root:
    python dedupe_trump.py
"""

import pandas as pd

path = "data/processed/trump.csv"
df = pd.read_csv(path)

before = len(df)
df_deduped = df.drop_duplicates(subset=["date", "title", "full_text"], keep="first")
after = len(df_deduped)

print(f"Rows before: {before}")
print(f"Duplicates removed: {before - after}")
print(f"Rows after: {after}")

df_deduped.to_csv(path, index=False)
print(f"\nSaved deduplicated file to {path}")