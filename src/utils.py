"""
Shared utilities for the Speech Gender Gap scraper project.

This module holds code that EVERY country-specific scraper will reuse:
- the Speech data record (the common schema all scraped speeches follow)
- a polite HTTP GET function with retries
- text-cleaning and date-parsing helpers
- a CSV writer

Keeping this in one place means we write "how to fetch a page politely"
or "how to clean messy text" exactly once, instead of copy-pasting it
into every country's scraper file.
"""

import dataclasses
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ResearchSpeechScraper/1.0; "
        "+for academic gender-and-discourse research)"
    )
}

REQUEST_DELAY_SECONDS = 1.5
REQUEST_TIMEOUT = 20
MAX_RETRIES = 3


@dataclasses.dataclass
class Speech:
    """The common schema every scraped speech gets normalized into,
    regardless of which country/site it came from."""
    country: str
    leader: str
    role: str
    date: Optional[str]      # ISO YYYY-MM-DD if parseable, else None
    title: str
    full_text: str
    language: str
    source_url: str
    likely_speech: str       # "yes" / "maybe" / "no" -- heuristic, not ground truth
    notes: str = ""


def get(url: str) -> Optional[requests.Response]:
    """GET a URL with retries and a polite delay between requests."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            time.sleep(REQUEST_DELAY_SECONDS)
            if resp.status_code == 200:
                return resp
            print(f"  [warn] {url} returned status {resp.status_code} (attempt {attempt})")
        except requests.RequestException as e:
            print(f"  [warn] {url} request failed: {e} (attempt {attempt})")
        time.sleep(REQUEST_DELAY_SECONDS * attempt)
    print(f"  [error] giving up on {url}")
    return None


def soupify(resp: requests.Response) -> BeautifulSoup:
    return BeautifulSoup(resp.text, "html.parser")


def clean_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

import csv
import os


def write_csv(speeches: list, out_path: str):
    """Append a list of Speech records to a CSV file, writing headers only if new."""
    fieldnames = [f.name for f in dataclasses.fields(Speech)]
    write_header = not os.path.exists(out_path)
    with open(out_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for s in speeches:
            writer.writerow(dataclasses.asdict(s))
    print(f"  -> wrote {len(speeches)} rows to {out_path}")