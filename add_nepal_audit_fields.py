"""
Adds doc_type_audit / audience_scope / audience_reach and fills delivered_venue
in data/processed/nepal_FINAL.csv (audit_vocab.py = the master dictionary's values).

Every row here comes from the Ministry of Foreign Affairs' statement pages, so
almost all are statements made at multilateral events abroad -> international.
Two exceptions, handled by rule:
  * Karki's briefing to the diplomatic corps in Kathmandu -> sectoral_stakeholder
    (same treatment as Tanzania's diplomatic-corps events).
  * the BIMSTEC Day item is a third-person Ministry press release summarising two
    messages (PM Shah and the Foreign Minister), not the PM's own words ->
    wire_announcement (dictionary: an item ABOUT the leader).
Usage: python add_nepal_audit_fields.py   (safe to re-run)
"""
import re
import pandas as pd

from audit_vocab import add_audit_reach, validate

CSV = "data/processed/nepal_FINAL.csv"

_PRESS_RELEASE = re.compile(r"bimstec day messages", re.I)
_DIPLOMATIC = re.compile(r"diplomatic corp", re.I)
_VENUES = [
    (r"bangkok", "Bangkok, Thailand"), (r"seville|sevilla", "Seville, Spain"),
    (r"awaza|third un conference on landlocked|third united nations conference on landlocked|lldc3|ministerial meeting on south-south",
     "Awaza, Turkmenistan"),
    (r"tianjin", "Tianjin, China"), (r"in kathmandu", "Kathmandu, Nepal"),
]


def doc_type(title, text):
    if _PRESS_RELEASE.search(title) or text.lstrip().lower().startswith("press release"):
        return "wire_announcement"
    return "delivered_speech"


def audience_scope(title):
    if _DIPLOMATIC.search(title):
        return "sectoral_stakeholder"
    return "international"


def venue(title):
    for pat, name in _VENUES:
        if re.search(pat, title, re.I):
            return name
    return ""


def main():
    d = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    d["doc_type_audit"] = [doc_type(t, x) for t, x in zip(d["title"], d["full_text"])]
    d["audience_scope"] = d["title"].map(audience_scope)
    d["delivered_venue"] = [v or venue(t) for v, t in zip(d["delivered_venue"], d["title"])]
    d = add_audit_reach(d)
    validate(d)
    d.to_csv(CSV, index=False, encoding="utf-8")
    print(d.groupby("leader").size().to_string())
    print(d["doc_type_audit"].value_counts().to_string())
    print(d["audience_scope"].value_counts().to_string())
    for _, r in d.sort_values("date").iterrows():
        print(f"{r['date']} | {r['leader'][:16]:16} | {r['doc_type_audit'][:12]:12} | {r['audience_scope'][:12]:12} | {r['delivered_venue']:20} | {r['title'][:50]}")


if __name__ == "__main__":
    main()
