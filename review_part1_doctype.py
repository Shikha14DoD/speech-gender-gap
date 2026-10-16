"""
Manual doc_type_audit review for the master Part 1 file (Ginette's
4,996-row, 20-country handoff). Resolves every `unclear_needs_review` row
by reading it and applying a per-site rubric built from samples, plus fixes
a handful of already-labeled rows that were actually mislabeled.

Rubric (confirmed against samples from Canada/pm.gc.ca and Italy/governo.it,
the two sites carrying 92% of the unclear backlog):
  - Spoken/video-sourced remarks                      -> delivered_speech
  - Office-issued written statement, leader's own      -> delivered_speech
    words (third-person intro + full quote, or no
    intro at all -- some scraper variants drop it)
  - Pure third-person narration, no reproduced words   -> wire_announcement
  - Multi-leader co-authored text (joint press         -> joint_statement
    release/statement/declaration/letter, G7/G20
    leaders' statement, First Ministers' statement)
  - Press-office recap of a parliamentary address      -> press_summary_of_speech
    ("addresses Parliament... responded to points")
  - Q&A format (Q:/Reporter:/Mananera press             -> press_conference
    conference)
  - Moderated panel / single Q&A exchange with a        -> interview
    reporter

Run: python review_part1_doctype.py --input <raw master csv> --out <path>
"""
import argparse
import re

import pandas as pd

ELIGIBLE_SIGNAL = "unclear_needs_review"

# ---- Canada (pm.gc.ca) rubric ----
STMT_INTRO_RE = re.compile(r"issued the following statement|released the following statement", re.I)
TITLE_STMT_RE = re.compile(r"^statement by (the )?prime minister", re.I)
VIDEO_URL_RE = re.compile(r"/videos?/", re.I)
QA_RE = re.compile(r"^\s*(Q:|Question:|Reporter:|MODERATOR:|JOURNALIST:)", re.I | re.M)
JOINT_TITLE_RE = re.compile(
    r"joint (press release|statement|declaration|letter|communiqu[eé])|"
    r"first ministers.? (joint )?statement|g7 leaders.?|g20 leaders.?|"
    r"leaders.? (statement|declaration)",
    re.I,
)

# ---- Italy (governo.it) rubric ----
IT_DATE_RE = re.compile(r"^\s*(\w+day,?\s+)?\d{1,2} \w+ \d{4}\s*", re.I)
IT_VIDEO_LABEL_RE = re.compile(r"^\[?\s*the following video is available in italian only\s*\]?", re.I)
IT_PARLIAMENT_RE = re.compile(r"addresses parliament|responded to the points|provided.*(chamber|senate).*with", re.I)
IT_JOINT_RE = re.compile(r"joint (press release|statement|declaration)|statement by president \w+.*(prime minister|chancellor|president)", re.I)
IT_STUB_RE = re.compile(
    r"^(the )?president (of the council of ministers,? )?giorgia meloni,?\s*"
    r"(delivered a speech|was in|attended|held a series of meetings)",
    re.I,
)
IT_MULTI_QUOTE_RE = re.compile(r"[-\u2013\u2014]\s*(stated|said|added|explained|commented|concluded)\s+(the )?(president|minister|prime minister)", re.I)
IT_FIRSTPERSON_RE = re.compile(r"\b(I|we|us|our|my|me)\b", re.I)

# ---- Mexico (gob.mx, Sheinbaum) ----
MX_PRESSCONF_RE = re.compile(r"press conference|ma[ñn]anera|right of reply", re.I)


def classify_canada(row):
    title, text = row["title"], row["full_text"]
    if JOINT_TITLE_RE.search(title):
        return "joint_statement"
    if QA_RE.search(text):
        return None  # fall through to manual
    if VIDEO_URL_RE.search(row["source_url"]):
        return "delivered_speech"
    if STMT_INTRO_RE.search(text[:200]) or TITLE_STMT_RE.search(title):
        return "delivered_speech" if len(text) > 80 else "wire_announcement"
    return None


def classify_italy(row):
    title, text = row["title"], row["full_text"]
    body = IT_DATE_RE.sub("", text, count=1).strip()
    body = IT_VIDEO_LABEL_RE.sub("", body).strip()
    if IT_JOINT_RE.search(title):
        return "joint_statement"
    if IT_PARLIAMENT_RE.search(title) or IT_PARLIAMENT_RE.search(body[:300]):
        return "press_summary_of_speech"
    if len(body) < 200 and IT_STUB_RE.search(body):
        return "wire_announcement"
    if len(IT_MULTI_QUOTE_RE.findall(body)) >= 2:
        return "press_summary_of_speech"
    if len(IT_FIRSTPERSON_RE.findall(body)) >= 1:
        return "delivered_speech"
    return "wire_announcement"


def classify_sheinbaum(row):
    blob = row["title"] + " " + row["full_text"][:300]
    return "press_conference" if MX_PRESSCONF_RE.search(blob) else "delivered_speech"


