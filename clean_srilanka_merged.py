"""
Post-merge cleanup for data/processed/srilanka_merged.csv, run between
merge_srilanka.py and finalize_dataset.py.

Three passes:

  1. drop rows that are not speeches --
       - PMD "President to deliver ..." announcement stubs
       - third-person PMD news write-ups *about* a speech (Ranil-era
         index.php WordPress posts were mostly news, not transcripts)
       - YouTube ceremony / anthem clips (anchor narration, [Music] only)
       - foreign-leader remarks / IMF-official remarks mis-attributed by the
         title keyword heuristic
       - one fully corrupted caption ("More information" repeated)
  2. drop URL-path and re-upload duplicates the exact-text pass missed
     (presidentsoffice.gov.lk/<slug> vs pmd.gov.lk/news/<slug>;
      "Full Speech" upload vs "LIVE" stream of the same event) -- keeps the
     text row over the video row, else the longer transcript
  3. re-attribute the 05-Apr-2025 joint-press-conference statement to
     President Dissanayake (title names the PM, speaker of record is the
     President)

Everything removed is printed. Idempotent.

Usage:  python clean_srilanka_merged.py
"""
import re
import datetime as dt
import pandas as pd

CSV = "data/processed/srilanka_merged.csv"

# --- pass 1: explicit non-speech titles (substring match) -------------------
NOT_SPEECH_TITLES = [
    "President meets youth group",
    "Addresses G77 & China Summit in Cuba",
    "Address at the UNGA: Sri Lanka's Jour",
    "මූල්‍ය දුෂ්කරතා ඇති",  # Sinhala "financial distress" news
    "Declaration of Assets and Liabilities Law",
    "Statement by the Government of Sri Lanka on discussions held in Washin",
    "President of the Maldives Mohamed M",
    "Addresses Global Financial Distress",
    "Documentary program on the President",
    "Presentation of the 2025 Annual Report of NSB",
    "Muizzu",
    "Grand Ceremonial Reception",
    "We warmly welcome the President of Viet Nam",
    "International Monetary Fund to evaluate",
]
ANNOUNCE = re.compile(r"(?i)\s*president to deliver\b")


def _d(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except Exception:
        return None


# --- pass 2: near-duplicate detection --------------------------------------
STOP = {"full", "speech", "live", "president", "anura", "kumara", "dissanayake",
        "disanayake", "delivered", "hon", "excellency", "statement", "address",
        "remarks", "the", "and", "for", "with", "his", "her",
        "2023", "2024", "2025", "2026"}
PLACES = {"york", "japan", "cuba", "washington", "maldives", "india", "vietnam",
          "china", "geneva", "davos", "delhi", "male"}


def _toks(t):
    t = re.sub(r"[^a-z0-9 ]", " ", str(t).lower())
    return {w for w in t.split() if len(w) > 3 and w not in STOP}


def main():
    d = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    n0 = len(d)

    # pass 1  (apostrophe/quote-insensitive title match)
    def _nq(s):
        return (s.str.replace("’", "'").str.replace("‘", "'")
                 .str.replace("“", '"').str.replace("”", '"'))
    title_n = _nq(d["title"])
    drop = pd.Series(False, index=d.index)
    for key in NOT_SPEECH_TITLES:
        k = key.replace("’", "'").replace("‘", "'")
        drop |= title_n.str.contains(k, regex=False)
    drop |= title_n.str.match(ANNOUNCE)
    wc = d["full_text"].str.split().str.len()
    drop |= d["source_url"].str.contains("youtube", case=False) & (wc < 250)
    for i in d.index[drop]:
        print(f"DROP not-speech   {d.at[i,'date']}  {d.at[i,'title'][:60]}")
    d = d[~drop].reset_index(drop=True)

    # pass 2
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
            da, db = _d(d.at[i, "date"]), _d(d.at[j, "date"])
            if not da or not db or abs((da - db).days) > 2:
                continue
            ta, tb = _toks(d.at[i, "title"]), _toks(d.at[j, "title"])
            if not ta or not tb:
                continue
            jac = len(ta & tb) / len(ta | tb)
            prefix = d.at[i, "full_text"][:80].strip() == d.at[j, "full_text"][:80].strip()
            if jac < 0.5 and not prefix:
                continue
            if (ta & PLACES) and (tb & PLACES) and (ta & PLACES) != (tb & PLACES):
                continue  # different state visits -> keep both
            keep, toss = (i, j)
            if (d.at[j, "_txt"], d.at[j, "_fl"]) > (d.at[i, "_txt"], d.at[i, "_fl"]):
                keep, toss = (j, i)
            gone.add(toss)
            print(f"DROP duplicate    {d.at[toss,'date']}  "
                  f"[{'TXT' if d.at[toss,'_txt'] else 'VID'}] {d.at[toss,'title'][:55]}")
    d = d.drop(index=list(gone)).drop(columns=["_fl", "_txt"]).reset_index(drop=True)

    # pass 3
    m = d["title"].str.contains(
        "Joint Press Conference on the Occasion of the State Visit of the Indian",
        regex=False)
    if m.any():
        d.loc[m, "leader"] = "Anura Kumara Dissanayake"
        d.loc[m, "role"] = "President"
        print(f"RE-ATTRIBUTE {int(m.sum())} row(s) -> President Dissanayake "
              "(05-Apr-2025 joint press conference)")

    d.to_csv(CSV, index=False, encoding="utf-8")
    print(f"\n{n0} -> {len(d)} rows")
    print(d.groupby("leader").size().to_string())


if __name__ == "__main__":
    main()
