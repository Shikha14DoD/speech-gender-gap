"""
Manual audience_scope review for the master Part 1 file. Resolves every
NMF-eligible (delivered_speech / official_excerpt_compilation /
signed_article) row whose audience_scope is `unclassified` or
`unclassified_provenance_lost` -- 420 rows, almost entirely a side effect
of review_part1_doctype.py promoting rows out of unclear_needs_review
(the original pipeline never computed audience_scope for them).

Read individually per country/leader, since each site's genre needed its
own judgment calls:
  - Canada (pm.gc.ca statements): overwhelmingly domestic commemorative/
    policy content, BUT a real minority (9 of 174) cover a specific
    foreign-affairs incident (Hamas attack anniversaries, an investigation
    into the Government of India, an Israeli military decision, a hostage
    release) -- caught by scanning for foreign-country/crisis keywords
    across the full set, not just a sample, after 2 were missed on first
    pass.
  - Mexico (Sheinbaum/AMLO stenographic transcripts): verified ~100%
    domestic program visits -- no international content hiding in the set.
  - Italy (governo.it "Statement by President Meloni on X" genre): genuine
    mix, read all 74 titles individually -- domestic policy/ceremonial
    vs. foreign-crisis condolence vs. addressed-to-a-specific-domestic-
    group (sectoral_stakeholder, e.g. a trade union assembly or foreign
    press corps briefing).
  - Latvia (Siliņa): skews heavily international (EU/Ukraine/bilateral
    content), consistent with her role as a small border state's PM.
  - The remaining small-country tail: read individually, one-off judgment
    calls noted inline where non-obvious (e.g. China's Xi Jinping party-
    document rows -> government_party_internal only where the text
    explicitly addresses a closed Party session/cadres, not just because
    the topic is party ideology).

Run: python review_part1_audience_scope.py --input <doc-type-reviewed csv> --out <path>
"""
import argparse

import pandas as pd

ELIGIBLE_DOC_TYPES = {"delivered_speech", "official_excerpt_compilation", "signed_article"}
UNCLASSIFIED_VALUES = {"unclassified", "unclassified_provenance_lost"}

CANADA_INTERNATIONAL_IDS = {
    "SPC-0618", "SPC-0712", "SPC-0723", "SPC-0830",  # trade/China/Lowy Institute/China
    "SPC-0411", "SPC-0508", "SPC-0620", "SPC-0647", "SPC-0648",  # Hamas/India/Israel/hostages
}

ITALY_LABELS = {
    "SPC-3814": "domestic_public", "SPC-3815": "domestic_public", "SPC-3827": "domestic_public",
    "SPC-3845": "international", "SPC-3851": "domestic_public", "SPC-3867": "domestic_public",
    "SPC-3868": "domestic_public", "SPC-3876": "international", "SPC-3891": "domestic_public",
    "SPC-3893": "international", "SPC-3895": "domestic_public", "SPC-3898": "sectoral_stakeholder",
    "SPC-3900": "domestic_public", "SPC-3907": "international", "SPC-3908": "domestic_public",
    "SPC-3918": "domestic_public", "SPC-3919": "domestic_public", "SPC-3922": "domestic_public",
    "SPC-3923": "international", "SPC-3925": "domestic_public", "SPC-3927": "international",
    "SPC-3928": "domestic_public", "SPC-3929": "domestic_public", "SPC-3930": "sectoral_stakeholder",
    "SPC-3933": "domestic_public", "SPC-3934": "domestic_public", "SPC-3935": "international",
    "SPC-3936": "sectoral_stakeholder", "SPC-3937": "domestic_public", "SPC-3938": "domestic_public",
    "SPC-3939": "domestic_public", "SPC-3940": "domestic_public", "SPC-3941": "domestic_public",
    "SPC-3942": "domestic_public", "SPC-3948": "domestic_public", "SPC-3952": "domestic_public",
    "SPC-3955": "domestic_public", "SPC-3989": "sectoral_stakeholder", "SPC-4000": "sectoral_stakeholder",
    "SPC-4001": "sectoral_stakeholder", "SPC-4015": "international", "SPC-4021": "domestic_public",
    "SPC-4023": "international", "SPC-4046": "international", "SPC-4060": "domestic_public",
    "SPC-4067": "international", "SPC-4071": "international", "SPC-4072": "international",
    "SPC-4073": "international", "SPC-4074": "international", "SPC-4083": "sectoral_stakeholder",
    "SPC-4084": "domestic_public", "SPC-4086": "domestic_public", "SPC-4090": "domestic_public",
    "SPC-4091": "domestic_public", "SPC-4103": "international", "SPC-4121": "domestic_public",
    "SPC-4126": "domestic_public", "SPC-4127": "domestic_public", "SPC-4133": "domestic_public",
    "SPC-4134": "international", "SPC-4135": "international", "SPC-4136": "domestic_public",
    "SPC-4141": "domestic_public", "SPC-4153": "international", "SPC-4156": "international",
    "SPC-4161": "domestic_public", "SPC-4162": "international", "SPC-4167": "domestic_public",
    "SPC-4169": "domestic_public", "SPC-4172": "sectoral_stakeholder", "SPC-4188": "international",
    "SPC-4196": "domestic_public", "SPC-4204": "domestic_public",
}

