"""
Adds doc_type_audit / audience_scope / audience_reach and fills delivered_venue
in data/processed/latvia_FINAL.csv (audit_vocab.py = master dictionary values).

All rows are press-office write-ups (mk.gov.lv has no dedicated speech archive
for this Prime Minister yet) -> press_summary_of_speech, except a plain
government-formation announcement -> wire_announcement. Any future page whose
title starts "Address by"/"Speech by" is delivered_speech (see scraper_latvia.py).
Foreign trips/summits -> international; domestic announcements -> domestic_public.
Usage: python add_latvia_audit_fields.py   (safe to re-run)
"""
import re
import pandas as pd

from audit_vocab import add_audit_reach, validate

CSV = "data/processed/latvia_FINAL.csv"

_ANNOUNCEMENT = re.compile(r"assumes office|hands over the powers of office", re.I)
_INTERNATIONAL = re.compile(
    r"ukraine|paris|riga conference|arctic|lithuania|european council|nato|sanctions|"
    r"special envoy|state award", re.I)

_VENUES = [
    (r"riga conference", "Riga, Latvia"),
    (r"arctic", "Rovaniemi, Finland"),
    (r"paris|visiting ukraine|ukraine.{0,15}state award", "Kyiv, Ukraine"),
]


def doc_type(title):
    if title.lower().startswith(("address by", "speech by")):
        return "delivered_speech"
    if _ANNOUNCEMENT.search(title):
        return "wire_announcement"
    return "press_summary_of_speech"


def scope(title):
    return "international" if _INTERNATIONAL.search(title) else "domestic_public"


def venue(title):
    for pat, name in _VENUES:
        if re.search(pat, title, re.I):
            return name
    return "Riga, Latvia" if scope(title) == "domestic_public" else ""


def main():
    d = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    d["doc_type_audit"] = d["title"].map(doc_type)
    d["audience_scope"] = d["title"].map(scope)
    d["delivered_venue"] = d["title"].map(venue)
    d = add_audit_reach(d)
    validate(d)
    d.to_csv(CSV, index=False, encoding="utf-8")
    print(d["doc_type_audit"].value_counts().to_string())
    print(d["audience_scope"].value_counts().to_string())
    for _, r in d.sort_values("date").iterrows():
        print(f"{r['date']} | {r['doc_type_audit'][:12]:12} | {r['audience_scope'][:12]:12} | {r['delivered_venue']:16} | {r['title'][:60]}")


if __name__ == "__main__":
    main()
