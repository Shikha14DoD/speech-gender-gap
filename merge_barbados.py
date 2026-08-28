import pandas as pd

main_df = pd.read_csv("data/processed/barbados.csv")
archive_df = pd.read_csv("data/processed/barbados_archive.csv")

print(f"barbados.csv: {len(main_df)} rows")
print(f"barbados_archive.csv: {len(archive_df)} rows")

main_df["_url_key"] = main_df["source_url"].str.rstrip("/")
archive_df["_url_key"] = archive_df["source_url"].str.rstrip("/")

overlap = set(main_df["_url_key"]) & set(archive_df["_url_key"])
print(f"URL overlap: {len(overlap)}")

merged = pd.concat([main_df, archive_df], ignore_index=True)
before = len(merged)
merged = merged.drop_duplicates(subset=["_url_key"], keep="first")
after = len(merged)
print(f"After URL dedup: {before} -> {after}")

before2 = after
merged = merged.drop_duplicates(subset=["date", "title", "full_text"], keep="first")
after2 = len(merged)
if before2 != after2:
    print(f"Additional exact-content duplicates removed: {before2 - after2}")

merged = merged.drop(columns=["_url_key"]).sort_values("date")
merged.to_csv("data/processed/barbados.csv", index=False)
print(f"\nSaved merged file: {len(merged)} rows to data/processed/barbados.csv")
print("(barbados_archive.csv is now redundant -- can be deleted)")