"""
Term-anchor translation spot-check.

For a given _FINAL.csv, checks whether high-salience source-language terms
(gender/equality vocabulary by default) that appear in `original_text`
actually survive into the English `full_text`. A row where the source
mentions the term N>=1 times but the translation has zero is a candidate
silent term-dropout -- the exact failure mode found in Tanzania (Swahili
"wanawake" present, English "women" absent in 3/24 checked rows).

This only works on rows where original_text is populated (has_source=True
in the printed report) -- everything else is unauditable and should be
treated as such, not assumed fine. See MEMORY.md / project notes on MT
reliability tiers: Spanish/French/Portuguese/Arabic/Chinese are high-to-mid
resource (spot-sample); Swahili/Sinhala and similar are low-resource
(audit every row).

Usage:
    python check_translation_terms.py data/processed/tanzania_FINAL.csv
    python check_translation_terms.py data/processed/brazil_FINAL.csv --terms mulher,mulheres,igualdade

Default term pairs cover a handful of languages seen in this project so
far; pass --terms for a language not in the built-in table, as a comma
list of the SOURCE-language word(s) to look for (English side is always
matched against the fixed ANCHOR_EN list below).
"""
import argparse
import re
import sys

import pandas as pd

# source-language term(s) -> what we expect on the English side if it
# survived translation (checked as a whole-word regex, case-insensitive)
ANCHOR_EN = re.compile(r"\bwomen\b|\bgirls?\b|\bgender\b", re.I)

BUILTIN_SOURCE_TERMS = {
    "swahili": [r"\bwanawake\b", r"\bwasichana\b", r"\bkijinsia\b"],
    "sinhala": [r"[ගැහෙ෋ු]"],  # placeholder -- Sinhala needs a real term list
    "portuguese": [r"\bmulher(es)?\b", r"\bmenina(s)?\b", r"\bg[êe]nero\b"],
    "spanish": [r"\bmujer(es)?\b", r"\bni[ñn]a(s)?\b", r"\bg[ée]nero\b"],
    "french": [r"\bfemmes?\b", r"\bfilles?\b", r"\bgenre\b"],
    "arabic": [r"المرأة", r"المساواة"],  # al-mar'a, al-musawah
}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="path to a *_FINAL.csv")
    ap.add_argument("--language", help="key into BUILTIN_SOURCE_TERMS, "
                    "e.g. swahili, portuguese (default: guess from the "
                    "file's `language` column)")
    ap.add_argument("--terms", help="comma-separated regex terms to use "
                    "instead of the built-in table")
    args = ap.parse_args()

    d = pd.read_csv(args.csv, dtype=str, keep_default_na=False)
    has_orig = d["original_text"].str.len() > 0
    print(f"{args.csv}: {len(d)} rows, {int(has_orig.sum())} with original_text "
          f"({int(has_orig.sum()) / max(1, len(d)):.0%}) -- only these are checkable")

    if args.terms:
        terms = [t.strip() for t in args.terms.split(",")]
    else:
        lang_key = args.language or (
            d.loc[has_orig, "language"].mode().iloc[0].lower()
            if has_orig.any() else "")
        terms = BUILTIN_SOURCE_TERMS.get(lang_key)
        if not terms:
            print(f"No built-in term list for '{lang_key}' -- pass --terms or --language.",
                  file=sys.stderr)
            sys.exit(1)
        print(f"Using built-in terms for '{lang_key}': {terms}")

    source_pat = re.compile("|".join(terms), re.I)
    checkable = d[has_orig].copy()
    checkable["src_hits"] = checkable["original_text"].apply(
        lambda t: len(source_pat.findall(t)))
    checkable = checkable[checkable["src_hits"] > 0]
    if checkable.empty:
        print("No rows with original_text mention the anchor term(s) -- nothing to check.")
        return

    checkable["en_hits"] = checkable["full_text"].apply(
        lambda t: len(ANCHOR_EN.findall(t)))
    dropout = checkable[checkable["en_hits"] == 0]

    print(f"\n{len(checkable)} rows mention the term in the source; "
          f"{len(dropout)} have ZERO matches in the English translation "
          f"({len(dropout) / len(checkable):.0%} term-survival failure rate)")
    if len(dropout):
        print("\nFlagged rows (source hits -> English hits):")
        for _, r in dropout.iterrows():
            print(f"  {r.get('date', '')} | src x{r['src_hits']} -> en x{r['en_hits']} "
                  f"| {r['title'][:70]}")


if __name__ == "__main__":
    main()
