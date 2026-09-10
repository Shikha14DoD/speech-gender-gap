"""
Post-process data/processed/srilanka.csv (the text route).

The Presidential Secretariat / PMD article pages append two kinds of
non-speech boilerplate that the body extractor picked up:
  1. a fixed ~350-char "About the media department" blurb ("The media
     department works as a source of information ... Identify the
     fallacies and reveal the truth.")
  2. a "Related Posts" strip -- several "<truncated headline>...  Read
     More" items.
They also repeat "Published on: <date>  <title>" at the top of the body.

This trims all of that. Also fixed at source in scraper_srilanka.py for
future runs.

Usage: python clean_srilanka.py
"""
import re
import pandas as pd

CSV = "data/processed/srilanka.csv"

BLURB = re.compile(
    r"\s*\n\s*(Facebook\s*\n\s*Twitter|Mission\s*\n\s*The Presidential Media Division"
    r"|The Presidential Media Division is fully responsible for socializing"
    r"|The media department works as a source of information"
    r"|Follow us on|Share this:|Share on Facebook).*$",
    re.I | re.S)
RELATED = re.compile(
    r"\s*\n\s*(Related News|Related Posts|Latest News|Recent (News|Posts)|More News|"
    r"You may also like|Related Articles)\s*\n.*$", re.I | re.S)
READMORE = re.compile(r"\s*\n[^\n]{0,160}?[…\.]{1,3}\s+[^\n]{0,180}?Read More.*$",
                      re.I | re.S)
LEAD = re.compile(r"^\s*Published on:\s*[A-Za-z]+ \d{1,2},? \d{4}\s*", re.I)


def clean(txt: str) -> str:
    if not isinstance(txt, str):
        return txt
    txt = BLURB.sub("", txt)
    txt = RELATED.sub("", txt)
    for _ in range(6):
        new = READMORE.sub("", txt)
        if new == txt:
            break
        txt = new
    txt = re.sub(r"\s*Read More\s*$", "", txt)
    txt = LEAD.sub("", txt).strip()
    return txt


def main():
    df = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    before = df["full_text"].str.len().sum()
    df["full_text"] = df["full_text"].map(clean)
    df = df[df["full_text"].str.len() >= 300].reset_index(drop=True)
    df.to_csv(CSV, index=False, encoding="utf-8")
    after = df["full_text"].str.len().sum()
    print(f"rows: {len(df)}  chars {before} -> {after}")
    still = df["full_text"].str.contains(
        "media department works|Read More|Identify the fallacies", na=False).sum()
    print(f"rows still containing boilerplate markers: {still}")
    print("shortest:", df["full_text"].str.len().min(),
          "| median:", int(df["full_text"].str.len().median()))


if __name__ == "__main__":
    main()
