"""
Adds an English translation column to an already-scraped speech CSV.

Usage:
    python translate_csv.py --input data/processed/denmark.csv --language da
    python translate_csv.py --input data/processed/samoa.csv --language sm

Adds a new column, full_text_en, to the CSV -- keeping the original
full_text column untouched, so both the source-language original and
the English translation are available side by side.
"""

import argparse
import time

import pandas as pd

from src.translate_helper import translate_to_english


def main():
    ap = argparse.ArgumentParser(description="Add English translations to a scraped speech CSV.")
    ap.add_argument("--input", required=True, help="Path to the CSV to translate.")
    ap.add_argument("--language", required=True,
                     help="Source language code, e.g. 'da' (Danish), 'sm' (Samoan), 'sl' (Slovenian), 'it' (Italian).")
    args = ap.parse_args()

    df = pd.read_csv(args.input)

    if "full_text_en" not in df.columns:
        df["full_text_en"] = ""
    if "title_en" not in df.columns:
        df["title_en"] = ""

    total = len(df)
    for i, row in df.iterrows():
        # Resumable: skip rows where BOTH translations already exist.
        text_done = isinstance(row.get("full_text_en", ""), str) and row.get("full_text_en", "").strip()
        title_done = isinstance(row.get("title_en", ""), str) and row.get("title_en", "").strip()
        if text_done and title_done:
            print(f"  [{i+1}/{total}] already translated, skipping: {row['title'][:50]}")
            continue

        print(f"  [{i+1}/{total}] translating: {row['title'][:50]}")

        if not title_done:
            translated_title = translate_to_english(str(row["title"]), args.language)
            df.at[i, "title_en"] = translated_title if translated_title is not None else ""

        if not text_done:
            translated = translate_to_english(str(row["full_text"]), args.language)
            df.at[i, "full_text_en"] = translated if translated is not None else ""

        # Save progress after every row -- if something crashes partway
        # through a long run, we don't lose everything already translated.
        df.to_csv(args.input, index=False)

    # Reorder columns so translations sit next to their original-language
    # counterpart, rather than tacked on at the far right.
    preferred_order = [
        "country", "leader", "role", "date",
        "title", "full_text",
        "title_en", "full_text_en",
        "language", "source_url", "likely_speech", "notes",
    ]
    existing_cols = [c for c in preferred_order if c in df.columns]
    remaining_cols = [c for c in df.columns if c not in existing_cols]
    df = df[existing_cols + remaining_cols]
    df.to_csv(args.input, index=False, encoding="utf-8-sig")

    print(f"\nDone. Translations added to {args.input}")


if __name__ == "__main__":
    main()