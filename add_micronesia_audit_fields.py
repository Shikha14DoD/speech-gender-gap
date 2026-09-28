"""
Adds doc_type_audit / audience_scope / audience_reach and fills delivered_venue
in data/processed/micronesia_FINAL.csv (audit_vocab.py = master dictionary values).

Every row here is a prepared address at an international body (the UN General
Assembly or a Pacific Islands Forum leaders' event) -> all international,
delivered_speech.
Usage: python add_micronesia_audit_fields.py   (safe to re-run)
"""
import re
import pandas as pd

from audit_vocab import add_audit_reach, validate

CSV = "data/processed/micronesia_FINAL.csv"

_VENUES = [
    (r"united nations|general debate|summit of the future|aosis|existential threat|sea-level rise",
     "New York, USA"),
    (r"small island states leaders meeting", "Koror, Palau"),
]


def venue(title):
    for pat, name in _VENUES:
        if re.search(pat, title, re.I):
            return name
    return ""


def main():
    d = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    d["doc_type_audit"] = "delivered_speech"
    d["audience_scope"] = "international"
    d["delivered_venue"] = [v or venue(t) for v, t in zip(d["delivered_venue"], d["title"])]
    d = add_audit_reach(d)
    validate(d)
    d.to_csv(CSV, index=False, encoding="utf-8")
    print(d["audience_scope"].value_counts().to_string())
    print(f"venue filled: {(d['delivered_venue']!='').sum()}/{len(d)}")
    for _, r in d.sort_values("date").iterrows():
        print(f"{r['date']} | {r['delivered_venue'][:20]:20} | {r['title'][:70]}")


if __name__ == "__main__":
    main()
