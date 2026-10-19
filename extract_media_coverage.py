"""
Media-coverage side-investigation for Ginette's Part 1 master handoff:
for the doc types excluded from the main speech NMF (press_summary_of_
speech, press_conference, wire_announcement, interview), check whether
any of it is usable to study how MEDIA covers a leader -- what topics/
questions journalists focus on -- as distinct from the leader's own
words (the main NMF analysis).

Finding: almost none of it is independent media coverage. It's
overwhelmingly the leader's OWN government apparatus writing about
itself in the third person:
  - press_summary_of_speech (Ukraine, Slovenia, Latvia, Italy): the
    leader's own press office recapping a speech ("This was announced
    by Prime Minister X...").
  - wire_announcement (Kenya, China, others): Kenya's is scraped from
    president.go.ke (the presidency's own site); China's is Xinhua /
    People's Daily (state media, not independent press).
  - interview (8 rows total, project-wide): genuinely independent in a
    few cases (Kenya's 3 CNN transcripts -- Amanpour, One World) but
    each is a FULL SHOW transcript bundling his segment with unrelated
    news (Singapore Airlines, an AI lawsuit, etc.), not isolated to his
    portion -- and too few rows (3) to model anything from regardless.

The one genuine, usable exception: 36 of Mexico's 609 `press_conference`
rows (the "Stenographic Version: Press Conference" transcripts) preserve
the literal reporter QUESTION: ... / PRESIDENT OF MEXICO: ... exchange,
unlike the other 573 which only kept her remarks (per Ginette's own
expectation that questions were generally stripped in scraping). This
script extracts those questions and prints a quick frequency/keyword
read -- not NMF (125 extracted fragments, well under the 30-doc floor
once filler is dropped, and they're one-liners, not full documents, so
NMF's document-level topic model doesn't fit this shape of data anyway).

Usage: python extract_media_coverage.py --input data/part1/master_part1_working.csv --out data/part1/mexico_presser_questions.csv
"""
import argparse
import re

import pandas as pd

Q_BLOCK_RE = re.compile(r"QUESTION:|^\s*(Q:|Reporter:|JOURNALIST:)", re.I | re.M)
Q_EXTRACT_RE = re.compile(r"QUESTION:\s*(.+?)(?=PRESIDENT OF MEXICO|$)", re.S)
FILLER_RE = re.compile(
    r"^\(inaudible\)$|^thank you,?\s*(madam president)?\.?$|^good morning\.?$|"
    r"^that'?s all\.?.*$|^yes,?.*in fact\.?$",
    re.I,
)


def extract_questions(df: pd.DataFrame) -> pd.DataFrame:
    mx = df[(df.country == "Mexico") & (df.doc_type_audit == "press_conference")]
    has_q = mx[mx.full_text.str.contains(Q_BLOCK_RE, na=False, regex=True)]

    rows = []
    for _, r in has_q.iterrows():
        for m in Q_EXTRACT_RE.finditer(r["full_text"]):
            q = re.sub(r"\s+", " ", m.group(1)).strip()
            if len(q) < 10 or len(q) > 500:
                continue
            if FILLER_RE.match(q):
                continue
            rows.append({"speech_id": r["speech_id"], "date": r["date"], "question": q})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    df = pd.read_csv(args.input, dtype=str, keep_default_na=False, low_memory=False)
    q_df = extract_questions(df)
    q_df.to_csv(args.out, index=False, encoding="utf-8")
    print(f"{len(q_df)} substantive reporter questions extracted (filler dropped) -> {args.out}")


if __name__ == "__main__":
    main()
