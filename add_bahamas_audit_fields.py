"""
Adds doc_type_audit / audience_scope / audience_reach and fills delivered_venue
in data/processed/bahamas_FINAL.csv, using the controlled vocabulary in
audit_vocab.py (the master data dictionary's values).

Definitions used (from the dictionary):
  delivered_speech         spoken address
  press_summary_of_speech  third-person write-up of a speech, quoting it
  unclear_needs_review     short WRITTEN statements the rules cannot settle
  joint_statement          negotiated text, not the leader's own words
  audience_scope: domestic_public / international / sectoral_stakeholder /
                  government_party_internal / unclassified. The dictionary says
                  unclassified means "not yet known", so rules stay
                  conservative: no strong marker in the title -> unclassified.

Prepared opening remarks at a press conference are labelled delivered_speech
(the dictionary's press_conference is a stenographic Q&A transcript, which
these are not); a note is appended so a reviewer can see why.

Usage: python add_bahamas_audit_fields.py
"""
import re
import pandas as pd

from audit_vocab import add_audit_reach, validate

CSV = "data/processed/bahamas_FINAL.csv"

# ---------------------------------------------------------------- doc_type
_JOINT = re.compile(r"joint communiqu", re.I)
_OFFICE_STATEMENT = re.compile(r"(statement|readout)\b.{0,12}\b(from|of) the office|official readout", re.I)
_THIRD_PERSON_ANNOUNCE = re.compile(r"^(prime minister )?(philip )?davis announces", re.I)
# first-person WRITTEN statements (not delivered from a podium)
_WRITTEN_STATEMENT = re.compile(
    r"^(prime minister (philip )?davis'?s? )?(condolence |press )?statement (by|from|on)\b|"
    r"^statement on\b|statement by prime minister", re.I)
_SPOKEN_STATEMENT = re.compile(
    r"statement (at|to)\b|national statement|budget statement|opening statement|"
    r"statement to parliament", re.I)


def doc_type(title: str, text: str) -> str:
    if _JOINT.search(title):
        return "joint_statement"
    if _OFFICE_STATEMENT.search(title):
        return "unclear_needs_review"
    if _THIRD_PERSON_ANNOUNCE.search(title):
        return "press_summary_of_speech"
    if _SPOKEN_STATEMENT.search(title):
        return "delivered_speech"
    if _WRITTEN_STATEMENT.search(title):
        return "unclear_needs_review"
    return "delivered_speech"


# ------------------------------------------------------------ audience_scope
_INTERNATIONAL = re.compile(
    r"united nations|\bun\b general assembly|unga|\bcop ?\d\d|climate week|caricom|"
    r"brazil-caribbean|botswana|interpol|\bidb\b|inter-american|paho|\bwho\b|ipcc|"
    r"afrieximbank|afreximbank|african export|alm africa|vienna|"
    r"washington|caribbean ministerial|eclac|escaz|kuwait|hunan|saudi fund|"
    r"china-bahamas|palm beach|conference of chief justices|"
    r"world telecommunication|\bitu\b|heads of government meeting|"
    r"official visit of his excellency", re.I)

_DIPLOMATIC = re.compile(
    r"embassy|national day reception|independence celebrations|lunar new year|"
    r"diplomatic week|flag raising", re.I)

_DOMESTIC_PUBLIC = re.compile(
    r"national address|national statement|to the nation|"
    r"parliament|house of assembly|budget|debate|contribution (on|to)|"
    r"communication (to|on)|tribute|funeral|memorial|thanksgiving|day of prayer|"
    r"church service|majority rule|swearing-in|sworn in|independence|"
    r"appointment of (the )?cabinet|cabinet of the bahamas|commonwealth of the bahamas 20|"
    r"resolution|prorogation|bill\b", re.I)

_SECTORAL = re.compile(
    r"business outlook|chamber of commerce|business and investment forum|"
    r"economic outlook|energy summit|energy reform stakeholder|summit|conference|"
    r"conclave|convention|forum|expo\b|symposium|workshop|seminar|"
    r"union|signing|heads of agreement|\bhoa\b|banquet|luncheon|gala|"
    r"fund raising|installation ceremony|awards?\b|graduation|"
    r"investiture|installation", re.I)


