"""
Finalize a scraped + translated speech CSV into the central hand-off
schema and print the hand-off validation report.

This implements the manager's spec (2026-09-01):
  - exactly 15 columns, fixed order (below)
  - NO likely_speech / content_type / audience columns (central team
    classifies centrally)
  - original-language text always kept (original_title / original_text)
  - date vs delivered_date tracked separately
  - notes carries the opening salutation (first 2-3 lines, copied
    exactly) + any provenance footnote, plus prose flags for
    interview / press-conference / multi-speaker-extract / excerpt
  - written with csv.QUOTE_ALL, UTF-8, no Excel round-trip
  - URL dedup: lowercase, drop www., drop trailing slash, strip only
    utm_* / fbclid / gclid; keep every other param
  - mojibake repaired with ftfy, never find-and-replace

Usage:
    python finalize_dataset.py --input data/processed/chile.csv \
        --language Spanish --leader-qid Q16297876 \
        --out data/processed/chile_final.csv
"""

import argparse
import csv
import re
import sys
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import ftfy
import pandas as pd

SCHEMA = [
    "country", "leader", "leader_qid", "role", "date", "delivered_date",
    "title", "full_text", "original_title", "original_text", "language",
    "translated", "source_url", "delivered_venue", "notes",
]

TRACKING_PARAMS = {"fbclid", "gclid", "gclsrc", "dclid", "msclkid", "mc_cid", "mc_eid", "yclid"}

# used when --leader-qid auto (a dataset with more than one leader)
LEADER_QID = {
    "Gabriel Boric Font": "Q16297876",
    "Gustavo Petro": "Q704022",
    "Jacinda Ardern": "Q3606816",
    "Chris Hipkins": "Q5106890",
    "Christopher Luxon": "Q74370310",
}


def norm_url(u: str) -> str:
    if not isinstance(u, str) or not u.strip():
        return ""
    parts = urlsplit(u.strip())
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parts.path.rstrip("/")
    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not (k.lower().startswith("utm_") or k.lower() in TRACKING_PARAMS)]
    query = urlencode(kept)
    # keep the fragment -- it can be a real record locator (e.g. a
    # #page=N anchor into a multi-speech PDF volume), the same way
    # YouTube's ?v= is meaningful. Only tracking params are dropped.
    fragment = parts.fragment
    return urlunsplit((scheme, netloc, path, query, fragment))


def fix(s):
    if not isinstance(s, str):
        return ""
    return ftfy.fix_text(s)


def opening_salutation(text: str, n_lines: int = 3) -> str:
    if not isinstance(text, str) or not text.strip():
        return ""
    lines = [l.strip() for l in text.replace("\r", "\n").split("\n") if l.strip()]
    return " / ".join(lines[:n_lines])


def type_flag_from_title(title: str) -> str:
    t = (title or "").lower()
    if "entrevista" in t or "interview" in t:
        return ("This row is an INTERVIEW (Q&A) -- full_text may include the "
                "interviewer's questions, not only the leader's words.")
    if any(k in t for k in ["declaraci", "punto de prensa", "conferencia de prensa",
                            "press conference", "declaración a medios",
                            "statement to the press", "press point"]):
        return ("This row is a PRESS DECLARATION / PRESS-POINT rather than a "
                "prepared address.")
    if any(k in t for k in ["joint statement", "joint declaration", "comunicado conjunto",
                            "declaración conjunta", "g7", "g20", "g-7", "g-20"]):
        return ("This row may be a JOINT / MULTILATERAL statement -- not solely "
                "the leader's own words.")
    return ""


