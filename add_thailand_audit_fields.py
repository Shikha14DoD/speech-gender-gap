"""
Adds doc_type_audit / audience_scope / audience_reach and fills delivered_venue
in data/processed/thailand_FINAL.csv (audit_vocab.py = master dictionary values).
Runs on the MERGED text+video file (merge_thailand.py's output, finalized).

Text-route rows (mfa.go.th) are prepared addresses at named international
occasions -> international, except one domestic-hosted bilateral reception.
Video-route rows (the official @thaigovernment YouTube channel) cover a much
wider mix: UN/regional bodies and bilateral business forums (international),
domestic trade expos/galas/dinners hosted in Thailand for industry or
diplomatic audiences (sectoral_stakeholder), and a military/ceremonial
reception and a national symposium addressed to the domestic public
(domestic_public). Read title by title (see the listing this script prints)
rather than guessed from a couple of keywords.
Usage: python add_thailand_audit_fields.py   (safe to re-run)
"""
import re
import pandas as pd

from audit_vocab import add_audit_reach, validate

CSV = "data/processed/thailand_FINAL.csv"

_JOINT = re.compile(r"^joint statement", re.I)

_INTERNATIONAL = re.compile(
    r"unescap|bimstec|summit for democracy|nikkei forum|asean future forum|"
    r"\basec\b|general debate|general assembly|german association|"
    r"myanmar business forum|myanmar\b.{0,20}visit|joint statement|"
    r"russia.{0,3}asean business forum|indonesia.thailand business forum|"
    r"small-group discussions with representatives of the private sector|"
    r"uk government and private sector|united kingdom", re.I)

_SECTORAL = re.compile(
    r"cooperation expo|gala dinner|dinner talk|luncheon|foreign chambers of commerce|"
    r"mega halal|thailand.s offer to the world|gastech|"
    r"internet crime|global partnership|sustainability expo", re.I)

_DOMESTIC_PUBLIC = re.compile(
    r"air force|reception held in honor|national symposium|occupational|"
    r"opening ceremony.*(safety|national)", re.I)

# the joint statement's own text says Myanmar's president visited Thailand
# (not the reverse) -- both same-day Myanmar rows are in Bangkok, not
# Naypyidaw; confirmed by reading the actual body text, not guessed from the
# country name in the title (that mistake would have gone uncaught otherwise)
_VENUES = [
    (r"unescap", "Bangkok, Thailand"), (r"bimstec", "Bangkok, Thailand"),
    (r"summit for democracy", "Seoul, South Korea"),
    (r"nikkei forum", "Tokyo, Japan"),
    (r"asean future forum", "Hanoi, Vietnam"),
    (r"small-group discussions with representatives of the private sector", "New York, USA"),
    (r"\basec\b|indonesia.thailand business forum", "Jakarta, Indonesia"),
    (r"general debate.*81st|general debate.*united nations|"
     r"uk government and private sector|united kingdom", "New York, USA"),
    (r"german association|cooperation expo|gala dinner|foreign chambers of commerce|"
     r"mega halal|thailand.s offer to the world|gastech|internet crime|global partnership|"
     r"air force|reception held in honor|national symposium|occupational|82nd annual session|"
     r"sustainability expo|myanmar", "Bangkok, Thailand"),
    (r"russia.{0,3}asean business forum|dinner talk", "Bangkok, Thailand"),
]


def doc_type(title):
    return "joint_statement" if _JOINT.search(title) else "delivered_speech"


def scope(title, full_text=""):
    # the title alone is sometimes generic ("...at the Business Forum") --
    # the body's own opening line names the real event ("the Indonesia-
    # Thailand Business Forum"), so check both
    blob = title + " " + full_text[:400]
    if _SECTORAL.search(blob):
        return "sectoral_stakeholder"
    if _DOMESTIC_PUBLIC.search(blob):
        return "domestic_public"
    return "international" if _INTERNATIONAL.search(blob) else "domestic_public"


def venue(title, full_text=""):
    blob = title + " " + full_text[:400]
    for pat, name in _VENUES:
        if re.search(pat, blob, re.I):
            return name
    return ""


def main():
    d = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    d["doc_type_audit"] = d["title"].map(doc_type)
    d["audience_scope"] = [scope(t, f) for t, f in zip(d["title"], d["full_text"])]
    # always recompute (not "v or venue(t)") -- this script is delivered_venue's
    # only source for this file, so a stale wrong value must not survive a rerun
    d["delivered_venue"] = [venue(t, f) for t, f in zip(d["title"], d["full_text"])]
    d = add_audit_reach(d)
    validate(d)
    d.to_csv(CSV, index=False, encoding="utf-8")
    print(d["doc_type_audit"].value_counts().to_string())
    print(d["audience_scope"].value_counts().to_string())
    print(f"venue filled: {(d['delivered_venue']!='').sum()}/{len(d)}")
    for _, r in d.sort_values("date").iterrows():
        print(f"{r['date']} | {r['leader'][:18]:18} | {r['doc_type_audit'][:12]:12} | {r['audience_scope'][:12]:12} | {r['delivered_venue'][:20]:20} | {r['title'][:55]}")


if __name__ == "__main__":
    main()
