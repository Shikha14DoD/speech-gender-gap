"""
Removes rows dated 2026-07-01 through 2026-07-13 from trump.csv,
so the re-scrape of that window can drop in clean (no duplicates).

A backup should already exist at data/processed/trump_backup.csv
before running this.

Run from your project root:
    python remove_window_trump.py
"""

import pandas as pd

path = "data/processed/trump.csv"
df = pd.read_csv(path)

# Keep original date column untouched on disk; use a temp parsed column for filtering
df["_date_parsed"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

before = len(df)
mask = (df["_date_parsed"] >= "2026-07-01") & (df["_date_parsed"] <= "2026-07-13")
removed = df[mask]
df = df[~mask].drop(columns=["_date_parsed"])

print(f"Rows before: {before}")
print(f"Rows removed (2026-07-01 to 2026-07-13): {len(removed)}")
print(f"Rows remaining: {len(df)}")

df.to_csv(path, index=False)
print(f"\nSaved cleaned file to {path}")
print("Now re-run the scraper for that date range to fill it back in.")