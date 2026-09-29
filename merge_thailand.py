"""
Merge Thailand's two routes into one dataset:
  1. data/processed/thailand.csv       -- TEXT route (mfa.go.th Speeches
     section; official government text, sometimes PDF-only).
  2. data/processed/thailand_video.csv -- VIDEO route (official
     @thaigovernment YouTube channel; speech-recognition transcripts).

The same speech can appear on both (e.g. a UNGA statement is both published
as text on mfa.go.th AND recorded on the government's YouTube channel).
Since the text route's copy is the government's own verbatim written text
and the video route's is an ASR transcript, the TEXT version wins on overlap;
the video row is dropped. Detection: same leader, dates within 4 days,
word-overlap Jaccard >= 0.30 (video ASR of the same speech diverges more
from the official text than two verbatim copies of each other would).

Usage: python merge_thailand.py
Output: data/processed/thailand_merged.csv
"""
import re
import datetime as dt
import pandas as pd

TEXT = "data/processed/thailand.csv"
VIDEO = "data/processed/thailand_video.csv"
OUT = "data/processed/thailand_merged.csv"


def words(t):
    return set(re.findall(r"[ก-๙a-z]{4,}", str(t).lower()))


def main():
    text = pd.read_csv(TEXT, dtype=str, keep_default_na=False)
    video = pd.read_csv(VIDEO, dtype=str, keep_default_na=False)

    drop_video_idx = []
    for vi, v in video.iterrows():
        wv = words(v.full_text)
        for ti, t in text.iterrows():
            if v.leader != t.leader:
                continue
            d = abs((dt.date.fromisoformat(v.date) - dt.date.fromisoformat(t.date)).days)
            if d > 4:
                continue
            wt = words(t.full_text)
            ov = len(wv & wt) / len(wv | wt) if wv and wt else 0
            if ov >= 0.30:
                print(f"  overlap {ov:.2f}: video {v.date} {v.title[:45]!r} <-> text {t.date} {t.title[:45]!r}")
                drop_video_idx.append(vi)
                break
    video = video.drop(index=drop_video_idx)

    out = pd.concat([text, video], ignore_index=True).sort_values("date")
    out.to_csv(OUT, index=False, encoding="utf-8")
    print(f"\n{len(text)} text + {len(video)} video (after dropping {len(drop_video_idx)} duplicates of text) -> {len(out)} rows")


if __name__ == "__main__":
    main()
