"""
Resilient CSV translator for when the free translation services are flaky.

Same output as translate_csv.py (adds full_text_en / title_en columns) but
built for a long, slow, unattended run against rate-limited free engines:

  * CHUNK CACHE on disk (translate_cache_<lang>.json next to the CSV). Every
    chunk that translates successfully is kept forever, so a crash, a
    session ending, or a service outage never throws work away, and a re-run
    only translates what's still missing.
  * BOTH ENGINES per chunk: MyMemory first, then Google. Either one working
    is enough.
  * SANITY CHECKS: an engine's quota-warning text ("MYMEMORY WARNING: YOU
    USED ALL AVAILABLE FREE TRANSLATIONS...") sometimes comes back as if it
    were a translation. Those, empty output, echoed input and absurd length
    ratios are all treated as failures, never saved.
  * COOLDOWNS instead of crashing: after a few consecutive failures it sleeps
    (growing up to an hour, or the engine's own "next available in N hours"
    hint) and carries on from the same chunk. Gives up only after many
    cooldowns with zero progress.
  * A row is written to the CSV only once EVERY chunk of it is translated --
    a partly-failed speech is never saved as done.
  * Progress lines report real cached-chunk counts, not loop iterations.

Usage:
    python translate_csv_resilient.py --input data/processed/brazil.csv --language pt-BR

Only runs while the machine/session is alive; just start it again to resume.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time

import pandas as pd
from deep_translator import GoogleTranslator, MyMemoryTranslator

import src.translate_helper as th

CHUNK_LIMIT = 450       # keeps each chunk under MyMemory's 500-char cap

_BAD_MARKERS = re.compile(
    r"MYMEMORY WARNING|YOU USED ALL AVAILABLE|QUERY LENGTH LIMIT|"
    r"INVALID LANGUAGE PAIR|DISTINCT LANGUAGES|TOO MANY REQUESTS", re.I)
_WAIT_HINT = re.compile(r"NEXT AVAILABLE IN\s+(\d+)\s+HOURS?\s*(\d+)?\s*(?:MINUTES?)?", re.I)


class GiveUp(Exception):
    pass


class Cache:
    def __init__(self, path):
        self.path = path
        self.d = {}
        self.dirty = 0
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                self.d = json.load(fh)

    @staticmethod
    def key(chunk, lang):
        return hashlib.sha1(f"{lang}\0{chunk}".encode("utf-8")).hexdigest()

    def get(self, k):
        return self.d.get(k)

    def put(self, k, v):
        self.d[k] = v
        self.dirty += 1
        if self.dirty >= 10:
            self.save()

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.d, fh, ensure_ascii=False)
        os.replace(tmp, self.path)
        self.dirty = 0


def looks_bad(out, chunk):
    if not out or not out.strip():
        return True
    if _BAD_MARKERS.search(out):
        return True
    if len(chunk) >= 40:
        ratio = len(out) / len(chunk)
        if ratio < 0.3 or ratio > 3.5:
            return True
        if out.strip() == chunk.strip():        # engine echoed the input
            return True
    return False


def try_engines(chunk, mm_source, g_source):
    """-> (translation | None, wait_hint_seconds)"""
    hint = 0
    for engine in ("mymemory", "google"):
        try:
            if engine == "mymemory":
                pieces = th._hard_split(chunk, 490)
                out = " ".join(MyMemoryTranslator(source=mm_source, target="en-GB").translate(p)
                               for p in pieces)
            else:
                out = GoogleTranslator(source=g_source, target="en").translate(chunk)
        except Exception as e:
            out = str(e)
            m = _WAIT_HINT.search(out)
            if m:
                hint = max(hint, int(m.group(1)) * 3600 + int(m.group(2) or 0) * 60)
            continue
        m = _WAIT_HINT.search(out or "")
        if m:
            hint = max(hint, int(m.group(1)) * 3600 + int(m.group(2) or 0) * 60)
        if not looks_bad(out, chunk):
            return out, 0
    return None, hint


class Runner:
    def __init__(self, cache, mm_source, g_source, delay, cooldown, max_cooldowns):
        self.cache, self.mm, self.g = cache, mm_source, g_source
        self.delay, self.base_cooldown = delay, cooldown
        self.cooldown = cooldown
        self.max_cooldowns = max_cooldowns
        self.consec_fail = 0
        self.idle_cooldowns = 0
        self.fresh = 0          # chunks translated this run

    def resolve(self, chunk):
        k = Cache.key(chunk, self.mm)
        hit = self.cache.get(k)
        if hit is not None:
            return hit
        while True:
            out, hint = try_engines(chunk, self.mm, self.g)
            if out is not None:
                self.cache.put(k, out)
                self.fresh += 1
                self.consec_fail = 0
                self.idle_cooldowns = 0
                self.cooldown = self.base_cooldown
                time.sleep(self.delay)
                return out
            self.consec_fail += 1
            if self.consec_fail < 4:
                time.sleep(20)
                continue
            wait = min(max(self.cooldown, hint + 120), 3 * 3600)
            print(f"COOLDOWN {wait // 60} min (4 consecutive failures; "
                  f"idle cooldowns {self.idle_cooldowns + 1}/{self.max_cooldowns})",
                  flush=True)
            self.cache.save()
            time.sleep(wait)
            self.idle_cooldowns += 1
            self.consec_fail = 0
            self.cooldown = min(int(self.cooldown * 1.5), 3600)
            if self.idle_cooldowns >= self.max_cooldowns:
                raise GiveUp(f"{self.max_cooldowns} cooldowns in a row with no progress")


def save_csv(df, path):
    tmp = path + ".tmp"
    df.to_csv(tmp, index=False, encoding="utf-8")
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--language", required=True,
                    help="MyMemory-style source code, e.g. pt-BR, sw-KE, si-LK")
    ap.add_argument("--delay", type=float, default=4.0, help="seconds between chunks")
    ap.add_argument("--cooldown", type=int, default=600, help="initial cooldown, seconds")
    ap.add_argument("--max-cooldowns", type=int, default=30)
    args = ap.parse_args()

    g_source = args.language.split("-")[0]
    df = pd.read_csv(args.input, dtype=str, keep_default_na=False)
    for col in ("full_text_en", "title_en"):
        if col not in df.columns:
            df[col] = ""

    cache_path = os.path.join(os.path.dirname(args.input) or ".",
                              f"translate_cache_{args.language}.json")
    cache = Cache(cache_path)
    runner = Runner(cache, args.language, g_source, args.delay, args.cooldown,
                    args.max_cooldowns)

    todo = df.index[df["full_text_en"].str.strip().eq("")].tolist()
    plan = {i: (th._chunk_text(str(df.at[i, "title"]), CHUNK_LIMIT),
                th._chunk_text(str(df.at[i, "full_text"]), CHUNK_LIMIT)) for i in todo}
    all_chunks = [c for i in todo for c in plan[i][0] + plan[i][1]]
    total = len(all_chunks)
    cached = sum(1 for c in all_chunks if cache.get(Cache.key(c, args.language)) is not None)
    print(f"{len(todo)} rows to translate; {total} chunks total, {cached} already cached "
          f"({total - cached} to go)", flush=True)

    try:
        for n, i in enumerate(todo, 1):
            t_chunks, f_chunks = plan[i]
            title_en = "\n\n".join(runner.resolve(c) for c in t_chunks)
            text_en = "\n\n".join(runner.resolve(c) for c in f_chunks)
            df.at[i, "title_en"] = title_en
            df.at[i, "full_text_en"] = text_en
            save_csv(df, args.input)
            cache.save()
            print(f"  ok row {n}/{len(todo)} ({len(f_chunks)} chunks)", flush=True)
            if n % 10 == 0 or n == len(todo):
                done_chunks = sum(1 for c in all_chunks
                                  if cache.get(Cache.key(c, args.language)) is not None)
                print(f"PROGRESS rows_done={n}/{len(todo)} "
                      f"chunks_cached={done_chunks}/{total} "
                      f"fresh_this_run={runner.fresh}", flush=True)
    except GiveUp as e:
        cache.save()
        n_ok = int((df["full_text_en"].str.strip() != "").sum())
        print(f"GAVE UP: {e}. {n_ok}/{len(df)} rows translated; cache kept "
              f"({len(cache.d)} chunks) -- re-run to resume.", flush=True)
        sys.exit(2)

    cache.save()
    n_ok = int((df["full_text_en"].str.strip() != "").sum())
    print(f"DONE. rows fully translated: {n_ok}/{len(df)}", flush=True)


if __name__ == "__main__":
    main()
