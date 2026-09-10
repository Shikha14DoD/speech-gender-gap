"""
Merge the two Sri Lanka sources into one dataset:

  1. data/processed/srilanka.csv        -- TEXT route (official-site
     verbatim transcripts via Wayback / live). Clean, punctuated English.
     Covers Wickremesinghe (2023 - Sep 2024) + some Dissanayake / a bit
     of Amarasuriya. PRIMARY where present.
  2. data/processed/srilanka_video.csv  -- VIDEO route (PMD YouTube,
     YouTube Sinhala ASR auto-translated to English). Rough text, but the
     bulk of Dissanayake-era coverage.

A speech present in both is kept once, from the TEXT source (verbatim).
Video rows with no text match are added. Matching = same leader, dates
within +/-3 days, and strong title-token overlap.

Usage:  python merge_srilanka.py
Output: data/processed/srilanka_merged.csv
"""

import re
import unicodedata
import datetime as dt
import pandas as pd

TEXT = "data/processed/srilanka.csv"
VIDEO = "data/processed/srilanka_video.csv"
OUT = "data/processed/srilanka_merged.csv"

_STRIP = re.compile(
    r"\b(full[- ]text( of)?|speech|statement|address|remarks|declaration|"
    r"message|lecture|keynote|policy statement|by|of|made by|delivered by|"
    r"his excellency|the president|the prime minister|president|prime minister|"
    r"ranil wickremesinghe|anura kumara dissanayake|akd|harini amarasuriya|"
    r"to the nation|at the|during the|to the)\b", re.I)


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

    # Video rows with no recoverable English caption carry no linguistic
    # content -- drop them from the deliverable, list them for the hand-off.
    nocap = video["full_text"].str.contains("NO ENGLISH AUTO-CAPTION", na=False)
    if nocap.any():
        video[nocap][["date", "title", "source_url"]].to_csv(
            "data/processed/srilanka_video_nocaption.csv", index=False,
            encoding="utf-8")
        print(f"VIDEO rows with no English caption (dropped, listed in "
              f"srilanka_video_nocaption.csv): {int(nocap.sum())}")
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
