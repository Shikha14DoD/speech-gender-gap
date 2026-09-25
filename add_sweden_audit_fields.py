"""
Post-translation step for data/processed/sweden_FINAL.csv (run after
finalize_dataset.py). Rules read the SWEDISH original_title, not the machine
translation, so they don't depend on translation wording.

  1. Language fix: six of the 48 speeches were delivered in ENGLISH (NATO
     flag-raising, Seoul Summit for Democracy, a business seminar, Join Sweden
     Summit, an EU capital-markets event, the Berlin Security Conference); the
     Swedish site simply posts them under Swedish titles. They are not
     translations: language English, translated no, original_text blank.
     Detected from the text itself (English function words vs Swedish ones).
  2. doc_type_audit: every row is a speech delivered by the PM (including his
     statements to the Riksdag) -> delivered_speech.
  3. audience_scope (conservative; no clear marker -> unclassified):
       international          Nato, Nordic Council, Berlin Security Conference,
                              the Seoul Summit for Democracy
       domestic_public        national addresses, national/commemorative
                              ceremonies, Riksdag statements, public rallies
       sectoral_stakeholder   conferences, seminars, galas, award events
  4. delivered_venue: from the delivery line the site prints under each title
     ("Sergels torg, Stockholm, den 24 augusti 2026"), kept in `notes`; only
     accepted when it has that place-then-date shape.
Usage: python add_sweden_audit_fields.py   (safe to re-run)
"""
import re
import pandas as pd

from audit_vocab import add_audit_reach, validate

CSV = "data/processed/sweden_FINAL.csv"

_EN = {"the", "and", "of", "to", "is", "we", "our", "that", "for", "are", "this", "with", "have", "will"}
_SV = {"och", "att", "som", "det", "är", "vi", "av", "en", "på", "för", "med", "har", "inte", "ett", "om", "till"}


def is_english(text: str) -> bool:
    words = re.findall(r"[a-zåäö]+", str(text).lower())
    if not words:
        return False
    en = sum(w in _EN for w in words) / len(words)
    sv = sum(w in _SV for w in words) / len(words)
    return en > 0.15 and sv < 0.02


_INTERNATIONAL = re.compile(
    r"nato|sydkorea|demokratitoppm|nordiska r|berlin security", re.I)
_DOMESTIC = re.compile(
    r"till nationen|nationaldag|jultal|riksdag|regeringsf|eu-deklaration|veterandagen|"
    r"minnes|f.rintelsens|manifestation|det r.cker|v.ldsd.d|masskjutning|"
    r"sj.lvst.ndighetsdag|estonia|tsunami|synagoga|g.va", re.I)
_SECTORAL = re.compile(
    r"konferens|seminarium|symposium|summit|h.gtidssammank|krigsvetenskap|event|"
    r"stipendieutdelning|gala|f.rebilder|folk och f.rsvar", re.I)


def scope(title):
    for pat, name in ((_INTERNATIONAL, "international"), (_DOMESTIC, "domestic_public"),
                      (_SECTORAL, "sectoral_stakeholder")):
        m = pat.search(title)
        if m:
            return name, m.group(0).lower()
    return "unclassified", ""


# "<place>[, <city>], [weekday] den <d> <month> <year>"  -> the place part
_DELIVERY = re.compile(
    r"^(?P<v>[^.\n]{2,70}?),?\s+(?:(?:mån|tis|ons|tors|fre|lör|sön)dag\s+)?den\s+\d{1,2}\s+\w+\s+20\d\d",
    re.I)


def venue_from_notes(notes):
    m = re.search(r'Delivery line from the site: "([^"]+)"', notes)
    if not m:
        return ""
    v = _DELIVERY.match(m.group(1).strip())
    if not v:
        return ""
    place = v.group("v").strip(" ,.")
    if re.match(r"(?i)(tal|statsminister|talet)", place):     # a title/summary, not a place
        return ""
    return place


def main():
    d = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    # after finalize_dataset.py, `full_text` is ALWAYS the English column
    # (translated or native) -- checking it can never tell the two apart.
    # `original_text` is finalize's copy of the raw pre-translation source,
    # which for the 6 native-English speeches is itself English -- that's
    # the real signal.
    eng = d["original_text"].map(is_english)
    d.loc[eng, ["language", "translated", "original_text"]] = ["English", "no", ""]
    d["doc_type_audit"] = "delivered_speech"
    sc = [scope(t) for t in d["original_title"]]
    d["audience_scope"] = [s for s, _ in sc]
    d["delivered_venue"] = [v or venue_from_notes(n) for v, n in zip(d["delivered_venue"], d["notes"])]
    d = add_audit_reach(d)
    validate(d)
    d.to_csv(CSV, index=False, encoding="utf-8")
    print(f"English-language rows fixed: {int(eng.sum())}")
    print(d["audience_scope"].value_counts().to_string())
    print(f"venue filled: {(d['delivered_venue'] != '').sum()} / {len(d)}")
    for (_, r), (_, ev) in zip(d.iterrows(), sc):
        print(f"{r['date']} | {r['language'][:3]} | {r['audience_scope'][:12]:12} | {ev[:12]:12} | {r['delivered_venue'][:30]:30} | {r['original_title'][:52]}")


if __name__ == "__main__":
    main()
