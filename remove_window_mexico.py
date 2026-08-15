"""
Removes rows dated 2026-07-09 through 2026-07-27 from mexico.csv,
since this window was already manually uploaded separately by
Ginette's team and doesn't need to be duplicated here.

Run from your project root:
    python remove_window_mexico.py
"""

import pandas as pd

path = "data/processed/mexico.csv"
df = pd.read_csv(path)

before = len(df)
mask = (df["date"] >= "2026-07-09") & (df["date"] <= "2026-07-27")
removed = df[mask]
df = df[~mask]

print(f"Rows before: {before}")
print(f"Rows removed (2026-07-09 to 2026-07-27): {len(removed)}")
print(f"Rows remaining: {len(df)}")

df.to_csv(path, index=False)
print(f"\nSaved cleaned file to {path}")