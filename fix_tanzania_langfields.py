"""
Post-finalize field fixup for tanzania_FINAL.csv.

`finalize_dataset.py --language Swahili` labels every row "Swahili" and, in
its translated branch, fills original_title/original_text for every row.
Tanzania is mixed, so correct per row:

  English-audio video rows (spoken language found by
  audit_tanzania_video_language.py -- ~40% of the videos):
      language       -> English
      translated     -> no    (caption is native English ASR, no translation)
      original_text  -> blank (there is no Swahili source to check against)

  Swahili-audio video rows (YouTube Swahili ASR -> English MT):
      language       -> Swahili
      translated     -> yes
      original_title -> the raw Swahili video title (from notes); blank if
                        YouTube's own title was already English
      original_text  -> the native Swahili auto-caption, when the scraper
                        recovered one (see scraper_tanzania_video.py
                        _swahili_caption); blank only for the videos where
                        that caption genuinely isn't available

  English-original State House PDFs:
      language       -> English
      translated     -> no
      original_title / original_text -> blank

  Swahili-original State House PDFs:
      language       -> Swahili
      translated     -> yes if full_text is actually English (the
                        translation succeeded); "no" if translate_csv.py
                        never reached it or the translation service failed
                        for that row -- full_text is still the raw Swahili
                        in that case, detected via a language heuristic
                        rather than assumed.

Usage: python fix_tanzania_langfields.py
"""
import re
import pandas as pd
from finalize_dataset import norm_url

CSV = "data/processed/tanzania_FINAL.csv"
MERGED = "data/processed/tanzania_merged.csv"

_SW_HINT = re.compile(
    r"\b(na|ya|wa|kwa|katika|ni|kwamba|hii|hizo|serikali|watu|nchi|ndugu|"
    r"waheshimiwa|mheshimiwa|zetu|yetu|hili|ambao|kufanya|maendeleo)\b", re.I)
_EN_HINT = re.compile(
    r"\b(the|and|of|to|is|are|this|that|with|for|our|we|will|have)\b", re.I)


def _still_swahili(text):
    sample = text[:4000].lower()
    return len(_SW_HINT.findall(sample)) > len(_EN_HINT.findall(sample))


d = pd.read_csv(CSV, dtype=str, keep_default_na=False)

# original per-row language + scraper-supplied original_text, keyed by
# source_url, from the pre-finalize file
orig_lang = {}
merged_orig_text = {}
try:
    m = pd.read_csv(MERGED, dtype=str, keep_default_na=False)
    m_url = m["source_url"].map(norm_url)   # match finalize_dataset.py's normalization
    orig_lang = dict(zip(m_url, m["language"]))
    if "original_text" in m.columns:
        merged_orig_text = dict(zip(m_url, m["original_text"]))
except Exception:
    pass

is_vid = d["source_url"].str.contains("youtube", case=False)
vpat = re.compile(r"Original video title \(Swahili\):\s*(['\"])(.+?)\1\.\s", re.S)
NONLAT_OR_SW = re.compile(r"[^\x00-\x7f]|\b(hotuba|rais|wakati|akizindua|akifungua)\b", re.I)

n_v = n_en = n_sw = n_v_en = 0
for i in d.index:
    url = d.at[i, "source_url"]
    if is_vid[i]:
        mm = vpat.search(d.at[i, "notes"])
        raw = mm.group(2).strip() if mm else ""
        d.at[i, "original_title"] = raw if (raw and NONLAT_OR_SW.search(raw)) else ""
        if orig_lang.get(url, "") == "English":
            # English-audio video (see audit_tanzania_video_language.py): the
            # caption is YouTube's native English ASR, not a translation, and
            # there is no Swahili source -- so nothing is missing.
            d.at[i, "language"] = "English"
            d.at[i, "translated"] = "no"
            d.at[i, "original_text"] = ""
            n_v_en += 1
            continue
        d.at[i, "language"] = "Swahili"
        d.at[i, "translated"] = "yes"
        # finalize_dataset.py falls back to full_text (English, for a video
        # row) when the scraper's original_text column is blank -- that's
        # correct for text-route rows but wrong here, so re-check against
        # what the scraper actually recovered and blank it out if nothing.
        if not merged_orig_text.get(url, "").strip():
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
        if _still_swahili(d.at[i, "full_text"]):
            d.at[i, "translated"] = "no"
            d.at[i, "notes"] = (
                d.at[i, "notes"] + " | English translation unavailable: "
                "the translation service failed or was rate-limited for this "
                "row; full_text is the original Swahili, untranslated. "
                "Re-run translate_csv.py on this row when the API quota resets.")
        else:
            d.at[i, "translated"] = "yes"
        n_sw += 1

d.to_csv(CSV, index=False, encoding="utf-8")
print(f"video rows (Swahili audio): {n_v}   video rows (English audio): {n_v_en}   "
      f"English PDF rows: {n_en}   Swahili PDF rows: {n_sw}")
print(d.groupby(["language", "translated"]).size().to_string())
