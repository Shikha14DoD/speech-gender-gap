"""
Helper for discovering archived page URLs via the Internet Archive's
Wayback Machine CDX API, for sites whose own listing/directory page
doesn't return real links to a plain HTTP request (e.g. Denmark's
stm.dk, where the speech list only renders after client-side JavaScript
runs, which our scraper can't execute).

This queries "what URLs has the Internet Archive ever crawled under
this path", giving us a reliable list of individual speech pages to
scrape directly -- sidestepping the broken listing page entirely.
"""

import json
from typing import List

from src.utils import get


def get_archived_urls(url_prefix: str, from_date: str = None, limit: int = 5000) -> List[str]:
    """
    Return a de-duplicated list of real URLs the Wayback Machine has
    archived under url_prefix (e.g. 'stm.dk/statsministeren/taler/').

    from_date, if given, should be 'YYYY-MM-DD' -- this asks the Wayback
    Machine itself to only return URLs first archived on/after that date,
    which is both faster (smaller server-side query, less likely to time
    out) and avoids wasting time later checking decades of a predecessor's
    speeches we'd only filter out anyway.
    """
    cdx_url = (
        "https://web.archive.org/cdx/search/cdx"
        f"?url={url_prefix}*"
        "&output=json"
        "&collapse=urlkey"
        "&fl=original"
        "&filter=statuscode:200"
        f"&limit={limit}"
    )
    if from_date:
        cdx_url += f"&from={from_date.replace('-', '')}"

    resp = get(cdx_url)
    if resp is None:
        print("  [error] could not reach the Wayback CDX API")
        return []

    rows = json.loads(resp.text)
    if not rows or len(rows) < 2:
        return []

    urls = [row[0] for row in rows[1:]]

    seen = set()
    deduped = []
    for u in urls:
        normalized = u.replace("https://www.", "https://").replace("http://www.", "https://")
        normalized = normalized.split("?")[0].split("#")[0]
        if not normalized.endswith("/"):
            normalized += "/"
        if normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)

    return deduped