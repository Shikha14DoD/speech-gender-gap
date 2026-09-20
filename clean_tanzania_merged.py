"""
Post-merge cleanup for data/processed/tanzania_merged.csv, run between
merge_tanzania.py and translate_csv.py / finalize_dataset.py.

Passes:
  1. drop rows that are not a single-speaker prepared speech --
       - joint communiqués / summit declarations (not the leader's own words)
       - video event-coverage / narration that slipped the title gate
       - foreign-leader remarks mis-attributed by the keyword heuristic
       - corrupted / empty captions
     Driven by NOT_SPEECH_TITLES (substring, quote-insensitive) + regexes;
     populated from verification, not guessed.
  1b. drop videos whose speech recognition ran in the wrong language
  2. drop near-duplicate pairs (same leader, dates within 2 days, title-token
     Jaccard >= 0.5 or shared 80-char prefix) -- keep the text row over the
     video row, else the longer transcript.
  3. add empty full_text_en / title_en columns and PRE-FILL them for rows
     that need no Swahili->English translation (English-original PDFs and the
     already-English video captions), so translate_csv.py only touches the
     Swahili PDF rows.

Idempotent.  Usage: python clean_tanzania_merged.py
"""
import re
import datetime as dt
import pandas as pd

CSV = "data/processed/tanzania_merged.csv"

NOT_SPEECH_TITLES = [
    "COMMUNIQUÉ OF THE EXTRA-ORDINARY SUMMIT",
    "COMMUNIQUE OF THE EXTRA-ORDINARY SUMMIT",
]
_JOINT = re.compile(r"communiqu|joint (statement|declaration|communiqu)|"
                    r"summit declaration|final declaration", re.I)
_ANNOUNCE = re.compile(r"(?i)\b(to deliver|to address|kutahutubia|will address)\b")

STOP = {"hotuba", "ya", "wa", "katika", "wakati", "speech", "live", "full",
        "president", "rais", "mhe", "mheshimiwa", "dkt", "samia", "suluhu",
        "hassan", "her", "excellency", "the", "and", "for", "with", "of",
        "statement", "address", "remarks", "2023", "2024", "2025", "2026"}
PLACES = {"dodoma", "zanzibar", "dar", "mwanza", "arusha", "mbeya", "geneva",
          "riyadh", "luanda", "beijing", "moscow", "nairobi", "kampala",
          "addis", "new", "york"}


def toks(t):
    t = re.sub(r"[^a-z0-9 ]", " ", str(t).lower())
    return {w for w in t.split() if len(w) > 3 and w not in STOP}


