"""
Adds three columns to tanzania_FINAL.csv, using the controlled vocabulary
from the master dataset's data dictionary (all_leaders_master.csv, Sep 2026):

  doc_type_audit  -- document type, read from the text/title rather than
                     trusted from the scraper. Allowed values (dictionary):
                     delivered_speech, press_conference, interview,
                     joint_statement, official_excerpt_compilation,
                     press_summary_of_speech, wire_announcement,
                     signed_article, unclear_needs_review.
  audience_scope  -- who the speech was addressed to. Allowed values:
                     domestic_public, international, sectoral_stakeholder,
                     government_party_internal, unclassified.
  audience_reach  -- collapsed audience_scope (national_public / international /
                     closed_door / unclassified). MAPPED from audience_scope via
                     audit_vocab.py, never assigned by hand.
  delivered_venue -- city/place, parsed from the title.

Rule-based, same spirit as the master merge's own classification
("provenance markers, agency datelines, title patterns and oral-delivery
markers"). Built by reading all 91 Tanzania titles in full (not just
keyword-matching blind) -- see the per-row audit printout at the bottom of
a run. Ambiguous rows are left "unclear_needs_review" / "unclassified"
rather than force-fit, per the dictionary's own guidance to treat
unclassified as not-yet-known.

Usage: python add_tanzania_audit_fields.py
"""
import re
import pandas as pd

from audit_vocab import add_audit_reach, validate

CSV = "data/processed/tanzania_FINAL.csv"

# ---------------------------------------------------------------- doc_type
_PRESS = re.compile(
    r"press statement|to the media|statement to the press|to journalists|"
    r"press point|press conference", re.I)
_INTERVIEW = re.compile(r"\binterview\b|mahojiano", re.I)
_JOINT = re.compile(r"joint statement|joint declaration|communiqu", re.I)


def doc_type(title: str, notes: str) -> str:
    blob = f"{title} {notes}"
    if _JOINT.search(blob):
        return "joint_statement"
    if _INTERVIEW.search(blob):
        return "interview"
    if _PRESS.search(blob):
        return "press_conference"
    # everything else in this file is a curated verbatim address (PDF
    # transcript or a >=4-minute video the leader is speaking in)
    return "delivered_speech"


# ------------------------------------------------------------ audience_scope
# Checked first, regardless of anything else in the title: a diplomatic
# reception is addressed to the diplomatic corps, not the general public,
# even though it happens to fall on New Year's.
_DIPLOMATIC_CORPS = re.compile(
    r"diplomatic sherry party|heads of diplomatic missions", re.I)

# Domestically-observed holidays that happen to carry "international" in
# their proper name -- must be checked BEFORE the international pattern.
_DOMESTIC_NAMED_DAY = re.compile(
    r"international women'?s day|international workers'? day", re.I)

# whole-nation addresses / state occasions broadcast to the country. Uses
# "hayati" (Swahili honorific for the recently deceased, used for Tanzania's
# own dignitaries) rather than "state funeral" alone, so a foreign leader's
# funeral abroad (which this project also covers) falls through to the
# international check below instead.
_DOMESTIC_PUBLIC = re.compile(
    r"new year|akihutubia taifa|to the nation\b|"
    r"national funeral|state funeral of .{0,20}hayati|"
    r"anniversary of the union|union of tanganyika|miaka (60|61) ya muungano|"
    r"opening.{0,15}(parliament|bunge)|closing.{0,20}bunge|kufungua rasmi bunge|"
    r"kuhitimisha shughuli za bunge|bunge la (12|13)|13th parliament|"
    r"kuapishwa kuwa rais|sworning? in elected leaders|"
    r"inaugurat\w+ (ceremony )?of .{0,25}\bpresident\b|"
    r"citizens of|wananchi wa|talking to the (citizens|elderly)|"
    r"farewell for the body of|kuuaga mwaka|salamu za mwaka",
    re.I)

# foreign country / city / international summit or organisation
_INTERNATIONAL = re.compile(
    r"malawi|zambia|rwanda|kigali|brics|saudi arabia|riyadh|african-saudi|"
    r"united nations|cop ?28|dubai|uae|g20|g-20|rio de janeiro|brazil|"
    r"focac|beijing|\bchina\b|kenya|nairobi|turkey|istanbul|\bkorea\b|seoul|"
    r"kintex|mozambique|msumbiji|maputo|mombizi|namibia|windhoek|angola|"
    r"luanda|bunge nchini angola|national assembly of the republic of|"
    r"india|jawaharlal nehru|new delhi|world tourism|world travel|"
    r"merck foundation|goalkeepers?( award)?|eac and sadc|"
    r"country and government of \(au\)|\bau\)|african union|"
    r"state visit|federal republic|federal president|international energy agency|"
    r"paris, france|commonwealth law ministers|"
    r"president of the republic of (malawi|zambia|namibia|mozambique|kenya|romania)|"
    r"honorable klaus iohan|kamala harris|steinmeier|"
    r"vice president of the u\.?s\.?a|"
    r"international development association|ida.{0,5}for africa|"
    r"international trade fair|forum of traders of tanzania and turkey|"
    r"idc for africa|heads of african countries|meeting of heads of",
    re.I)

