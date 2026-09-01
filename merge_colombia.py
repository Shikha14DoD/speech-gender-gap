"""
Merge the two Colombia (Gustavo Petro) sources into one dataset:

  1. data/processed/colombia_pdf.csv  -- official 'Discursos del
     presidente' PDF volumes (Vol 4-26). Full text, ~2024-06..2026-06.
     PRIMARY.
  2. data/processed/colombia.csv      -- Internet Archive Wayback route.
     Thinner, but covers dates the PDF volumes miss (a 2023 speech,
     parts of 2024, some 2025 gaps).

A speech in both is kept once, from the PDF source (cleaner, fuller
text). Wayback rows that don't match any PDF row are added.

Usage:  python merge_colombia.py
Output: data/processed/colombia_merged.csv
"""

import re
import unicodedata
import pandas as pd

PDF = "data/processed/colombia_pdf.csv"
WB = "data/processed/colombia.csv"
OUT = "data/processed/colombia_merged.csv"

_STRIP = re.compile(
    r"(apartes de las )?(palabras|alocuci[oó]n|intervenci[oó]n|declaraci[oó]n|"
    r"discurso|mensaje|saludo|instalaci[oó]n)(es)?\s+(iniciales\s+)?"
    r"del?\s+(se[nñ]or\s+)?president[ea]\s+(de\s+la\s+rep[uú]blica\s+)?"
    r"(gustavo\s+)?(petro\s+)?(urrego\s+)?", re.I)


def norm(title: str) -> str:
    t = unicodedata.normalize("NFKD", str(title)).encode("ascii", "ignore").decode()
    t = t.lower()
    t = _STRIP.sub("", t)
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def tokens(title: str) -> set:
    return {w for w in norm(title).split() if len(w) > 3}


def main():
    pdf = pd.read_csv(PDF, dtype=str, keep_default_na=False)
    wb = pd.read_csv(WB, dtype=str, keep_default_na=False)
    print(f"PDF volumes: {len(pdf)} rows   Wayback: {len(wb)} rows")

    pdf_index = {}
    for _, r in pdf.iterrows():
        pdf_index.setdefault(r["date"], []).append(tokens(r["title"]))

    def is_dup(row):
        cands = pdf_index.get(row["date"], [])
        if not cands:
            return False
        rt = tokens(row["title"])
        if not rt:
            return False
        for ct in cands:
            if not ct:
                continue
            jac = len(rt & ct) / len(rt | ct)
            if jac >= 0.4 or rt <= ct or ct <= rt:
                return True
        return False

    wb["_dup"] = wb.apply(is_dup, axis=1)
    wb_keep = wb[~wb["_dup"]].drop(columns=["_dup"])
    wb_drop = int(wb["_dup"].sum())

    merged = pd.concat([pdf, wb_keep], ignore_index=True, sort=False)
    merged = merged.sort_values(["date", "title"]).reset_index(drop=True)
    merged.to_csv(OUT, index=False, encoding="utf-8")

    print(f"\nWayback rows matching a PDF speech (dropped): {wb_drop}")
    print(f"Wayback rows added (unique):                  {len(wb_keep)}")
    print(f"Merged total:                                 {len(merged)}")
    print(f"  date range: {merged['date'].min()} -> {merged['date'].max()}")
    ym = merged["date"].str[:7].value_counts().sort_index()
    print(ym.to_string())
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
