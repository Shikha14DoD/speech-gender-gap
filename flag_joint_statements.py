"""
Adds an `is_joint_multilateral` boolean column to a scraped speech CSV,
flagging entries whose title suggests a joint/multilateral document
(G7/G20 communiques, joint statements with other leaders) rather than
the leader's own individual remarks -- so these can be filtered in or
out downstream as needed, per project methodology (retain all content
with classification columns, don't filter at scrape time).

Usage:
    python flag_joint_statements.py data/processed/canada_trudeau.csv
    python flag_joint_statements.py data/processed/canada_carney.csv
"""

import sys
import re
import pandas as pd

JOINT_KEYWORDS = [
    r"\bg7\b", r"\bg20\b", r"\bg8\b",
    r"joint statement", r"joint declaration", r"joint communiqu",
    r"leaders[’']? statement", r"leaders[’']? declaration",
    r"joint statement by", r"statement by the leaders",
]
pattern = re.compile("|".join(JOINT_KEYWORDS), re.IGNORECASE)

path = sys.argv[1]
df = pd.read_csv(path)

df["is_joint_multilateral"] = df["title"].astype(str).str.contains(pattern, na=False)

flagged = df["is_joint_multilateral"].sum()
print(f"{path}")
print(f"  Flagged as joint/multilateral: {flagged} / {len(df)}")
if flagged:
    print("  Examples:")
    for t in df[df["is_joint_multilateral"]]["title"].head(5):
        print("   -", t)

df.to_csv(path, index=False)