"""
Validates data/processed/trump.csv against the Senate Democrats
Trump Transcripts archive, page 2 (2026-06-17 to 2026-06-29).

Run from your project root:
    python validate_trump_window2.py
"""

import pandas as pd

REFERENCE = [
    ("2026-06-29", "Automobile Repairs"),
    ("2026-06-26", "Religious Liberty Commission"),
    ("2026-06-26", "Faith and Freedom Coalition"),
    ("2026-06-25", "Julia Letlow"),
    ("2026-06-25", "Rose Garden Dinner"),
    ("2026-06-24", "Great American State Fair"),
    ("2026-06-24", "Mark Rutte"),
    ("2026-06-24", "Departing the Capitol"),
    ("2026-06-24", "Arriving at the Capitol"),
    ("2026-06-23", "Mack Trucks"),
    ("2026-06-23", "Air Force One Arrival"),
    ("2026-06-22", "Quantum Technology"),
    ("2026-06-19", "Daniele Compatangelo"),
    ("2026-06-19", "Servicemembers After New Air Force One"),
    ("2026-06-18", "Marc Caputo"),  # NOTE: appears twice on source itself, see below
    ("2026-06-18", "Medal of Honor"),
    ("2026-06-17", "Air Force One Arrival"),
    ("2026-06-17", "G7 Summit"),
    ("2026-06-17", "Versailles Departure"),
]

df = pd.read_csv("data/processed/trump.csv")
df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

window = df[(df["date"] >= "2026-06-17") & (df["date"] <= "2026-06-29")]

print(f"Rows in your CSV for 2026-06-17 to 2026-06-29: {len(window)}")
print(f"Unique reference titles expected: {len(REFERENCE)} "
      f"(source lists 20 total, but Marc Caputo 6.18 appears twice on the "
      f"source page itself due to a URL glitch, so {len(REFERENCE)} unique)\n")

title_col = None
for candidate in ["title", "speech_title", "headline"]:
    if candidate in df.columns:
        title_col = candidate
        break

missing = []
for date, keyword in REFERENCE:
    match = window[
        (window["date"] == date)
        & (window[title_col].str.contains(keyword, case=False, na=False))
    ]
    if match.empty:
        missing.append((date, keyword))

if missing:
    print(f"MISSING ({len(missing)}):")
    for date, keyword in missing:
        print(f"  {date} - {keyword}")
else:
    print("All reference entries found. No gaps detected for this window.")