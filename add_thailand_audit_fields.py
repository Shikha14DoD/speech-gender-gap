"""
Adds doc_type_audit / audience_scope / audience_reach and fills delivered_venue
in data/processed/thailand_FINAL.csv (audit_vocab.py = master dictionary values).

All rows are prepared addresses/remarks at named international occasions
(BIMSTEC, UNESCAP, ASEAN, Nikkei Forum, Summit for Democracy, UN General
Assembly) or a joint statement -> international audience, except the German
Association reception, which is a domestic-hosted bilateral event and
therefore sectoral_stakeholder.
Usage: python add_thailand_audit_fields.py   (safe to re-run)
"""
import re
import pandas as pd

from audit_vocab import add_audit_reach, validate

CSV = "data/processed/thailand_FINAL.csv"

_JOINT = re.compile(r"^joint statement", re.I)
_VENUES = [
    (r"unescap", "Bangkok, Thailand"), (r"bimstec", "Bangkok, Thailand"),
    (r"summit for democracy", "Seoul, South Korea"),
    (r"nikkei forum", "Tokyo, Japan"),
    (r"asean future forum", "Hanoi, Vietnam"),
    (r"asec", "Jakarta, Indonesia"),
    (r"general debate.*81st|general debate.*united nations", "New York, USA"),
    (r"german association", "Bangkok, Thailand"),
]


def doc_type(title):
    return "joint_statement" if _JOINT.search(title) else "delivered_speech"


def scope(title):
    if re.search(r"german association", title, re.I):
        return "sectoral_stakeholder"
    return "international"


def venue(title):
    for pat, name in _VENUES:
        if re.search(pat, title, re.I):
            return name
    return ""


def main():
    d = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    d["doc_type_audit"] = d["title"].map(doc_type)
    d["audience_scope"] = d["title"].map(scope)
    # always recompute (not "v or venue(t)") -- this script is delivered_venue's
    # only source for this file, so a stale wrong value must not survive a rerun
    d["delivered_venue"] = d["title"].map(venue)
    d = add_audit_reach(d)
    validate(d)
    d.to_csv(CSV, index=False, encoding="utf-8")
    print(d["doc_type_audit"].value_counts().to_string())
    print(d["audience_scope"].value_counts().to_string())
    print(f"venue filled: {(d['delivered_venue']!='').sum()}/{len(d)}")
    for _, r in d.sort_values("date").iterrows():
        print(f"{r['date']} | {r['leader'][:20]:20} | {r['doc_type_audit'][:12]:12} | {r['delivered_venue'][:20]:20} | {r['title'][:55]}")


if __name__ == "__main__":
    main()