def audience_scope(title: str):
    """Returns (scope, evidence). Evidence is the matched phrase, for auditing."""
    for pat, scope in ((_DIPLOMATIC, "sectoral_stakeholder"),
                       (_INTERNATIONAL, "international"),
                       (_DOMESTIC_PUBLIC, "domestic_public"),
                       (_SECTORAL, "sectoral_stakeholder")):
        m = pat.search(title)
        if m:
            return scope, m.group(0).lower()
    return "unclassified", ""


# ------------------------------------------------------------- venue
_VENUES = [
    (r"general assembly|unga|climate week", "New York, USA"),
    (r"cop ?29", "Baku, Azerbaijan"),
    (r"brasília|brasilia|brazil-caribbean", "Brasilia, Brazil"),
    (r"botswana", "Botswana"),
    (r"washington", "Washington, DC"),
    (r"grand bahama", "Grand Bahama"), (r"exuma", "Exuma"), (r"abaco", "Abaco"),
    (r"long island", "Long Island"), (r"cat island", "Cat Island"),
    (r"eleuthera", "Eleuthera"), (r"andros", "Andros"), (r"bimini", "Bimini"),
    (r"san salvador", "San Salvador"), (r"mayaguana", "Mayaguana"),
    (r"rum cay", "Rum Cay"), (r"black point", "Black Point, Exuma"),
    (r"fox hill", "Fox Hill, New Providence"), (r"treasure cay", "Treasure Cay, Abaco"),
    (r"walker'?s cay", "Walker's Cay, Abaco"), (r"moore'?s island", "Moore's Island, Abaco"),
    (r"arthur'?s town", "Arthur's Town, Cat Island"),
    (r"deadman'?s cay", "Deadman's Cay, Long Island"),
    (r"rock sound", "Rock Sound, Eleuthera"), (r"palmetto point", "Palmetto Point, Eleuthera"),
    (r"stirrup cay", "Great Stirrup Cay"), (r"carmichael|bozine|cockburn town", ""),
]


def delivered_venue(title: str) -> str:
    for pat, name in _VENUES:
        if re.search(pat, title, re.I):
            return name
    return ""


def main():
    d = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    d["doc_type_audit"] = [doc_type(t, x) for t, x in zip(d["title"], d["full_text"])]
    sc = [audience_scope(t) for t in d["title"]]
    d["audience_scope"] = [s for s, _ in sc]
    d["delivered_venue"] = [v or delivered_venue(t) for v, t in zip(d["delivered_venue"], d["title"])]
    d = add_audit_reach(d)
    validate(d)

    # note why press-conference remarks are delivered_speech (see docstring)
    PC_NOTE = " Prepared opening remarks at a press conference/briefing; Q&A is not included."
    pc = (d["title"].str.contains(r"press (?:conference|briefing)", case=False, regex=True)
          & ~d["notes"].str.contains(PC_NOTE, regex=False))      # idempotent: never append twice
    d.loc[pc, "notes"] = d.loc[pc, "notes"] + PC_NOTE

    d.to_csv(CSV, index=False, encoding="utf-8")

    print("doc_type_audit:\n" + d["doc_type_audit"].value_counts().to_string())
    print("\naudience_scope:\n" + d["audience_scope"].value_counts().to_string())
    print("\naudience_reach:\n" + d["audience_reach"].value_counts().to_string())
    print(f"\ndelivered_venue filled: {(d['delivered_venue'].str.len() > 0).sum()} / {len(d)}")
    print("\n--- listing for manual audit (date | doc | scope | evidence | title) ---")
    for (_, r), (_, ev) in zip(d.iterrows(), sc):
        print(f"{r['date']} | {r['doc_type_audit'][:12]:12} | {r['audience_scope'][:12]:12} | {ev[:16]:16} | {r['title'][:70]}")


if __name__ == "__main__":
    main()
