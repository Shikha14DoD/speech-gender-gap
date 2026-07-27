"""
One-off verification: compares our scraped Italy CSV against the list of
URLs manually copied from governo.it's own official "interventi-en"
(interventions/speeches) listing page.

NOTE: the official listing represents the government's own curated
definition of "interventions" -- it will likely be SMALLER than our
scraped set, since our scraper draws from the broader /en/articolo/
article namespace and uses keyword heuristics to guess at speech-like
content. Rows in our CSV but NOT on the official list aren't necessarily
wrong -- they need a manual look to judge whether they're legitimately
speech-like content the official list just doesn't include, or false
positives that slipped through our filters.
"""

import re
import pandas as pd

# Slugs manually copied from governo.it/en/interventi-en (the official,
# curated interventions/speeches listing), normalized (no domain, no
# trailing numeric ID, lowercase).
official_slugs_raw = """
https://www.governo.it/en/articolo/president-meloni-s-press-statement-prime-minister-montenegro-portugal/32377
https://www.governo.it/en/articolo/president-meloni-s-address-police-officers-involved-special-local-prevention-and-patrol
https://www.governo.it/en/articolo/new-draft-law-security-president-meloni-s-video-message/32357
https://www.governo.it/en/articolo/president-meloni-addresses-meeting-provincial-committee-public-order-and-security
https://www.governo.it/en/articolo/president-meloni-s-press-conference-introduction-2026-nato-summit/32303
""".strip().splitlines()  # (truncated sample -- full list loaded from manual_list.txt if present)

import os

def normalize(u):
    u = u.replace("https://www.governo.it", "").replace("https://governo.it", "")
    u = u.rstrip("/")
    u = re.sub(r"/\d+$", "", u)
    return u.lower()

# Load the full manual list from a sibling file if available, else use the
# short inline sample above.
manual_path = os.path.join(os.path.dirname(__file__), "italy_manual_list.txt")
if os.path.exists(manual_path):
    with open(manual_path) as f:
        official_slugs_raw = [l.strip() for l in f if l.strip()]

official_slugs = set(normalize(u) for u in official_slugs_raw)
print(f"Official 'interventi-en' list: {len(official_slugs)} unique entries")

df = pd.read_csv("data/processed/italy.csv")
our_slugs_map = {}
for url in df["source_url"]:
    our_slugs_map[normalize(url)] = url

our_slugs = set(our_slugs_map.keys())
print(f"Our CSV: {len(df)} rows, {len(our_slugs)} unique normalized URLs")

on_official_not_ours = official_slugs - our_slugs
on_ours_not_official = our_slugs - official_slugs
overlap = official_slugs & our_slugs

print(f"\nOverlap (on both lists): {len(overlap)}")
print(f"On official list but MISSING from our CSV: {len(on_official_not_ours)}")
for s in sorted(on_official_not_ours):
    print(" -", s)

print(f"\nIn our CSV but NOT on official list: {len(on_ours_not_official)}")
print("(This is expected to be a large number -- these need manual review,")
print(" not automatic removal. Showing first 20 as a sample:)")
for s in sorted(on_ours_not_official)[:20]:
    print(" -", s)