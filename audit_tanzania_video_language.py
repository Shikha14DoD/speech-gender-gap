"""
Audit (and correct) what language each Tanzania VIDEO row is actually spoken in.

Why this exists: scraper_tanzania_video.py assumed every State House video is
Swahili audio and labelled it "YouTube Swahili speech-recognition,
auto-translated to English", then backfilled `original_text` from YouTube's
`sw` caption track. That is wrong for a large share of videos: Samia gives
many international addresses (G20, FOCAC, WTTC, honorary degrees ...) in
ENGLISH. For those:
  * the English caption is YouTube's native English ASR -- NOT a translation,
    so translated must be "no" and language "English";
  * the `sw` track is YouTube machine-translating the English INTO Swahili, so
    storing it as `original_text` was backwards (a fake "original").
And for a few videos YouTube's speech recognition ran in the WRONG language
(detected Romanian / Filipino / Portuguese for Swahili or English audio),
producing gibberish captions.

How the spoken language is found: yt-dlp lists auto-captions per language and
marks the recogniser's source language with a "-orig" suffix (e.g. `en-orig`,
`sw-orig`). That code is the language the ASR actually heard.

What it does to tanzania_merged.csv and tanzania_video.csv (only rows whose
video id is in the answer cache):
    spoken en  -> language="English", original_text blank, notes reworded
    spoken sw  -> unchanged (genuine Swahili audio)
    other      -> language="UNRELIABLE_ASR_<code>"; clean_tanzania_merged.py
                  drops these

Answers are cached in data/processed/tanzania_video_spoken_lang.csv so a
re-run only queries YouTube for ids it hasn't seen (--refresh re-queries all).

Usage: python audit_tanzania_video_language.py [--refresh]
"""
import argparse
import os
import re

import pandas as pd

os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + r"C:\nvm4w\nodejs"

MERGED = "data/processed/tanzania_merged.csv"
VIDEO = "data/processed/tanzania_video.csv"
CACHE = "data/processed/tanzania_video_spoken_lang.csv"

_ASR_SENTENCE = re.compile(
    r"VIDEO\. Transcript is YouTube's automatic Swahili speech-recognition, "
    r"auto-translated to English by YouTube -- no punctuation, "
    r"machine-translation errors, suitable for thematic/word-frequency "
    r"analysis only, NOT verbatim\.")
_NO_SW_SENTENCE = re.compile(
    r"\s*Native Swahili auto-caption was not recoverable for this video -- "
    r"original_text is blank; the English full_text is YouTube's own "
    r"translation, not independently verified against it\.")
_ENGLISH_ASR = ("VIDEO. Spoken in English; transcript is YouTube's automatic "
                "English speech-recognition (not a translation) -- no "
                "punctuation, recognition errors, suitable for "
                "thematic/word-frequency analysis only, NOT verbatim.")


def video_id(url: str):
    m = re.search(r"v=([\w-]+)", str(url))
    return m.group(1) if m else None


def spoken_language(info: dict) -> str:
    """Language the recogniser heard: the '<code>-orig' caption key, else the
    video's declared language."""
    ac = info.get("automatic_captions") or {}
    for k in ac:
        if k.endswith("-orig"):
            return k[:-5].split("-")[0]
    return (info.get("language") or "?").split("-")[0]


def query(ids):
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "skip_download": True,
            "noprogress": True, "js_runtimes": {"node": {}},
            "ignoreerrors": True}
    out = []
    for n, v in enumerate(ids, 1):
        try:
            with yt_dlp.YoutubeDL(opts) as y:
                info = y.extract_info(f"https://www.youtube.com/watch?v={v}",
                                      download=False)
        except Exception:
            info = None
        if info:
            out.append({"vid": v, "spoken": spoken_language(info),
                        "yt_language": info.get("language") or ""})
        else:
            print(f"  [warn] could not query {v}")
        if n % 10 == 0:
            print(f"  queried {n}/{len(ids)}", flush=True)
    return out


def patch(df: pd.DataFrame, spoken: dict) -> dict:
    counts = {"en": 0, "sw": 0, "unreliable": 0, "unknown": 0}
    if "original_text" not in df.columns:
        df["original_text"] = ""
    for i in df.index[df["source_url"].str.contains("youtube", case=False)]:
        code = spoken.get(video_id(df.at[i, "source_url"]))
        if code is None:
            counts["unknown"] += 1
            continue
        if code == "en":
            df.at[i, "language"] = "English"
            df.at[i, "original_text"] = ""
            notes = _ASR_SENTENCE.sub(_ENGLISH_ASR, df.at[i, "notes"])
            df.at[i, "notes"] = _NO_SW_SENTENCE.sub("", notes)
            counts["en"] += 1
        elif code == "sw":
            counts["sw"] += 1
        else:
            df.at[i, "language"] = f"UNRELIABLE_ASR_{code}"
            counts["unreliable"] += 1
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true",
                    help="re-query YouTube for every id, ignoring the cache")
    args = ap.parse_args()

    merged = pd.read_csv(MERGED, dtype=str, keep_default_na=False)
    ids = sorted({video_id(u) for u in merged["source_url"]
                  if "youtube" in u.lower() and video_id(u)})

    cache = pd.DataFrame(columns=["vid", "spoken", "yt_language"])
    if os.path.exists(CACHE) and not args.refresh:
        cache = pd.read_csv(CACHE, dtype=str, keep_default_na=False)
    todo = [v for v in ids if v not in set(cache["vid"])]
    print(f"{len(ids)} video ids; {len(ids) - len(todo)} cached, {len(todo)} to query")
    if todo:
        cache = pd.concat([cache, pd.DataFrame(query(todo))], ignore_index=True)
        cache.drop_duplicates("vid", keep="last").to_csv(CACHE, index=False, encoding="utf-8")
    spoken = dict(zip(cache["vid"], cache["spoken"]))

    print("spoken-language summary:", pd.Series([spoken.get(v, "?") for v in ids]).value_counts().to_dict())
    for path in (MERGED, VIDEO):
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        c = patch(df, spoken)
        df.to_csv(path, index=False, encoding="utf-8")
        print(f"{path}: {c}")


if __name__ == "__main__":
    main()
