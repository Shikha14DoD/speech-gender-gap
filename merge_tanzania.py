"""
Merge the two Tanzania sources into one dataset:

  1. data/processed/tanzania.csv        -- TEXT route (State House PDF
     transcripts, ikulu.go.tz/speeches). Clean, verbatim; mostly Swahili,
     some English. ~44 curated set-piece speeches. PRIMARY where present.
  2. data/processed/tanzania_video.csv  -- VIDEO route (Ikulu YouTube,
     YouTube Swahili ASR auto-translated to English). Rough text, but the
     bulk of the coverage.

A speech present in both is kept once, from the TEXT source (verbatim).
Video rows with no text match are added. Matching = same leader, dates
within +/-3 days, and strong title-token overlap.

Usage:  python merge_tanzania.py
Output: data/processed/tanzania_merged.csv
"""

import re
import unicodedata
import datetime as dt
import pandas as pd

TEXT = "data/processed/tanzania.csv"
VIDEO = "data/processed/tanzania_video.csv"
OUT = "data/processed/tanzania_merged.csv"

_STRIP = re.compile(
    r"\b(hotuba|ya|wa|katika|wakati|speech|statement|address|remarks|"
    r"keynote|acceptance|welcome|welcoming|declaration|message|by|of|"
    r"her excellency|his excellency|the president|the prime minister|"
    r"president|prime minister|rais|mhe|mheshimiwa|dkt|dr|samia suluhu hassan|"
    r"kassim majaliwa|mwigulu nchemba|to the nation|at the|during the)\b", re.I)


def norm(title):
    t = unicodedata.normalize("NFKD", str(title)).encode("ascii", "ignore").decode()
    t = _STRIP.sub(" ", t.lower())
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def toks(title):
    return {w for w in norm(title).split() if len(w) > 3}


def _d(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def main():
    text = pd.read_csv(TEXT, dtype=str, keep_default_na=False)
    video = pd.read_csv(VIDEO, dtype=str, keep_default_na=False)
    print(f"TEXT: {len(text)} rows   VIDEO: {len(video)} rows")

    nocap = video["full_text"].str.contains("NO ENGLISH AUTO-CAPTION", na=False)
    if nocap.any():
        video[nocap][["date", "title", "source_url"]].to_csv(
            "data/processed/tanzania_video_nocaption.csv", index=False,
            encoding="utf-8")
        print(f"VIDEO rows with no English caption (dropped, listed in "
              f"tanzania_video_nocaption.csv): {int(nocap.sum())}")
        video = video[~nocap].reset_index(drop=True)

    tindex = []
    for _, r in text.iterrows():
        tindex.append((r["leader"], _d(r["date"]), toks(r["title"])))

    def is_dup(row):
        rl, rd, rt = row["leader"], _d(row["date"]), toks(row["title"])
        if not rt:
            return False
        for tl, td, tt in tindex:
            if tl != rl or not tt:
                continue
            if rd and td and abs((rd - td).days) > 3:
                continue
            jac = len(rt & tt) / len(rt | tt)
            if jac >= 0.4:
                return True
        return False

    video["_dup"] = video.apply(is_dup, axis=1)
    vid_keep = video[~video["_dup"]].drop(columns=["_dup"])
    vid_drop = int(video["_dup"].sum())

    merged = pd.concat([text, vid_keep], ignore_index=True, sort=False)
    merged = merged.sort_values(["date", "leader", "title"]).reset_index(drop=True)
    merged.to_csv(OUT, index=False, encoding="utf-8")

    print(f"\nvideo rows matching a text speech (dropped): {vid_drop}")
    print(f"video rows added (unique):                   {len(vid_keep)}")
    print(f"merged total:                                {len(merged)}")
    print(f"  date range: {merged['date'].min()} -> {merged['date'].max()}")
    print(merged.groupby(["leader"]).agg(n=("title", "size")).to_string())
    print(merged["date"].str[:7].value_counts().sort_index().to_string())
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
