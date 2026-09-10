"""
Post-finalize field fixup for tanzania_FINAL.csv.

`finalize_dataset.py --language Swahili` labels every row "Swahili" and, in
its translated branch, fills original_title/original_text for every row.
Tanzania is mixed, so correct per row:

  video rows (YouTube Swahili ASR -> English MT):
      language       -> Swahili
      translated     -> yes
      original_title -> the raw Swahili video title (from notes); blank if
                        YouTube's own title was already English
      original_text  -> blank (source is audio; no verbatim Swahili text)

  English-original State House PDFs:
      language       -> English
      translated     -> no
      original_title / original_text -> blank

  Swahili-original State House PDFs:
      language       -> Swahili
      translated     -> yes   (full_text is the Google translation,
                               original_text is the Swahili PDF text)

Usage: python fix_tanzania_langfields.py
"""
import re
import pandas as pd

CSV = "data/processed/tanzania_FINAL.csv"
MERGED = "data/processed/tanzania_merged.csv"

d = pd.read_csv(CSV, dtype=str, keep_default_na=False)

# original per-row language, keyed by source_url, from the pre-finalize file
orig_lang = {}
try:
    m = pd.read_csv(MERGED, dtype=str, keep_default_na=False)
    orig_lang = dict(zip(m["source_url"], m["language"]))
except Exception:
    pass

is_vid = d["source_url"].str.contains("youtube", case=False)
vpat = re.compile(r"Original video title \(Swahili\):\s*(['\"])(.+?)\1\.\s", re.S)
NONLAT_OR_SW = re.compile(r"[^\x00-\x7f]|\b(hotuba|rais|wakati|akizindua|akifungua)\b", re.I)

n_v = n_en = n_sw = 0
for i in d.index:
    url = d.at[i, "source_url"]
    if is_vid[i]:
        d.at[i, "language"] = "Swahili"
        d.at[i, "translated"] = "yes"
        mm = vpat.search(d.at[i, "notes"])
        raw = mm.group(2).strip() if mm else ""
        d.at[i, "original_title"] = raw if (raw and NONLAT_OR_SW.search(raw)) else ""
        d.at[i, "original_text"] = ""
        n_v += 1
        continue
    lang = orig_lang.get(url, "")
    if lang == "English" or "English original" in d.at[i, "notes"]:
        d.at[i, "language"] = "English"
        d.at[i, "translated"] = "no"
        d.at[i, "original_title"] = ""
        d.at[i, "original_text"] = ""
        n_en += 1
    else:
        d.at[i, "language"] = "Swahili"
        d.at[i, "translated"] = "yes"
        n_sw += 1

d.to_csv(CSV, index=False, encoding="utf-8")
print(f"video rows: {n_v}   English PDF rows: {n_en}   Swahili PDF rows: {n_sw}")
print(d.groupby(["language", "translated"]).size().to_string())
