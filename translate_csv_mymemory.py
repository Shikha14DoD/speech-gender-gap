"""
Same job as translate_csv.py (adds full_text_en / title_en columns) but
calls MyMemory directly instead of trying Google first.

Use this when Google's free endpoint is visibly rate-limited (every chunk
burning through translate_helper.py's 6 retries + backoff before falling
back) -- this session hit that on both Tanzania (Swahili) and Brazil
(Portuguese) after enough cumulative volume in one day. Skipping straight to
MyMemory avoids wasting ~2-3 minutes per chunk on doomed Google retries.

Resumable: skips rows where both full_text_en and title_en are already
filled (matches translate_csv.py's behavior), so it can pick up a
translate_csv.py run that was interrupted partway.

Usage:
    python translate_csv_mymemory.py --input data/processed/brazil.csv --language pt-BR
"""
import argparse
import time

import pandas as pd
from deep_translator import MyMemoryTranslator

import src.translate_helper as th


def translate_mymemory(text: str, source: str) -> str:
    if not text or not text.strip():
        return ""
    chunks = th._chunk_text(text, limit=450)
    out = []
    for i, chunk in enumerate(chunks):
        pieces = th._hard_split(chunk, 490)
        done = None
        last = None
        for attempt in range(5):
            try:
                done = " ".join(MyMemoryTranslator(source=source, target="en-GB").translate(p)
                                for p in pieces)
                break
            except Exception as e:
                last = e
                time.sleep(6 * (attempt + 1))
        out.append(done if done is not None else f"[TRANSLATION FAILED FOR THIS SECTION: {last}]")
        if i % 10 == 0:
            print(f"    chunk {i + 1}/{len(chunks)}", flush=True)
        time.sleep(1.5)
    return "\n\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--language", required=True,
                    help="MyMemory source code, e.g. pt-BR, sw-KE, si-LK")
    args = ap.parse_args()

    df = pd.read_csv(args.input, dtype=str, keep_default_na=False)
    if "full_text_en" not in df.columns:
        df["full_text_en"] = ""
    if "title_en" not in df.columns:
        df["title_en"] = ""

    todo = df.index[~(df["full_text_en"].str.len().gt(0) & df["title_en"].str.len().gt(0))].tolist()
    print(f"{len(todo)} rows left", flush=True)

    for n, i in enumerate(todo, 1):
        print(f"[{n}/{len(todo)}] {df.at[i, 'title'][:60]}", flush=True)
        if not df.at[i, "title_en"].strip():
            df.at[i, "title_en"] = translate_mymemory(str(df.at[i, "title"]), args.language) or df.at[i, "title"]
        if not df.at[i, "full_text_en"].strip():
            df.at[i, "full_text_en"] = translate_mymemory(str(df.at[i, "full_text"]), args.language)
        df.to_csv(args.input, index=False, encoding="utf-8")

    still_bad = df["full_text_en"].str.contains(r"\[TRANSLATION FAILED", na=False, regex=True).sum()
    print(f"\nDONE. rows with failed sections: {still_bad}", flush=True)


if __name__ == "__main__":
    main()
