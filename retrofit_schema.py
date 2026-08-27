"""
Retrofits a scraped speech CSV to the new 15-field master schema.
Pilot version -- run on moldova.csv first to validate before applying
to other countries.

Usage:
    python retrofit_schema.py data/processed/moldova.csv
"""

import sys
import pandas as pd

LEADER_QID_MAP = {
    "Joe Biden": "Q6279",
    "Nataša Pirc Musar": "Q12797332",
    "Donald Trump": "Q22686",
    "Claudia Sheinbaum Pardo": "Q5771800",
    "Andrés Manuel López Obrador": "Q318508",
    "Maia Sandu": "Q15071069",
    "Justin Trudeau": "Q3099714",
    "Mark Carney": "Q192533",
    "Mia Mottley": "Q6827147",
    "Fiamē Naomi Mataʻafa": "Q5446290",
    "Nataša Pirc Musar": "Q12797332",
}


def opening_salutation(text: str, n_lines: int = 3) -> str:
    if not isinstance(text, str) or not text.strip():
        return ""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    return " / ".join(lines[:n_lines])


def retrofit(path: str):
    df = pd.read_csv(path)
    has_translation = "full_text_en" in df.columns

    out = pd.DataFrame()
    out["country"] = df["country"]
    out["leader"] = df["leader"]
    out["leader_qid"] = df["leader"].map(LEADER_QID_MAP)
    out["role"] = df["role"]
    out["date"] = df["date"]
    out["delivered_date"] = df["date"]  # best-effort default; see notes

    if has_translation:
        out["title"] = df["title_en"].fillna(df["title"])
        out["full_text"] = df["full_text_en"].fillna(df["full_text"])
        out["translated"] = "yes"
        out["original_title"] = df["title"]
        out["original_text"] = df["full_text"]
    else:
        out["title"] = df["title"]
        out["full_text"] = df["full_text"]
        out["translated"] = "no"
        out["original_title"] = ""
        out["original_text"] = ""

    out["language"] = "English"
    out["source_url"] = df["source_url"]
    out["delivered_venue"] = ""  # left blank -- see notes column for why

    # Pass through our own scraper's classification labels -- the schema
    # doc describes content_type as "the source scraper's own label,
    # retained as a record" -- so we keep sending it, not drop it.
    if "likely_speech" in df.columns:
        out["likely_speech"] = df["likely_speech"]
    if "content_type" in df.columns:
        out["content_type"] = df["content_type"]
    if "is_joint_multilateral" in df.columns:
        out["is_joint_multilateral"] = df["is_joint_multilateral"]

    salutations = df["full_text"].apply(opening_salutation)
    existing_notes = df["notes"].fillna("")
    out["notes"] = (
        existing_notes
        + " | Opening lines: " + salutations
        + " | delivered_date defaulted to date (no separate dateline tracked at scrape time)."
        + " | delivered_venue left blank (not extracted at scrape time)."
    )

    # Flag any missing QIDs instead of silently leaving them blank unexplained
    missing_qid = out["leader_qid"].isna()
    if missing_qid.any():
        print(f"WARNING: {missing_qid.sum()} row(s) have no leader_qid match for leader(s): "
              f"{df.loc[missing_qid, 'leader'].unique().tolist()}")

    # Word count check -- flag anything under ~300 words as a possible stub
    word_counts = out["full_text"].astype(str).str.split().str.len()
    stubs = word_counts < 300
    if stubs.any():
        print(f"WARNING: {stubs.sum()} row(s) under 300 words -- possible stub pages:")
        for i in out[stubs].index[:5]:
            print(f"  - {out.loc[i, 'title'][:60]} ({word_counts[i]} words)")

    out_path = path.replace(".csv", "_retrofit.csv")
    out.to_csv(out_path, index=False)
    print(f"\nSaved retrofitted file: {out_path} ({len(out)} rows)")


if __name__ == "__main__":
    retrofit(sys.argv[1])