# specific-audience / stakeholder-group occasions (held in Tanzania, not a
# nation-wide broadcast address)
_SECTORAL = re.compile(
    r"diplomatic sherry party|heads of diplomatic missions|"
    r"chief justice|jaji mkuu|justice week|law day|"
    r"fishing boats|zstc|mining equipment|energy\b|"
    r"personal information protection|data protection|"
    r"forum|traders of|business forum|wafanyabiashara|"
    r"national development vision|dira ya taifa|"
    r"induction of bishop|kkkt|eid el ?fitr|eid council|"
    r"land policy|water policy|water project|foreign affairs policy|"
    r"cooperative bank|nyerere'?s book|teacher\b|mwalimu|"
    r"pen awards|police force|senior officers of the police|"
    r"alat\b|association of local authorities|"
    r"information sector|honorary doctorate|honorary degree|"
    r"national land policy|revised law version|"
    r"government dividend from public organi[sz]ations|"
    r"inspection of the construction|salato international airport|"
    r"vaccine|chanjo|livestock|mifugo|utambuzi wa mifugo|"
    r"clove|karafuu|honorary award of the parliament|university of mzumbe",
    re.I)


def audience_scope(title: str) -> str:
    if _DIPLOMATIC_CORPS.search(title):
        return "sectoral_stakeholder"
    if _DOMESTIC_NAMED_DAY.search(title):
        return "domestic_public"
    if _INTERNATIONAL.search(title):
        return "international"
    if _DOMESTIC_PUBLIC.search(title):
        return "domestic_public"
    if _SECTORAL.search(title):
        return "sectoral_stakeholder"
    return "unclassified"


# ------------------------------------------------------------- venue
_VENUES = [
    # Tanzania
    (r"chamwino", "Chamwino, Dodoma"), (r"\bnala\b", "Nala, Dodoma"),
    (r"\bdodoma\b", "Dodoma"),
    (r"\btunguu\b", "Tunguu, Zanzibar"), (r"\bpemba\b", "Pemba"),
    (r"\bunguja\b", "Unguja"), (r"kizimkazi", "Kizimkazi, Zanzibar"),
    (r"\bzanzibar\b", "Zanzibar"),
    (r"dar es salaam", "Dar es Salaam"),
    (r"moshi|kilimanjaro", "Moshi, Kilimanjaro"),
    (r"\bmwanga\b", "Mwanga"), (r"\bmwanza\b", "Mwanza"),
    (r"\bmonduli\b", "Monduli"), (r"morogoro|mzumbe", "Morogoro"),
    (r"\bmeatu\b", "Meatu"), (r"\barusha\b", "Arusha"),
    (r"\bmbeya\b", "Mbeya"),
    # foreign
    (r"malawi", "Malawi"), (r"zambia", "Zambia"),
    (r"kigali|rwanda", "Kigali, Rwanda"),
    (r"riyadh|saudi arabia", "Riyadh, Saudi Arabia"),
    (r"nairobi|kenya", "Nairobi, Kenya"),
    (r"istanbul|turkey", "Istanbul, Turkey"),
    (r"seoul|kintex|korea", "Seoul, South Korea"),
    (r"beijing|focac", "Beijing, China"),
    (r"maputo|mozambique|msumbiji|mombizi", "Maputo, Mozambique"),
    (r"windhoek|namibia", "Windhoek, Namibia"),
    (r"luanda|angola", "Luanda, Angola"),
    (r"new delhi|india", "New Delhi, India"),
    (r"dubai|uae\b", "Dubai, UAE"),
    (r"paris, france", "Paris, France"),
    (r"rio de janeiro|brazil", "Rio de Janeiro, Brazil"),
]


def delivered_venue(title: str) -> str:
    for pat, name in _VENUES:
        if re.search(pat, title, re.I):
            return name
    return ""


def main():
    d = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    d["doc_type_audit"] = [doc_type(t, n) for t, n in zip(d["title"], d["notes"])]
    d["audience_scope"] = d["title"].map(audience_scope)
    d["delivered_venue"] = d["title"].map(delivered_venue)
    d = add_audit_reach(d)
    validate(d)

    d.to_csv(CSV, index=False, encoding="utf-8")

    print("doc_type_audit:")
    print(d["doc_type_audit"].value_counts().to_string())
    print("\naudience_scope:")
    print(d["audience_scope"].value_counts().to_string())
    print(f"\ndelivered_venue filled: {(d['delivered_venue'].str.len() > 0).sum()} / {len(d)}")

    print("\n--- full listing for manual audit ---")
    for _, r in d.sort_values("date").iterrows():
        print(f"{r['date']} | {r['doc_type_audit']:18} | {r['audience_scope']:22} | "
              f"{r['delivered_venue']:22} | {r['title'][:75]}")


if __name__ == "__main__":
    main()
