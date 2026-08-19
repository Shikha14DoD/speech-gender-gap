"""
Merges canada_carney.csv (from CDX discovery, covers speeches/
statements/videos) with canada_carney_videos.csv (from live
pagination, covers videos specifically) into one deduped file,
since both may contain overlapping video-category articles.

Run from your project root:
    python merge_canada_carney.py
"""

import pandas as pd

main_df = pd.read_csv("data/processed/canada_carney.csv")
videos_df = pd.read_csv("data/processed/canada_carney_videos.csv")

print(f"canada_carney.csv: {len(main_df)} rows")
print(f"canada_carney_videos.csv: {len(videos_df)} rows")

# Normalize source_url (strip trailing slash) for reliable comparison
main_df["_url_key"] = main_df["source_url"].str.rstrip("/")
videos_df["_url_key"] = videos_df["source_url"].str.rstrip("/")

overlap = set(main_df["_url_key"]) & set(videos_df["_url_key"])
print(f"URL overlap between the two files: {len(overlap)}")

merged = pd.concat([main_df, videos_df], ignore_index=True)
before = len(merged)
merged = merged.drop_duplicates(subset=["_url_key"], keep="first")
after = len(merged)
print(f"After merging and deduping by URL: {before} -> {after}")

# Also catch any same-content-different-URL duplicates
before2 = after
merged = merged.drop_duplicates(subset=["date", "title", "full_text"], keep="first")
after2 = len(merged)
if before2 != after2:
    print(f"Additional exact-content duplicates removed: {before2 - after2}")

merged = merged.drop(columns=["_url_key"])
merged.to_csv("data/processed/canada_carney.csv", index=False)
print(f"\nSaved merged file: {len(merged)} rows to data/processed/canada_carney.csv")
print("(canada_carney_videos.csv is now redundant -- can be deleted)")