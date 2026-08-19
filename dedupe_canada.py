"""
Removes confirmed exact duplicate rows (same date + title + identical
full_text) from the given CSV, keeping the first occurrence.

Run from your project root:
    python dedupe_canada.py data/processed/canada_carney.csv
    python dedupe_canada.py data/processed/canada_trudeau.csv
"""

import sys
import pandas as pd

path = sys.argv[1]
df = pd.read_csv(path)

before = len(df)
df_deduped = df.drop_duplicates(subset=["date", "title", "full_text"], keep="first")
after = len(df_deduped)

print(f"{path}")
print(f"  Rows before: {before}")
print(f"  Duplicates removed: {before - after}")
print(f"  Rows after: {after}")

df_deduped.to_csv(path, index=False)