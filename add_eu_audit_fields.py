"""
Adds doc_type_audit / audience_scope / audience_reach and fills delivered_venue
in data/processed/eu_FINAL.csv, using the controlled vocabulary in
audit_vocab.py (the master data dictionary's values).

The EU has no single "nation", so the dictionary's domestic/international split
is applied as: domestic_public = addressed to EU institutions / the EU public
(European Parliament plenaries, State of the Union, accession anniversaries,
EU-internal commemorations); international = addressed to third countries or
international bodies (G7, NATO, UN, Ukraine, bilateral summits);
sectoral_stakeholder = specific industry / research / civil-society audiences;
government_party_internal = closed EU-executive or party meetings (EU
Ambassadors Conference, the College of Commissioners, the EPP party congress).
No strong marker in the title -> unclassified ("not yet known").

Recorded video messages are spoken, so they are delivered_speech.

Usage: python add_eu_audit_fields.py   (safe to re-run)
"""
import re
import pandas as pd

from audit_vocab import add_audit_reach, validate

CSV = "data/processed/eu_FINAL.csv"

# ---------------------------------------------------------------- doc_type
_SHARED_STATEMENT = re.compile(r"high representative.{0,40}with president von der leyen", re.I)
_PLAIN_MESSAGE = re.compile(r"^message by president", re.I)


def doc_type(title: str) -> str:
    if _SHARED_STATEMENT.search(title):
        return "unclear_needs_review"      # one text, spoken jointly with HR/VP Kallas
    if _PLAIN_MESSAGE.search(title):
        return "unclear_needs_review"      # written or recorded? the title does not say
    return "delivered_speech"


# ------------------------------------------------------------ audience_scope
_INTERNAL_CLOSED = re.compile(
    r"epp congress|eu ambassadors conference|solemn undertaking", re.I)

_INTERNATIONAL = re.compile(
    r"\bg7\b|\bg20\b|nato|antonov|united nations|\bun\b|\bcop ?\d\d|ukrain|kyiv|munich security|"
    r"world economic forum|eu-[a-z ]{2,25}summit|african union|gulf cooperation|mattei|"
    r"\bindia\b|egypt|uzbekistan|samarkand|central asia|tirana|albania|western balkans|"
    r"montenegro|south africa|canad|australia|mercosur|moldova|gavi|palestin|middle east|"
    r"syria|international coalition|global gateway|global alliance|small island|keio|"
    r"nordic council|ocean conference|climate summit|summit for democracy|"
    r"summit in support of multilateralism|italy-africa|international energy agency|"
    r"international summit|ai(?:rtificial intelligence)? action summit|"
    r"czech and slovak|international space summit|un ocean|\bunga\b", re.I)

# a speech TO the European Parliament is addressed to that EU institution,
# whatever its topic (Ukraine, the Middle East, China ...)
_EP_AUDIENCE = re.compile(
    r"european parliament|\bep\b plenary|\bep\b joint debate|\bep\b formal|"
    r"plenary debate|parliamentary session|formal sitting", re.I)

_DOMESTIC_PUBLIC = re.compile(
    r"european parliament|\bep plenary|\bep\b|state of the union|accession|"
    r"membership in the european union|committee of the regions|"
    r"economic and social committee|opening ceremony of the (danish|cypriot|hungarian)|"
    r"presidency|memorial ceremony|delors|spinelli|international women'?s day|"
    r"new year|chanukah|parliamentary committees|parliamentary session|"
    r"cohesion forum|european youth event|covenant of mayors", re.I)

_SECTORAL = re.compile(
    r"forum|conference|summit|congress|dialogue|days\b|festival|prize|award|"
    r"ceremony|business|industry|industrial|university|research|bauhaus|innovation|"
    r"symposium|event|congress|assembly|academy|institute|federation|association|"
    r"roundtable|convention|competitiveness|medicines|hydrogen|energy|climate|"
    r"defence|security|cancer|digital|artificial intelligence|space|agri|farm|"
    r"chamber of|laudatio|honoris causa|medal|order of europe|erasmus|tech week|job day|medical school", re.I)


def audience_scope(title: str):
    """Returns (scope, evidence) -- evidence is the matched phrase, for auditing."""
    for pat, scope in ((_INTERNAL_CLOSED, "government_party_internal"),
                       (_EP_AUDIENCE, "domestic_public"),
                       (_INTERNATIONAL, "international"),
                       (_DOMESTIC_PUBLIC, "domestic_public"),
                       (_SECTORAL, "sectoral_stakeholder")):
        m = pat.search(title)
        if m:
            return scope, m.group(0).lower()
    return "unclassified", ""


# ------------------------------------------------------------- venue
_VENUES = [
    (r"kyiv|antonov airport|college-to-government meeting in ukraine", "Kyiv, Ukraine"),
    (r"hamburg", "Hamburg, Germany"), (r"munich", "Munich, Germany"),
    (r"world economic forum", "Davos, Switzerland"),
    (r"aachen", "Aachen, Germany"), (r"berlin", "Berlin, Germany"),
    (r"copenhagen|royal danish military", "Copenhagen, Denmark"),
    (r"tirana", "Tirana, Albania"), (r"samarkand", "Samarkand, Uzbekistan"),
    (r"antwerp", "Antwerp, Belgium"), (r"sorbonne", "Paris, France"),
    (r"australian parliament", "Canberra, Australia"),
    (r"cottbus", "Cottbus, Germany"), (r"bled strategic", "Bled, Slovenia"),
    (r"keio", "Tokyo, Japan"), (r"eu-india summit", "New Delhi, India"),
    (r"cop30", "Belem, Brazil"), (r"un ocean conference", "Nice, France"),
    (r"sevilla|seville", "Seville, Spain"), (r"hannover", "Hannover, Germany"),
    (r"european court of justice", "Luxembourg"),
]


def delivered_venue(title: str) -> str:
    for pat, name in _VENUES:
        if re.search(pat, title, re.I):
            return name
    return ""


def main():
    d = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    d["doc_type_audit"] = d["title"].map(doc_type)
    sc = [audience_scope(t) for t in d["title"]]
    d["audience_scope"] = [s for s, _ in sc]
    d["delivered_venue"] = [v or delivered_venue(t) for v, t in zip(d["delivered_venue"], d["title"])]
    d = add_audit_reach(d)
    validate(d)

    NOTE = " Statement delivered jointly with High Representative/Vice-President Kallas; authorship of individual passages is not marked in the source."
    m = d["title"].str.contains(_SHARED_STATEMENT) & ~d["notes"].str.contains(NOTE, regex=False)
    d.loc[m, "notes"] = d.loc[m, "notes"] + NOTE

    d.to_csv(CSV, index=False, encoding="utf-8")

    print("doc_type_audit:\n" + d["doc_type_audit"].value_counts().to_string())
    print("\naudience_scope:\n" + d["audience_scope"].value_counts().to_string())
    print("\naudience_reach:\n" + d["audience_reach"].value_counts().to_string())
    print(f"\ndelivered_venue filled: {(d['delivered_venue'].str.len() > 0).sum()} / {len(d)}")
    print("\n--- listing for manual audit (date | scope | evidence | title) ---")
    for (_, r), (_, ev) in zip(d.iterrows(), sc):
        print(f"{r['date']} | {r['audience_scope'][:12]:12} | {ev[:18]:18} | {r['title'][:78]}")


if __name__ == "__main__":
    main()