LATVIA_LABELS = {
    "SPC-7744": "international", "SPC-7745": "domestic_public", "SPC-7747": "international",
    "SPC-7748": "international", "SPC-7750": "international", "SPC-7755": "international",
    "SPC-7758": "international", "SPC-7766": "international", "SPC-7767": "international",
    "SPC-7768": "international", "SPC-7769": "sectoral_stakeholder", "SPC-7772": "international",
    "SPC-7774": "international", "SPC-7775": "international", "SPC-7777": "international",
    "SPC-7779": "international", "SPC-7780": "international", "SPC-7782": "domestic_public",
    "SPC-7784": "domestic_public", "SPC-7786": "international", "SPC-7789": "international",
    "SPC-7793": "international", "SPC-7798": "international", "SPC-7799": "international",
    "SPC-7800": "international", "SPC-7801": "international", "SPC-7804": "international",
    "SPC-7808": "domestic_public", "SPC-7811": "domestic_public", "SPC-7812": "domestic_public",
    "SPC-7814": "domestic_public", "SPC-7815": "domestic_public",
}

TAIL_LABELS = {
    # Bolivia
    "SPC-0223": "domestic_public", "SPC-0225": "domestic_public",
    # China -- Xi Jinping party-document rows; government_party_internal only
    # where the text explicitly addresses officials/cadres at a closed
    # session ("Comrades:", "this seminar for new members" of the Central
    # Committee), not merely because the topic is party ideology
    "SPC-1170": "domestic_public", "SPC-1174": "government_party_internal", "SPC-1178": "domestic_public",
    "SPC-1181": "domestic_public", "SPC-1193": "domestic_public", "SPC-1205": "domestic_public",
    "SPC-1263": "government_party_internal", "SPC-1266": "domestic_public", "SPC-1274": "domestic_public",
    "SPC-1321": "domestic_public", "SPC-1325": "domestic_public", "SPC-1326": "government_party_internal",
    # Denmark -- all domestic commemorative/civic events
    "SPC-1348": "domestic_public", "SPC-1351": "domestic_public", "SPC-1356": "domestic_public",
    "SPC-1357": "domestic_public", "SPC-1364": "domestic_public", "SPC-1368": "domestic_public",
    "SPC-1381": "domestic_public", "SPC-1383": "domestic_public",
    # Marshall Islands
    "SPC-4851": "domestic_public",
    # North Macedonia
    "SPC-6084": "sectoral_stakeholder", "SPC-6104": "domestic_public",
    # Panama
    "SPC-6114": "domestic_public",
    # Paraguay -- address to a foreign parliament (the Knesset)
    "SPC-6116": "international",
    # Peru
    "SPC-6122": "domestic_public",
    # Slovenia
    "SPC-7478": "domestic_public", "SPC-7482": "sectoral_stakeholder", "SPC-7490": "domestic_public",
    "SPC-7509": "sectoral_stakeholder", "SPC-7516": "international", "SPC-7538": "domestic_public",
    "SPC-7576": "domestic_public", "SPC-7615": "sectoral_stakeholder", "SPC-7636": "domestic_public",
    "SPC-7640": "domestic_public", "SPC-7653": "sectoral_stakeholder", "SPC-7686": "domestic_public",
    # Thailand -- Global Soft Power Talks, an international forum
    "SPC-6462": "international",
}


def review(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    elig_mask = df["doc_type_audit"].isin(ELIGIBLE_DOC_TYPES)
    unclass_mask = elig_mask & df["audience_scope"].isin(UNCLASSIFIED_VALUES)

    df["audience_scope_manually_reviewed"] = unclass_mask.map(str)

    canada_mask = unclass_mask & (df["country"] == "Canada")
    df.loc[canada_mask & df.speech_id.isin(CANADA_INTERNATIONAL_IDS), "audience_scope"] = "international"
    df.loc[canada_mask & ~df.speech_id.isin(CANADA_INTERNATIONAL_IDS), "audience_scope"] = "domestic_public"

    mexico_mask = unclass_mask & (df["country"] == "Mexico")
    df.loc[mexico_mask, "audience_scope"] = "domestic_public"

    for sid, label in {**ITALY_LABELS, **LATVIA_LABELS, **TAIL_LABELS}.items():
        df.loc[df.speech_id == sid, "audience_scope"] = label

    remaining = (elig_mask & df["audience_scope"].isin(UNCLASSIFIED_VALUES)).sum()
    if remaining:
        raise RuntimeError(f"{remaining} NMF-eligible rows still unclassified after review")

    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, help="output of review_part1_doctype.py")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    df = pd.read_csv(args.input, dtype=str, keep_default_na=False, low_memory=False)
    df = review(df)
    df.to_csv(args.out, index=False, encoding="utf-8")

    print(f"manually reviewed: {(df['audience_scope_manually_reviewed']=='True').sum()} rows")

    ELIGIBLE = ELIGIBLE_DOC_TYPES
    REACH_MAP = {
        "domestic_public": "national_public", "international": "international",
        "sectoral_stakeholder": "closed_door", "government_party_internal": "closed_door",
    }
    elig = df[df["doc_type_audit"].isin(ELIGIBLE)].copy()
    elig["reach"] = elig["audience_scope"].map(REACH_MAP)
    counts = elig.groupby(["country", "leader"]).size().sort_values(ascending=False)
    qualify = counts[counts >= 30]
    print(f"\nleaders with >=30 eligible docs: {len(qualify)}")
    for (c, l) in qualify.index:
        sub = elig[(elig.country == c) & (elig.leader == l)]
        rc = sub["reach"].value_counts()
        print(f"{l} ({c}): total {len(sub)} | {dict(rc[rc >= 5])} | drop(<5): {dict(rc[rc < 5])}")


if __name__ == "__main__":
    main()
