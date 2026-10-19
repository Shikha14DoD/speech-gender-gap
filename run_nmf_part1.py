"""
Per-leader NMF topic modeling for Ginette's Part 1 master handoff.

Scope (per her instructions):
  - Input: rows where doc_type_audit is delivered_speech, official_excerpt_
    compilation, or signed_article -- everything else (press summaries,
    press conferences, wire announcements, interviews, joint statements)
    is excluded from topic modeling here.
  - NMF runs SEPARATELY per leader -- never pooled -- so the model finds
    what's distinctive about each leader's own speeches, not generic
    topics shared by everyone.
  - A leader needs 30+ eligible docs to be analyzed at all. Within a
    leader, audience_reach subgroups (national_public / international /
    closed_door) need 5+ docs to get their own disaggregated run.
  - Ceremonial content is KEPT (per her instruction) -- the cleaning step
    strips non-substantive boilerplate/greetings/footers so they don't
    crowd out real topics, rather than dropping ceremonial rows outright.

Cleaning (see clean_for_nmf()):
  - Normalizes curly quotes/apostrophes to straight ASCII ones (ftfy
    handles most mojibake, but a direct unicode-quote map catches the
    rest -- needed because several sources mix both; see the apostrophe
    mismatch bug this caused earlier in review_part1_doctype.py).
  - Strips known boilerplate patterns observed across sources: PMO-style
    "today issued the following statement on X:" intros, "[Courtesy
    translation]" tags, social-share footers ("Share on Facebook..."),
    CNN transcript headers ("Return to Transcripts main page"), stray
    pipe-delimited bylines.
  - TfidfVectorizer's stop_words='english' handles ordinary function
    words; EXTRA_STOPWORDS adds speech-genre boilerplate (greetings,
    honorifics, sign-offs) that isn't in a general English stopword list
    but is generic across every leader's every speech and would otherwise
    dominate a trivial "greeting" topic instead of surfacing real content.

Usage:
    python run_nmf_part1.py --input data/part1/master_part1_working.csv \
        --out-dir data/part1/nmf_results --n-topics 8 --n-words 12
"""
import argparse
import json
import os
import re

import pandas as pd
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer

ELIGIBLE_DOC_TYPES = {"delivered_speech", "official_excerpt_compilation", "signed_article"}
MIN_LEADER_DOCS = 30
MIN_SUBGROUP_DOCS = 5

REACH_MAP = {
    "domestic_public": "national_public",
    "international": "international",
    "sectoral_stakeholder": "closed_door",
    "government_party_internal": "closed_door",
}

# ---- cleaning ----
QUOTE_MAP = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "–": "-", "—": "-",
})

BOILERPLATE_PATTERNS = [
    re.compile(r"The Prime Minister,[^,]+,\s*today (issued|released) the following statement[^:]*:", re.I),
    re.compile(r"\[\s*Courtesy translation\s*\]", re.I),
    re.compile(r"\[\s*The following video is available in Italian only\s*\]", re.I),
    re.compile(r"Return to Transcripts main page.*?(?=Aired)", re.I | re.S),
    re.compile(r"THIS IS A RUSH TRANSCRIPT.*?FORM\.", re.I | re.S),
    re.compile(r"Share on (Facebook|Twitter|Linkedin|Whatsapp|Telegram).*$", re.I | re.S),
    re.compile(r"Share on social network.*$", re.I | re.S),
    re.compile(r"Read more$", re.I),
]

EXTRA_STOPWORDS = {
    # greetings / sign-offs
    "thank", "thanks", "please", "good", "morning", "afternoon", "evening",
    "everyone", "everybody", "hello", "hi", "welcome", "goodbye", "friends",
    # honorifics / forms of address
    "ladies", "gentlemen", "distinguished", "honourable", "honorable",
    "excellency", "excellencies", "colleagues", "dear",
    # titles that are near-universal across every row and carry no topic signal
    "mr", "mrs", "ms", "president", "minister", "prime", "secretary",
    "chairman", "chairwoman", "speaker",
    # generic connective/filler common in transcribed speech
    "today", "very", "much", "just", "going", "want", "know", "think",
    "said", "say", "going", "ve", "re", "ll", "don", "didn", "let",
}


def clean_for_nmf(text: str) -> str:
    text = text.translate(QUOTE_MAP)
    for pat in BOILERPLATE_PATTERNS:
        text = pat.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def run_nmf_for_group(texts, n_topics, n_words, extra_stopwords):
    stop = set(EXTRA_STOPWORDS) | set(extra_stopwords)
    vectorizer = TfidfVectorizer(
        max_df=0.85, min_df=2, stop_words="english",
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z']{2,}\b",
    )
    X = vectorizer.fit_transform(texts)
    vocab = vectorizer.get_feature_names_out()
    keep_idx = [i for i, w in enumerate(vocab) if w not in stop]
    if len(keep_idx) < n_topics * n_words:
        return None  # not enough real vocabulary left to be meaningful
    X = X[:, keep_idx]
    vocab = vocab[keep_idx]

    k = min(n_topics, X.shape[0] - 1, X.shape[1] - 1)
    if k < 2:
        return None
    model = NMF(n_components=k, init="nndsvda", random_state=42, max_iter=500)
    model.fit(X)

    topics = []
    for comp in model.components_:
        top = comp.argsort()[::-1][:n_words]
        topics.append([vocab[i] for i in top])
    return topics


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--n-topics", type=int, default=8)
    ap.add_argument("--n-words", type=int, default=12)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    df = pd.read_csv(args.input, dtype=str, keep_default_na=False, low_memory=False)
    elig = df[df["doc_type_audit"].isin(ELIGIBLE_DOC_TYPES)].copy()
    elig["reach"] = elig["audience_scope"].map(REACH_MAP)
    elig["clean_text"] = elig["full_text"].map(clean_for_nmf)

    counts = elig.groupby(["country", "leader"]).size().sort_values(ascending=False)
    qualify = counts[counts >= MIN_LEADER_DOCS]

    results = {}
    for (country, leader) in qualify.index:
        sub = elig[(elig.country == country) & (elig.leader == leader)]
        leader_stop = {w.lower() for w in leader.split()}
        leader_key = f"{country}__{leader}".replace(" ", "_")

        overall_topics = run_nmf_for_group(
            sub["clean_text"].tolist(), args.n_topics, args.n_words, leader_stop
        )
        results[leader_key] = {"country": country, "leader": leader, "total_docs": len(sub),
                                "overall_topics": overall_topics, "by_audience_reach": {}}

        for reach_val, grp in sub.groupby("reach"):
            if len(grp) < MIN_SUBGROUP_DOCS:
                continue
            sub_topics = run_nmf_for_group(
                grp["clean_text"].tolist(), args.n_topics, args.n_words, leader_stop
            )
            results[leader_key]["by_audience_reach"][reach_val] = {
                "n_docs": len(grp), "topics": sub_topics
            }

        print(f"{leader} ({country}): {len(sub)} docs -> {len(results[leader_key]['overall_topics'] or [])} topics overall; "
              f"reach subgroups run: {list(results[leader_key]['by_audience_reach'].keys())}")

    out_path = os.path.join(args.out_dir, "nmf_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    main()
