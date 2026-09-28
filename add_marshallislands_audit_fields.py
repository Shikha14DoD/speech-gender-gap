"""
Adds doc_type_audit / audience_scope / audience_reach and fills delivered_venue
in data/processed/marshallislands_FINAL.csv (audit_vocab.py = master dictionary values).

Only 2 rows: the UNGA statement (international) and the opening remarks to the
Marshall Islands Mayors Association conference (a domestic stakeholder body).
Usage: python add_marshallislands_audit_fields.py   (safe to re-run)
"""
import pandas as pd

from audit_vocab import add_audit_reach, validate

CSV = "data/processed/marshallislands_FINAL.csv"


def scope(title):
    return "international" if "General Assembly" in title else "sectoral_stakeholder"


def venue(title):
    return "New York, USA" if "General Assembly" in title else "Majuro, Marshall Islands"


def main():
    d = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    d["doc_type_audit"] = "delivered_speech"
    d["audience_scope"] = d["title"].map(scope)
    d["delivered_venue"] = d["title"].map(venue)
    d = add_audit_reach(d)
    validate(d)
    d.to_csv(CSV, index=False, encoding="utf-8")
    print(d["audience_scope"].value_counts().to_string())
    for _, r in d.iterrows():
        print(r["date"], "|", r["delivered_venue"], "|", r["title"][:70])


if __name__ == "__main__":
    main()
