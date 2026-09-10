"""Post-finalize field fixup for srilanka_FINAL.csv.

finalize_dataset.py treats the whole file as one language. Sri Lanka is mixed:
 - text-route rows  = native English official transcripts  -> leave as-is
 - video-route rows = YouTube Sinhala ASR auto-translated to English by YouTube.
   The spoken language is Sinhala and the English is machine output, so:
       language       -> Sinhala
       translated     -> yes
       original_title -> the raw (Sinhala/Tamil) video title, when non-Latin;
                         blank when PMD's own title was already English
       original_text  -> stays blank (the source is audio; no verbatim
                         Sinhala transcript exists -- the notes say so)
"""
import re
import pandas as pd

CSV = "data/processed/srilanka_FINAL.csv"
d = pd.read_csv(CSV, dtype=str, keep_default_na=False)

isvid = d["source_url"].str.contains("youtube", case=False)
pat = re.compile(r"Original video title \(Sinhala\):\s*(['\"])(.+?)\1\.\s", re.S)
NONLAT = re.compile(r"[^\x00-\x7f]")

for i in d.index[isvid]:
    d.at[i, "language"] = "Sinhala"
    d.at[i, "translated"] = "yes"
    m = pat.search(d.at[i, "notes"])
    raw = m.group(2).strip() if m else ""
    d.at[i, "original_title"] = raw if (raw and NONLAT.search(raw)) else ""

d.to_csv(CSV, index=False, encoding="utf-8")
print(d.groupby(["language", "translated"]).size().to_string())
print("video rows:", int(isvid.sum()),
      "| with non-Latin original_title:",
      int((isvid & d["original_title"].str.len().gt(0)).sum()))
