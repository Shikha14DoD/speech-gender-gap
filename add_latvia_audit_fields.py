"""
Adds doc_type_audit / audience_scope / audience_reach and fills delivered_venue
in data/processed/latvia_FINAL.csv (audit_vocab.py = master dictionary values).
Runs on the MERGED text+video file (merge_latvia.py's output, finalized).

Text rows (mk.gov.lv press feed, source_url has no "youtube") are press-office
write-ups -> press_summary_of_speech, except a plain government-formation
announcement -> wire_announcement. Video rows (source_url is a YouTube link)
are delivered_speech -- full recordings/transcripts of him speaking, not
third-person write-ups. Any future text page whose title starts "Address
by"/"Speech by" is also delivered_speech (see scraper_latvia.py).
Foreign trips/summits/press points with foreign officials -> international;
domestic announcements -> domestic_public.
Usage: python add_latvia_audit_fields.py   (safe to re-run)
"""
import re
import pandas as pd

from audit_vocab import add_audit_reach, validate

CSV = "data/processed/latvia_FINAL.csv"

_ANNOUNCEMENT = re.compile(r"assumes office|hands over the powers of office", re.I)

# audience_scope keyed on WHO it's addressed to, not the topic discussed --
# a domestic press conference that happens to mention Ukraine is still
# domestic_public. "r[iī]ga conference" handles the accented "Rīga" the video
# title uses (a plain "riga" pattern silently misses it -- caught by re-reading
# the actual title strings, not assuming ASCII).
_DOMESTIC_PRESSER = re.compile(r"full presser|speaks after government vote", re.I)
_CLOSED_MEETING = re.compile(r"closed meeting", re.I)   # checked against full_text below, not title
_DIPLOMATIC = re.compile(r"american embassy|4th of july", re.I)
_INTERNATIONAL = re.compile(
    r"\bparis\b|r[iī]ga conference|arctic|lithuania|european council|\bnato\b|"
    r"visiting ukraine|state award|secretary general|special envoy|sanctions", re.I)

_VENUES = [
    (r"r[iī]ga conference", "Riga, Latvia"),
    (r"arctic", "Rovaniemi, Finland"),
    (r"\bparis\b|visiting ukraine|ukraine.{0,15}state award", "Kyiv, Ukraine"),
    (r"nato headquarters|secretary general", "Brussels, Belgium"),
    (r"american embassy|4th of july|full presser|government vote", "Riga, Latvia"),
]

_VIDEO_PRESSER = re.compile(r"full presser|speaks after government vote|secretary general", re.I)


def doc_type(title, is_video):
    if is_video:
        # some of these videos are full press conferences (journalist Q&A
        # included in the transcript, verified by reading two of them),
        # not a prepared single-speaker address
        return "press_conference" if _VIDEO_PRESSER.search(title) else "delivered_speech"
    if title.lower().startswith(("address by", "speech by")):
        return "delivered_speech"
    if _ANNOUNCEMENT.search(title):
        return "wire_announcement"
    return "press_summary_of_speech"


def scope(title, full_text=""):
    if _CLOSED_MEETING.search(full_text):
        return "government_party_internal"   # a closed Cabinet meeting's decision
    if _DOMESTIC_PRESSER.search(title):
        return "domestic_public"
    if _DIPLOMATIC.search(title):
        return "sectoral_stakeholder"        # a foreign embassy's own reception, diplomatic corps
    return "international" if _INTERNATIONAL.search(title) else "domestic_public"


def venue(title, full_text=""):
    for pat, name in _VENUES:
        if re.search(pat, title, re.I):
            return name
    return "Riga, Latvia" if scope(title, full_text) in ("domestic_public", "sectoral_stakeholder",
                                                          "government_party_internal") else ""


def main():
    d = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    is_video = d["source_url"].str.contains("youtube", case=False)
    d["doc_type_audit"] = [doc_type(t, v) for t, v in zip(d["title"], is_video)]
    d["audience_scope"] = [scope(t, f) for t, f in zip(d["title"], d["full_text"])]
    d["delivered_venue"] = [venue(t, f) for t, f in zip(d["title"], d["full_text"])]
    d = add_audit_reach(d)
    validate(d)
    d.to_csv(CSV, index=False, encoding="utf-8")
    print(d["doc_type_audit"].value_counts().to_string())
    print(d["audience_scope"].value_counts().to_string())
    for _, r in d.sort_values("date").iterrows():
        print(f"{r['date']} | {r['doc_type_audit'][:12]:12} | {r['audience_scope'][:12]:12} | {r['delivered_venue']:16} | {r['title'][:60]}")


if __name__ == "__main__":
    main()