def build(df: pd.DataFrame, language: str, leader_qid: str) -> pd.DataFrame:
    has_tr = "full_text_en" in df.columns
    out = pd.DataFrame()

    out["country"] = df["country"].map(fix)
    out["leader"] = df["leader"].map(fix)
    if leader_qid == "auto":
        out["leader_qid"] = out["leader"].map(LEADER_QID).fillna("")
        missing = out.loc[out["leader_qid"].eq(""), "leader"].unique().tolist()
        if missing:
            print(f"WARNING: no QID mapping for leader(s): {missing}")
    else:
        out["leader_qid"] = leader_qid
    out["role"] = df["role"].map(fix)
    out["date"] = df["date"].astype("string").fillna("")
    # Chile/Colombia press feeds publish same-day; no separate publication
    # date is tracked at scrape time, so delivered_date defaults to date.
    out["delivered_date"] = out["date"]

    orig_title = df["title"].map(fix)
    orig_text = df["full_text"].map(fix)

    if has_tr:
        out["title"] = df["title_en"].map(fix).where(lambda s: s.str.strip().ne(""), orig_title)
        out["full_text"] = df["full_text_en"].map(fix).where(lambda s: s.str.strip().ne(""), orig_text)
        out["original_title"] = orig_title
        out["original_text"] = orig_text
        out["translated"] = df["full_text_en"].map(
            lambda v: "yes" if isinstance(v, str) and v.strip() else "no")
    else:
        out["title"] = orig_title
        out["full_text"] = orig_text
        out["original_title"] = orig_title
        out["original_text"] = orig_text
        out["translated"] = "no"

    out["language"] = language
    out["source_url"] = df["source_url"].map(norm_url)
    out["delivered_venue"] = df.get("delivered_venue", "")

    notes = []
    scraper_notes = df["notes"].fillna("") if "notes" in df.columns else pd.Series([""] * len(df))
    for i in range(len(df)):
        prov = str(scraper_notes.iloc[i]).strip()
        sal = opening_salutation(orig_text.iloc[i])
        tflag = type_flag_from_title(orig_title.iloc[i])
        parts = []
        if prov:
            parts.append(f"Provenance: {prov}")
        parts.append(f"Opening salutation: {sal}" if sal else "Opening salutation: [none captured]")
        parts.append("date and delivered_date both taken from the article "
                     "dateline (same-day publication feed); no separate "
                     "publication date tracked at scrape time.")
        if tflag:
            parts.append(tflag)
        wc = len(str(orig_text.iloc[i]).split())
        if wc < 300:
            parts.append(f"SHORT: original text is only {wc} words -- possible "
                         f"stub/excerpt, verify against full transcript.")
        notes.append(" | ".join(parts))
    out["notes"] = [fix(n) for n in notes]

    return out[SCHEMA]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--language", required=True, help="Original language, e.g. 'Spanish'")
    ap.add_argument("--leader-qid", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pages-fetched", type=int, default=None,
                    help="For the hand-off report (scraper doesn't persist this).")
    args = ap.parse_args()

    raw = pd.read_csv(args.input, dtype=str, keep_default_na=False)
    scraped_n = len(raw)

    out = build(raw, args.language, args.leader_qid)

    # ---- URL dedup -----------------------------------------------------
    # For most sources source_url is unique per speech. For a multi-speech
    # PDF volume the locator is <url>#page=N and two speeches can share a
    # page, so those rows are disambiguated by date + title before dedup;
    # a genuine duplicate (same url, date and title) still collapses.
    def _dupkey(r):
        u = r["source_url"]
        if "#page=" in u:
            return f"{u}|{r['date']}|{re.sub(r'[^a-z0-9]', '', r['title'].lower())[:40]}"
        return u
    out["_key"] = out.apply(_dupkey, axis=1)
    dup_mask = out["_key"].duplicated(keep=False) & out["source_url"].ne("")
    suspected_dups = out.loc[dup_mask, ["date", "title", "source_url"]].copy()
    # keep the longest full_text per url
    out["_len"] = out["full_text"].str.len()
    out = (out.sort_values("_len", ascending=False)
              .drop_duplicates(subset="_key", keep="first")
              .sort_values(["date", "title"])
              .drop(columns=["_key", "_len"]))

    # ---- write (QUOTE_ALL, utf-8, no Excel) ----------------------------
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(SCHEMA)
        for _, row in out.iterrows():
            w.writerow([row[c] for c in SCHEMA])

    # ---- hand-off report ---------------------------------------------
    over_limit = out["full_text"].str.len().gt(32767).sum()
    over_rows = out.loc[out["full_text"].str.len() > 32767, ["date", "title", "full_text"]]
    blank_url = out["source_url"].eq("").sum()
    word_counts = out["full_text"].str.split().str.len()
    shortest = int(word_counts.min()) if len(word_counts) else 0
    excerpt_rows = out[out["notes"].str.contains("SHORT:")][["date", "title"]]
    non_en = out[out["translated"].eq("no")][["date", "title", "language"]] if False else None

    print("\n" + "=" * 64)
    print(f"HAND-OFF REPORT  --  {args.out}")
    print("=" * 64)
    print(f"speeches scraped          = {scraped_n}")
    print(f"rows in file (no header)  = {len(out)}    (was {scraped_n} pre-dedupe)")
    print(f"pages fetched             = {args.pages_fetched if args.pages_fetched else 'see scrape log / rerun listing'}")
    print(f"rows after URL dedupe     = {len(out)}")
    print(f"cells over 32,767 chars   = {over_limit}    (must be 0)")
    print(f"rows with blank source_url= {blank_url}    (should be 0)")
    print(f"shortest speech (words)   = {shortest}" + ("   <-- under 300, see excerpt list" if shortest < 300 else ""))
    print("-" * 64)
    print(f"suspected duplicates by URL ({len(suspected_dups)} rows involved):")
    for _, r in suspected_dups.iterrows():
        print(f"    {r['date']}  {r['source_url']}")
    print(f"excerpt / stub rows (<300 words) ({len(excerpt_rows)}):")
    for _, r in excerpt_rows.iterrows():
        print(f"    {r['date']}  {r['title'][:80]}")
    if over_limit:
        print(f"rows over 32,767 chars ({over_limit}) -- CHECK whether truncated or genuinely long:")
        for _, r in over_rows.iterrows():
            tail = r["full_text"][-60:].replace("\n", " ")
            print(f"    {r['date']}  {len(r['full_text'])} chars  ...ends: {tail!r}")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    main()
