"""
Merge Latvia's two routes into one dataset:
  1. data/processed/latvia.csv       -- TEXT route (mk.gov.lv press feed;
     third-person write-ups with embedded quotes).
  2. data/processed/latvia_video.csv -- VIDEO route (his own channel, event
     organisers, third-party news re-uploads; full speech-recognition
     transcripts, much closer to verbatim).

The one known cross-route duplicate (20 Aug border-control press point) was
already excluded from the video candidate list by hand (see
scraper_latvia_video.py's docstring). This still runs an automated
content-overlap check as a safety net before merging, same principle as
merge_tanzania.py -- a video row overlapping a text row within a few days
is dropped (the video, since it's the fuller/more verbatim account, wins
over the press write-up).

Usage: python merge_latvia.py
Output: data/processed/latvia_merged.csv
"""
import re
import datetime as dt
import pandas as pd

TEXT = "data/processed/latvia.csv"
VIDEO = "data/processed/latvia_video.csv"
OUT = "data/processed/latvia_merged.csv"


def words(t):
    return set(re.findall(r"[a-z]{5,}", str(t).lower()))


def main():
    text = pd.read_csv(TEXT, dtype=str, keep_default_na=False)
    video = pd.read_csv(VIDEO, dtype=str, keep_default_na=False)
    text["_route"] = "text"
    video["_route"] = "video"

    drop_text_idx = []
    for vi, v in video.iterrows():
        for ti, t in text.iterrows():
            d = abs((dt.date.fromisoformat(v.date) - dt.date.fromisoformat(t.date)).days)
            if d > 4:
                continue
            wv, wt = words(v.full_text), words(t.full_text)
            ov = len(wv & wt) / len(wv | wt) if wv and wt else 0
            if ov >= 0.30:
                print(f"  overlap {ov:.2f}: video {v.date} {v.title[:45]!r} <-> text {t.date} {t.title[:45]!r}")
                drop_text_idx.append(ti)   # video (fuller) wins over the press write-up
    text = text.drop(index=drop_text_idx)

    out = pd.concat([text, video], ignore_index=True).drop(columns=["_route"]).sort_values("date")
    out.to_csv(OUT, index=False, encoding="utf-8")
    print(f"\n{len(text)} text + {len(video)} video -> {len(out)} rows (dropped {len(drop_text_idx)} superseded text rows)")


if __name__ == "__main__":
    main()
