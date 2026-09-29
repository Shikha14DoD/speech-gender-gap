"""
Translate the untranslated rows of a country CSV (full_text_en/title_en blank)
using the DeepL API Free tier. DeepL's own request limit is generous (500k
chars/month, ~30 requests/sec) and its per-request text limit is 128 KiB, so
unlike the free Google/MyMemory route this needs no chunk cache or cooldowns
-- one request per row is enough for any speech in this project.

Reads the key from .env (DEEPL_API_KEY=...), which is gitignored -- never
pass it on the command line where it could end up in shell history.

Usage: python translate_deepl.py --input data/processed/sweden.csv --source SV
"""
import argparse
import csv
import os
import sys
import time

import requests

API = "https://api-free.deepl.com/v2/translate"


def _load_key() -> str:
    if os.path.exists(".env"):
        for line in open(".env", encoding="utf-8"):
            if line.startswith("DEEPL_API_KEY="):
                return line.strip().split("=", 1)[1]
    key = os.environ.get("DEEPL_API_KEY")
    if key:
        return key
    sys.exit("No DEEPL_API_KEY found in .env or the environment.")


MAX_CHUNK_CHARS = 1500   # DeepL Free returned "413 Payload too large" on
                        # Thai-script texts well under its documented 128 KiB
                        # limit (Thai has no spaces, so a "long text" is also
                        # very information-dense) -- split defensively small


def _translate_one(key: str, text: str, source: str, max_retries: int = 3) -> str:
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(API, headers={"Authorization": f"DeepL-Auth-Key {key}"},
                                 data={"text": text, "source_lang": source, "target_lang": "EN-US"},
                                 timeout=60)
        except requests.RequestException as e:
            print(f"    [warn] request failed: {e} (attempt {attempt})")
            time.sleep(5 * attempt)
            continue
        if resp.status_code == 200:
            return resp.json()["translations"][0]["text"]
        if resp.status_code == 429:
            print(f"    [warn] rate limited, waiting 30s (attempt {attempt})")
            time.sleep(30)
            continue
        if resp.status_code == 413 and len(text) > 200:
            # `x or y or z` treats a real split point of 0 as falsy and skips
            # it -- Thai script often has no spaces at all, so rfind()
            # legitimately returns 0 or -1 here; fall through explicitly
            # instead, or this can loop splitting off an empty first half
            mid = len(text) // 2
            split = text.rfind("\n", 0, mid)
            if split <= 0:
                split = text.rfind(" ", 0, mid)
            if split <= 0:
                split = mid
            print(f"    [warn] 413 on {len(text)} chars, splitting at {split}")
            return (_translate_one(key, text[:split], source, max_retries) + " "
                    + _translate_one(key, text[split:], source, max_retries))
        raise RuntimeError(f"DeepL {resp.status_code}: {resp.text[:200]}")
    raise RuntimeError(f"gave up after {max_retries} attempts")


def translate(key: str, text: str, source: str, max_retries: int = 3) -> str:
    """Split into paragraph-sized chunks before sending -- DeepL Free 413'd
    on some long Thai-script texts well under its documented size limit."""
    if len(text) <= MAX_CHUNK_CHARS:
        return _translate_one(key, text, source, max_retries)
    paras = text.split("\n")
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 1 > MAX_CHUNK_CHARS and cur:
            chunks.append(cur)
            cur = ""
        cur = (cur + "\n" + p) if cur else p
    if cur:
        chunks.append(cur)
    return "\n".join(_translate_one(key, c, source, max_retries) for c in chunks if c.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--source", required=True, help="DeepL source language code, e.g. SV")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    key = _load_key()

    with open(args.input, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

    todo = [r for r in rows if not r.get("full_text_en", "").strip()]
    print(f"{len(rows)} rows total; {len(todo)} need translation")
    if args.limit:
        todo = todo[: args.limit]

    done = 0
    for row in todo:
        try:
            row["title_en"] = translate(key, row["title"], args.source)
            row["full_text_en"] = translate(key, row["full_text"], args.source)
            done += 1
            print(f"  ok {row['date']} {row['title'][:50]!r} -> {row['title_en'][:50]!r}")
        except Exception as e:
            print(f"  [error] {row['date']} {row['title'][:50]!r}: {e}")
            continue
        # write after every row, so a crash loses no completed work
        with open(args.input, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            w.writeheader()
            w.writerows(rows)

    print(f"DONE: {done}/{len(todo)} rows translated this run")


if __name__ == "__main__":
    main()
