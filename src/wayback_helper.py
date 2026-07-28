"""
Helper for discovering archived page URLs via the Internet Archive's
Wayback Machine CDX API, for sites whose own listing/directory page
doesn't return real links to a plain HTTP request.

IMPORTANT: large wildcard queries (e.g. asking for 1000s of results
across years of history in one request) have been found to reliably
time out on the Archive's server (returns an unusual "498" status,
even after retries). Smaller queries (a few dozen to a few hundred
results) succeed quickly and reliably. So this module splits a large
date range into smaller yearly chunks and queries each separately,
combining the results -- this is slower overall (several requests
instead of one) but far more reliable than one big request that keeps
failing outright.
"""

import json
import datetime as dt
from typing import List

from src.utils import get


def _query_chunk(url_prefix: str, from_date: str, to_date: str, limit: int) -> List[str]:
    """Query one date-range chunk. Returns a list of raw URLs (possibly empty)."""
    from curl_cffi import requests as curl_requests

    cdx_url = (
        "https://web.archive.org/cdx/search/cdx"
        f"?url={url_prefix}*"
        "&output=json"
        "&collapse=urlkey"
        "&fl=original"
        "&filter=statuscode:200"
        f"&limit={limit}"
        f"&from={from_date.replace('-', '')}"
        f"&to={to_date.replace('-', '')}"
    )

    try:
        # impersonate="chrome" mimics a real Chrome browser's connection
        # signature, not just its headers -- this is specifically needed
        # because the Wayback CDX endpoint appears to block Python's
        # standard `requests` library at the connection level, even with
        # full browser-like headers added.
        resp = curl_requests.get(cdx_url, impersonate="chrome", timeout=60)
    except Exception as e:
        print(f"  [error] curl_cffi request failed for {from_date} to {to_date}: {e}")
        return []

    if resp.status_code != 200:
        print(f"  [error] status {resp.status_code} for {from_date} to {to_date}")
        return []

    try:
        rows = json.loads(resp.text)
    except json.JSONDecodeError:
        print(f"  [error] bad response from Wayback CDX for {from_date} to {to_date}")
        return []

    if not rows or len(rows) < 2:
        return []

    return [row[0] for row in rows[1:]]

def get_archived_urls(url_prefix: str, from_date: str = None, limit: int = 5000) -> List[str]:
    """
    Return a de-duplicated list of real URLs the Wayback Machine has
    archived under url_prefix, discovered by querying year-by-year
    chunks (to avoid large-query timeouts) rather than one big request.
    """
    if from_date is None:
        from_date = "2019-01-01"  # reasonable fallback floor

    start_year = int(from_date[:4])
    current_year = dt.date.today().year

    all_urls: List[str] = []
    for year in range(start_year, current_year + 1):
        chunk_from = from_date if year == start_year else f"{year}-01-01"
        chunk_to = f"{year}-12-31"
        print(f"  querying Wayback CDX for {chunk_from} to {chunk_to}...")
        chunk_urls = _query_chunk(url_prefix, chunk_from, chunk_to, limit=500)
        print(f"    -> {len(chunk_urls)} URLs found")
        all_urls.extend(chunk_urls)

    # Normalize www vs non-www duplicates, AND strip tracking parameters.
    seen = set()
    deduped = []
    for u in all_urls:
        normalized = u.replace("https://www.", "https://").replace("http://www.", "https://")
        normalized = normalized.split("?")[0].split("#")[0]
        if not normalized.endswith("/"):
            normalized += "/"
        if normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)

    return deduped