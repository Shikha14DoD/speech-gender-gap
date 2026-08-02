"""
One-off verification: compares our scraped China CSV against a list of
(date, title) pairs manually collected by browsing english.scio.gov.cn's
own "Speeches" listing pages directly.

Matching is done by DATE, not exact title text -- the listing page's
teaser title sometimes differs slightly in wording from the real
article's title (e.g. "Xi's speech..." vs "Chinese President Xi
Jinping's speech..."), so exact string matching would produce false
mismatches. For dates with more than one entry, we compare COUNTS per
date rather than trying to pair up which specific entry is which.
"""

import pandas as pd
from collections import Counter

# (date, short_title_snippet) collected from the site's own listing
# pages, spanning May 2024 - July 2026.
reference_entries = [
    ("2026-07-18", "World AI Conference"),
    ("2026-01-01", "2026 New Year message"),
    ("2025-11-01", "Session II of the 32nd APEC"),
    ("2025-11-01", "written speech at APEC CEO Summit"),
    ("2025-10-31", "Session I of the 32nd APEC"),
    ("2025-10-29", "15th Five-Year Plan"),
    ("2025-10-14", "Global Leaders' Meeting on Women"),
    ("2025-09-25", "UN Climate Summit"),
    ("2025-09-09", "virtual BRICS Summit"),
    ("2025-09-02", "25th Meeting of Council of Heads of State of SCO"),
    ("2025-09-02", "Shanghai Cooperation Organization Plus"),
    ("2025-09-01", "welcoming banquet of SCO Tianjin Summit"),
    ("2025-07-03", "All-China Youth Federation"),
    ("2025-06-18", "second China-Central Asia Summit"),
    ("2025-05-14", "China-CELAC Forum"),
    ("2025-05-07", "signed article in Russian media"),
    ("2025-04-17", "signed article in Cambodian media"),
    ("2025-04-16", "signed article in Malaysian media"),
    ("2025-04-14", "signed article in Vietnamese newspaper"),
    ("2025-02-08", "9th Asian Winter Games"),
    ("2025-01-01", "2025 New Year message"),
    ("2024-12-21", "25th anniv of Macao's return"),
    ("2024-12-20", "welcoming dinner hosted by Macao SAR"),
    ("2024-11-19", "Session II of 19th G20 Summit"),
    ("2024-11-19", "Session I of 19th G20 Summit"),
    ("2024-11-17", "31st APEC Economic Leaders' Meeting"),
    ("2024-11-17", "written speech at APEC CEO Summit"),
    ("2024-11-15", "signed article in Peruvian media"),
    ("2024-10-25", "BRICS Plus leaders' dialogue"),
    ("2024-10-24", "16th BRICS Summit"),
    ("2024-09-05", "2024 FOCAC summit keynote"),
    ("2024-09-05", "2024 FOCAC summit toast"),
    ("2024-07-05", "signed article on Tajik media"),
    ("2024-07-05", "Shanghai Cooperation Organization Plus Meeting in Astana"),
    ("2024-07-02", "signed article in Kazakh media"),
    ("2024-06-28", "70th anniv. of Five Principles of Peaceful Coexistence"),
    ("2024-05-08", "signed article in Serbian media"),
    ("2024-05-07", "China-France Business Council"),
]

print(f"Reference list: {len(reference_entries)} entries (manually collected)")

ref_date_counts = Counter(d for d, _ in reference_entries)

df = pd.read_csv("data/processed/china.csv")
scraped_date_counts = Counter(df["date"])

print(f"Our CSV: {len(df)} rows\n")

print("=== Comparing counts per date ===")
all_dates = sorted(set(ref_date_counts) | set(scraped_date_counts))
mismatches = 0
for d in all_dates:
    ref_n = ref_date_counts.get(d, 0)
    scraped_n = scraped_date_counts.get(d, 0)
    if ref_n != scraped_n:
        mismatches += 1
        print(f"  {d}: reference has {ref_n}, our CSV has {scraped_n}  <-- MISMATCH")

if mismatches == 0:
    print("  No mismatches -- every date has the same count in both lists.")
else:
    print(f"\n{mismatches} date(s) with mismatched counts -- see above.")