def dd(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def _nq(s):
    return (s.str.replace("’", "'").str.replace("‘", "'")
             .str.replace("“", '"').str.replace("”", '"'))


def _words(t):
    return {w for w in re.findall(r"[a-zà-ÿ]{5,}", str(t).lower())}


def content_overlap(a, b):
    """Jaccard overlap of distinct 5+-letter words. On this corpus true
    duplicates (same speech from the PDF set and the video set) score
    0.60-0.82 while different speeches score <= 0.18, so 0.40 is a safe cut."""
    A, B = _words(a), _words(b)
    return len(A & B) / len(A | B) if A and B else 0.0


DUP_OVERLAP = 0.40
DUP_WINDOW_DAYS = 6      # video upload can lag the event by several days


def main():
    d = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    n0 = len(d)

    # ---- pass 1: non-speech -------------------------------------------------
    title_n = _nq(d["title"])
    drop = pd.Series(False, index=d.index)
    for key in NOT_SPEECH_TITLES:
        drop |= title_n.str.contains(key.replace("’", "'"), regex=False, case=False)
    drop |= title_n.str.contains(_JOINT)
    drop |= title_n.str.match(_ANNOUNCE)
    # Some YouTube auto-captions come back as garbled phonetic
    # transliteration rather than real English MT (low ASR confidence) --
    # these tend to also be short. Use a slightly higher bar than Sri
    # Lanka's for that reason.
    wc = d["full_text"].str.split().str.len()
    drop |= d["source_url"].str.contains("youtube", case=False) & (wc < 350)
    for i in d.index[drop]:
        print(f"DROP not-speech   {d.at[i,'date']}  {d.at[i,'title'][:65]}")
    d = d[~drop].reset_index(drop=True)

    # ---- pass 1b: videos whose speech recognition ran in the WRONG language
    # (see audit_tanzania_video_language.py) -- gibberish captions, not usable
    bad_asr = d["language"].str.startswith("UNRELIABLE_ASR")
    for i in d.index[bad_asr]:
        print(f"DROP wrong-language ASR {d.at[i,'date']}  {d.at[i,'language']}  {d.at[i,'title'][:55]}")
    d = d[~bad_asr].reset_index(drop=True)

    # ---- pass 2: near-duplicates -----------------------------------------
    d["_fl"] = d["full_text"].str.len().astype(int)
    d["_txt"] = ~d["source_url"].str.contains("youtube", case=False)
    idx = list(d.index)
    gone = set()
    for a in range(len(idx)):
        i = idx[a]
        if i in gone:
            continue
        for b in range(a + 1, len(idx)):
            j = idx[b]
            if j in gone or d.at[i, "leader"] != d.at[j, "leader"]:
                continue
            da, db = dd(d.at[i, "date"]), dd(d.at[j, "date"])
            if not da or not db or abs((da - db).days) > 2:
                continue
            ta, tb = toks(d.at[i, "title"]), toks(d.at[j, "title"])
            if not ta or not tb:
                continue
            jac = len(ta & tb) / len(ta | tb)
            prefix = d.at[i, "full_text"][:80].strip() == d.at[j, "full_text"][:80].strip()
            if jac < 0.5 and not prefix:
                continue
            if (ta & PLACES) and (tb & PLACES) and (ta & PLACES) != (tb & PLACES):
                continue
            keep, toss = (i, j)
            if (d.at[j, "_txt"], d.at[j, "_fl"]) > (d.at[i, "_txt"], d.at[i, "_fl"]):
                keep, toss = (j, i)
            gone.add(toss)
            print(f"DROP duplicate    {d.at[toss,'date']} "
                  f"[{'TXT' if d.at[toss,'_txt'] else 'VID'}] {d.at[toss,'title'][:55]}")
    d = d.drop(index=list(gone)).drop(columns=["_fl", "_txt"]).reset_index(drop=True)

    # ---- pass 2b: the SAME speech present in both routes ----------------
    # Title matching can't see these (Swahili-titled PDF vs English-titled
    # video, upload dates a few days apart), so compare the text itself, like
    # with like: English vs English, Swahili vs Swahili. The official PDF is
    # verbatim and wins; the video-ASR row is dropped.
    is_vid = d["source_url"].str.contains("youtube", case=False)
    pdf_en = d["notes"].str.contains("English original", na=False)
    drop_vid = set()
    for vi in d.index[is_vid]:
        v = d.loc[vi]
        for pi in d.index[~is_vid]:
            p_ = d.loc[pi]
            if v["leader"] != p_["leader"]:
                continue
            da, db = dd(v["date"]), dd(p_["date"])
            if not da or not db or abs((da - db).days) > DUP_WINDOW_DAYS:
                continue
            if pdf_en[pi]:                       # English PDF vs English caption
                a_txt, b_txt = v["full_text"], p_["full_text"]
            elif v["language"] == "Swahili" and v.get("original_text", ""):
                a_txt, b_txt = v["original_text"], p_["full_text"]   # Swahili vs Swahili
            else:
                continue
            ov = content_overlap(a_txt, b_txt)
            if ov >= DUP_OVERLAP:
                drop_vid.add(vi)
                print(f"DROP cross-route dup {v['date']} [VID] {v['title'][:40]}  "
                      f"== {p_['date']} [PDF] {p_['title'][:34]}  overlap={ov:.2f}")
                break
    d = d.drop(index=list(drop_vid)).reset_index(drop=True)

    # ---- pass 3: prep translation columns --------------------------------
    if "full_text_en" not in d.columns:
        d["full_text_en"] = ""
    if "title_en" not in d.columns:
        d["title_en"] = ""
    is_vid = d["source_url"].str.contains("youtube", case=False)
    is_en_pdf = ~is_vid & d["notes"].str.contains("English original", na=False)
    ready = is_vid | is_en_pdf          # no sw->en translation needed
    # same mask on both sides, so re-running on a file that already has some
    # of these columns filled is safe (it used to crash: mask/value mismatch)
    m_text = ready & d["full_text_en"].eq("")
    d.loc[m_text, "full_text_en"] = d.loc[m_text, "full_text"]
    m_title = ready & d["title_en"].eq("")
    d.loc[m_title, "title_en"] = d.loc[m_title, "title"]

    d.to_csv(CSV, index=False, encoding="utf-8")
    print(f"\n{n0} -> {len(d)} rows  ({n0 - len(d)} dropped)")
    print(f"  need sw->en translation: {int((~ready).sum())}  "
          f"(pre-filled: {int(ready.sum())})")
    print(d.groupby("leader").size().to_string())


if __name__ == "__main__":
    main()
