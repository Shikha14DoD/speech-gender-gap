"""
Validates data/processed/trump.csv against the Senate Democrats
Trump Transcripts archive, page 1 (most recent 20 entries as of 2026-08-06).

Run from your project root:
    python validate_trump.py
"""

import pandas as pd

# Reference list: (date, title keyword) from page 1 of
# https://www.democrats.senate.gov/newsroom/trump-transcripts
REFERENCE = [
    ("2026-07-13", "Freedom 250 Grand Prix"),
    ("2026-07-13", "Hugh Hewitt"),
    ("2026-07-12", "Jake Tapper"),
    ("2026-07-12", "Kristen Welker"),
    ("2026-07-08", "Air Force One"),
    ("2026-07-08", "NATO Summit in Ankara"),
    ("2026-07-08", "Volodymyr Zelenskyy"),
    ("2026-07-08", "Ahmed al-Sharaa"),
    ("2026-07-08", "Mark Rutte"),
    ("2026-07-07", "Recep Tayyip Erdogan"),
    ("2026-07-06", "Trump Account Launch"),
    ("2026-07-06", "Rose Garden Lunch"),
    ("2026-07-04", "250th Birthday"),
    ("2026-07-03", "Mount Rushmore"),
    ("2026-07-03", "Usha Vance"),
    ("2026-07-02", "Joe Kernen"),
    ("2026-07-01", "Presidential Library Tour"),
    ("2026-07-01", "Teddy Roosevelt Presidential Library"),
    ("2026-07-01", "Air Force One Departure"),
    ("2026-07-01", "Teddy Roosevelt Library"),
]

df = pd.read_csv("data/processed/trump.csv")
df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

# Filter to the same window
window = df[(df["date"] >= "2026-07-01") & (df["date"] <= "2026-07-13")]

print(f"Rows in your CSV for 2026-07-01 to 2026-07-13: {len(window)}")
print(f"Rows expected from source page 1: {len(REFERENCE)}\n")

# Find title column (guess common names)
title_col = None
for candidate in ["title", "speech_title", "headline"]:
    if candidate in df.columns:
        title_col = candidate
        break

if title_col is None:
    print("Could not find a title column — checked: title, speech_title, headline")
    print("Your columns are:", list(df.columns))
else:
    missing = []
    for date, keyword in REFERENCE:
        match = window[
            (window["date"] == date)
            & (window[title_col].str.contains(keyword, case=False, na=False))
        ]
        if match.empty:
            missing.append((date, keyword))

    if missing:
        print(f"MISSING ({len(missing)}) — in source but not found in your CSV:")
        for date, keyword in missing:
            print(f"  {date} - {keyword}")
    else:
        print("All reference entries found. No gaps detected for this window.")

    extra_count = len(window) - (len(REFERENCE) - len(missing))
    if extra_count > 0:
        print(f"\nNote: your CSV has {extra_count} more row(s) in this window than "
              f"the reference list — likely fine (page 1 sometimes shows fewer "
              f"than what's indexed, or duplicates/near-duplicates exist).")