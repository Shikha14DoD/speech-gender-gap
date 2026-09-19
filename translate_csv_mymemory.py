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


def translate_mymemory(text: str, source: str):
    """-> (translated_text, n_failed_chunks, n_chunks). Failures are counted
    from what actually came back, not from loop progress -- an earlier
    version only printed iteration counts and hid a total failure wall."""
    if not text or not text.strip():
        return "", 0, 0
    chunks = th._chunk_text(text, limit=450)
    out = []
    n_failed = 0
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
        if done is None:
            n_failed += 1
            out.append(f"[TRANSLATION FAILED FOR THIS SECTION: {last}]")
        else:
            out.append(done)
        if i % 10 == 0:
            print(f"    chunk {i + 1}/{len(chunks)}  (failed so far: {n_failed})", flush=True)
        # fail fast: if the opening chunks ALL failed the service is down --
        # stop now instead of burning hours on retries
        if i >= 4 and n_failed == i + 1:
            raise RuntimeError(f"first {i + 1} chunks ALL failed ({last}) -- service down, aborting")
        time.sleep(1.5)
    return "\n\n".join(out), n_failed, len(chunks)


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
    total_failed_rows = 0

    for n, i in enumerate(todo, 1):
        print(f"[{n}/{len(todo)}] {df.at[i, 'title'][:60]}", flush=True)
        if not df.at[i, "title_en"].strip():
            t_en, t_fail, _ = translate_mymemory(str(df.at[i, "title"]), args.language)
            df.at[i, "title_en"] = t_en if (t_en and not t_fail) else df.at[i, "title"]
        if not df.at[i, "full_text_en"].strip():
            ft_en, n_fail, n_chunks = translate_mymemory(str(df.at[i, "full_text"]), args.language)
            if n_fail:
                # do NOT save a partly-failed row as "done" -- leave it
                # blank so a re-run retries it instead of shipping markers
                print(f"  !! row {n} had {n_fail}/{n_chunks} failed chunks -- left blank for retry", flush=True)
                total_failed_rows += 1
                df.at[i, "title_en"] = ""
            else:
                df.at[i, "full_text_en"] = ft_en
                print(f"  ok: {n_chunks} chunks, 0 failed", flush=True)
        df.to_csv(args.input, index=False, encoding="utf-8")

    n_ok = int((df["full_text_en"].str.len() > 0).sum())
    print(f"\nDONE. rows fully translated: {n_ok}/{len(df)}; "
          f"rows left blank after failures (re-run to retry): {total_failed_rows}", flush=True)


if __name__ == "__main__":
    main()
