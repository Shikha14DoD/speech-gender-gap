"""
Recovers the pre-2025-05-24 rows (early 2025, whitehouse.gov-sourced,
now a dead link) from the backup taken before the full re-scrape,
and appends them into the current trump.csv.

Run from your project root:
    python recover_early2025.py
"""

import pandas as pd

backup_path = "data/processed/trump_backup_before_full_rescrape.csv"
current_path = "data/processed/trump.csv"

backup = pd.read_csv(backup_path)
current = pd.read_csv(current_path)

backup["_date_parsed"] = pd.to_datetime(backup["date"]).dt.strftime("%Y-%m-%d")
early = backup[backup["_date_parsed"] < "2025-05-24"].drop(columns=["_date_parsed"])

print(f"Early-2025 rows found in backup: {len(early)}")
print(f"Date range of recovered rows: {early['date'].min()} to {early['date'].max()}")
print(f"Current trump.csv rows before merge: {len(current)}")

merged = pd.concat([early, current], ignore_index=True)

# Safety check: flag any exact duplicate rows (by date + title) before saving
dupes = merged.duplicated(subset=["date", "title"], keep=False)
if dupes.any():
    print(f"\nWARNING: {dupes.sum()} potential duplicate rows found (same date+title).")
    print("Review before trusting the merge. Duplicates NOT auto-removed.")
else:
    print("\nNo duplicate date+title rows detected.")

merged.to_csv(current_path, index=False)
print(f"\nMerged file saved. Total rows now: {len(merged)}")