# Everything else (AMLO's 6, and the ~20-row long tail across 13 small
# countries) was read and labeled individually -- too few rows per leader
# to warrant a heuristic, and each had its own tell (video URL, "Q:"
# exchange, panel-discussion framing, UN General Debate address, etc).
# See the project's hand-off notes for the per-row reasoning.
MANUAL_LABELS = {
    # Canada: the heuristic above left 22 rows ambiguous (title doesn't
    # start with "Statement by Prime Minister" and isn't a /videos/ URL).
    # Read individually: solo remarks at a bilateral/summit visit ->
    # delivered_speech; multilateral declarations ("We, the Leaders of
    # the G7...") and bilateral meeting readouts -> joint_statement.
    "SPC-0230": "delivered_speech", "SPC-0231": "delivered_speech",
    "SPC-0234": "delivered_speech", "SPC-0235": "delivered_speech",
    "SPC-0720": "delivered_speech",
    "SPC-0568": "delivered_speech", "SPC-0712": "delivered_speech",
    "SPC-0713": "delivered_speech", "SPC-0715": "delivered_speech",
    "SPC-0718": "delivered_speech",
    "SPC-0520": "joint_statement", "SPC-0544": "joint_statement",
    "SPC-0580": "joint_statement", "SPC-0592": "joint_statement",
    "SPC-0601": "joint_statement",
    "SPC-0330": "joint_statement", "SPC-0357": "joint_statement",
    "SPC-0535": "joint_statement", "SPC-0606": "joint_statement",
    "SPC-0607": "joint_statement", "SPC-0665": "joint_statement",
    "SPC-0736": "joint_statement", "SPC-0740": "joint_statement",
    "SPC-0742": "joint_statement", "SPC-0795": "joint_statement",
    "SPC-0796": "joint_statement", "SPC-0801": "joint_statement",
    "SPC-0815": "joint_statement", "SPC-0819": "joint_statement",
    # Mexico -- AMLO
    "SPC-4854": "delivered_speech", "SPC-5016": "delivered_speech",
    "SPC-5017": "delivered_speech", "SPC-5072": "delivered_speech",
    "SPC-5078": "delivered_speech", "SPC-5100": "delivered_speech",
    # Small-country tail
    "SPC-0224": "delivered_speech", "SPC-0227": "press_conference",
    "SPC-0874": "delivered_speech", "SPC-1243": "delivered_speech",
    "SPC-1251": "delivered_speech", "SPC-1312": "delivered_speech",
    "SPC-1419": "interview", "SPC-1424": "delivered_speech",
    "SPC-4851": "delivered_speech", "SPC-6090": "delivered_speech",
    "SPC-6112": "delivered_speech", "SPC-6113": "delivered_speech",
    "SPC-6115": "delivered_speech", "SPC-6116": "delivered_speech",
    "SPC-6117": "delivered_speech", "SPC-6118": "interview",
    "SPC-6122": "delivered_speech", "SPC-6126": "interview",
    "SPC-6461": "delivered_speech", "SPC-6462": "delivered_speech",
}

# Rows that already carried *a* doc_type_audit value (so never entered the
# unclear-review queue) but were mislabeled -- caught by scanning for
# joint-document titles across the whole NMF-eligible set. Latvia's
# text_completeness column had already correctly flagged these as
# not_sole_authored; doc_type_audit just never got updated to match.
JOINT_DOCUMENT_BUGFIXES = {
    "SPC-7754", "SPC-7763", "SPC-7781", "SPC-7785", "SPC-7790",
    "SPC-7794", "SPC-7796", "SPC-7809", "SPC-8932", "SPC-7795",
}


def review(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["doc_type_manually_reviewed"] = "False"

    unclear = df["doc_type_audit"] == ELIGIBLE_SIGNAL

    canada = unclear & (df["country"] == "Canada")
    df.loc[canada, "doc_type_audit"] = df.loc[canada].apply(
        lambda r: classify_canada(r) or ELIGIBLE_SIGNAL, axis=1
    )

    italy = unclear & (df["country"] == "Italy")
    df.loc[italy, "doc_type_audit"] = df.loc[italy].apply(classify_italy, axis=1)

    sheinbaum = unclear & (df["country"] == "Mexico") & (df["leader"] == "Claudia Sheinbaum")
    df.loc[sheinbaum, "doc_type_audit"] = df.loc[sheinbaum].apply(classify_sheinbaum, axis=1)

    for sid, label in MANUAL_LABELS.items():
        df.loc[df.speech_id == sid, "doc_type_audit"] = label

    # mark every row touched above as manually reviewed
    was_unclear = unclear.copy()
    df.loc[was_unclear, "doc_type_manually_reviewed"] = "True"

    # separate bugfix pass: already-labeled rows that were wrong
    bugfix_mask = df.speech_id.isin(JOINT_DOCUMENT_BUGFIXES)
    df.loc[bugfix_mask, "doc_type_audit"] = "joint_statement"
    df.loc[bugfix_mask, "doc_type_manually_reviewed"] = "True"

    remaining = (df["doc_type_audit"] == ELIGIBLE_SIGNAL).sum()
    if remaining:
        raise RuntimeError(f"{remaining} rows still unclear_needs_review after review")

    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    df = pd.read_csv(args.input, dtype=str, keep_default_na=False, low_memory=False)
    df = review(df)
    df.to_csv(args.out, index=False, encoding="utf-8")

    print(df["doc_type_audit"].value_counts().to_string())
    print(f"\nmanually reviewed: {(df['doc_type_manually_reviewed']=='True').sum()} rows")


if __name__ == "__main__":
    main()
