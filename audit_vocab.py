"""
Controlled vocabulary for the audit / classification columns, copied from the
master dataset's data dictionary (all_leaders_master, Sep 2026) so every
country's extract uses exactly the same labels.

    doc_type_audit  -- what kind of document the row is
    audience_scope  -- who the speech was addressed to
    audience_reach  -- collapsed version of audience_scope, for the
                       narrow-vs-broad comparison. Never assigned by hand:
                       always MAPPED from audience_scope, so the two can't
                       disagree.

Per-country scripts (add_<country>_audit_fields.py) decide doc_type_audit and
audience_scope from that country's titles/text; they then call
add_audit_reach() / validate() from here so the mapping and the allowed
values live in exactly one place.
"""
import pandas as pd

DOC_TYPE_AUDIT = {
    "delivered_speech", "press_conference", "interview", "joint_statement",
    "official_excerpt_compilation", "press_summary_of_speech",
    "wire_announcement", "signed_article", "unclear_needs_review",
}

AUDIENCE_SCOPE = {
    "domestic_public", "international", "sectoral_stakeholder",
    "government_party_internal", "unclassified", "unclassified_provenance_lost",
}

AUDIENCE_REACH = {"national_public", "international", "closed_door", "unclassified"}

# Dictionary: "closed_door = party_internal + sectoral_stakeholder.
# international is kept separate from national_public deliberately -- a
# summit is public but addressed to foreign leaders, not the nation."
# (Checks against the master's own counts: 701 + 1659 = 2360 closed_door;
#  1542 + 12 = 1554 unclassified.)
_REACH_FROM_SCOPE = {
    "domestic_public": "national_public",
    "international": "international",
    "government_party_internal": "closed_door",
    "sectoral_stakeholder": "closed_door",
    "unclassified": "unclassified",
    "unclassified_provenance_lost": "unclassified",
}


def audience_reach(scope: str) -> str:
    """audience_scope value -> audience_reach value. An unknown scope raises
    rather than silently becoming 'unclassified'."""
    try:
        return _REACH_FROM_SCOPE[scope]
    except KeyError:
        raise ValueError(f"audience_scope {scope!r} is not in the dictionary vocabulary")


def add_audit_reach(df: pd.DataFrame) -> pd.DataFrame:
    """Add/overwrite audience_reach from audience_scope."""
    df["audience_reach"] = df["audience_scope"].map(audience_reach)
    return df


def validate(df: pd.DataFrame) -> None:
    """Fail loudly if any audit column holds a value outside the dictionary."""
    for col, allowed in (("doc_type_audit", DOC_TYPE_AUDIT),
                         ("audience_scope", AUDIENCE_SCOPE),
                         ("audience_reach", AUDIENCE_REACH)):
        bad = sorted(set(df[col]) - allowed)
        if bad:
            raise ValueError(f"{col} has values outside the dictionary: {bad}")
