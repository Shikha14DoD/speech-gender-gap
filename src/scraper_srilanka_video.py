"""
Sri Lanka -- VIDEO route.  President's Media Division YouTube channel
(@PresidentsMediaSriLanka): near-complete video coverage of President
Anura Kumara Dissanayake's speeches / addresses / press events, plus a
few Prime Minister (Harini Amarasuriya) items.

The videos are in Sinhala with NO manual captions, but YouTube
auto-generates Sinhala speech-recognition captions and offers them
machine-translated into English.  This scraper pulls that English
auto-caption via yt-dlp -- it is rough (no punctuation, ASR + MT
errors), usable for thematic / word-frequency analysis only, NOT
verbatim.  Every row says so in `notes`.

The channel's uploads only go back to Nov 2024, so this route is
effectively AKD-era only -- Wickremesinghe-era video is not available
here (see `scraper_srilanka.py` for his text transcripts).

Companion: `scraper_srilanka.py` (text) and `merge_srilanka.py`.
"""

import os
import re
import time
import datetime as dt
from typing import List, Optional

from curl_cffi import requests as curl_requests

from src.utils import clean_text, Speech
from src.text_processing import in_date_range, classify_as_speech, classify_content_type
from src.translate_helper import translate_to_english

# yt-dlp needs a JS runtime for YouTube; node ships with the machine
os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + r"C:\nvm4w\nodejs"
import yt_dlp  # noqa: E402

CHANNEL = "https://www.youtube.com/@PresidentsMediaSriLanka"
YDL_COMMON = {"quiet": True, "no_warnings": True, "skip_download": True,
              "js_runtimes": {"node": {}}, "ignoreerrors": True}

AKD_START = "2024-09-23"
# The channel is the President's Media Division -- essentially everything
# is presidential activity. Keep any item >= this long (short items are
# news-bulletin clips / photo-op stings); only drop the obvious non-speech
# categories below.
MIN_DURATION = 240

_NON_SPEECH_CUE = re.compile(
    r"\bsong\b|ගීතය|ගීතය|jayamangala|anthem|ජාතික ගීය|trailer|promo|teaser|"
    r"theme (song|music)|music video|documentary trailer",
    re.I,
)


def _ydl(opts):
    o = dict(YDL_COMMON)
    o.update(opts)
    return yt_dlp.YoutubeDL(o)


def _list_channel() -> List[dict]:
    out, seen = [], set()
    for tab in ("videos", "streams"):
        try:
            with _ydl({"extract_flat": True}) as y:
                info = y.extract_info(f"{CHANNEL}/{tab}", download=False)
        except Exception as e:
            print(f"  [warn] channel/{tab} list failed: {e}")
            continue
        ents = [e for e in (info.get("entries") or []) if e and e.get("id")]
        for e in ents:
            if e["id"] not in seen:
                seen.add(e["id"])
                out.append(e)
        print(f"  channel/{tab}: {len(ents)} entries")
    return out


def _vtt_to_text(vtt: str) -> str:
    lines = []
    for ln in vtt.splitlines():
        ln = ln.strip()
        if (not ln or ln == "WEBVTT" or ln.startswith(("Kind:", "Language:", "NOTE"))
                or "-->" in ln or re.match(r"^\d+$", ln)):
            continue
        ln = re.sub(r"<[^>]+>", "", ln)                  # inline timing tags
        ln = re.sub(r"&nbsp;", " ", ln)
        if lines and lines[-1] == ln:                    # YT repeats rolling lines
            continue
        lines.append(ln)
    return clean_text(" ".join(lines))


def _english_caption(video_id: str) -> str:
    """Download YouTube's English (auto-translated) auto-caption as plain text."""
    try:
        with _ydl({"writeautomaticsub": True, "subtitleslangs": ["en"],
                   "subtitlesformat": "vtt"}) as y:
            info = y.extract_info(f"https://www.youtube.com/watch?v={video_id}",
                                  download=False)
    except Exception:
        return ""
    auto = (info or {}).get("automatic_captions") or {}
    tracks = auto.get("en") or auto.get("en-US") or []
    url = next((t["url"] for t in tracks if t.get("ext") == "vtt"),
               next((t["url"] for t in tracks), None))
    if not url:
        return ""
    for attempt in range(4):
        try:
            r = curl_requests.get(url, impersonate="chrome", timeout=40)
            if r.status_code == 200 and "WEBVTT" in r.text[:200]:
                return _vtt_to_text(r.text)
            time.sleep(4 * (attempt + 1))
        except Exception:
            time.sleep(4 * (attempt + 1))
    return ""


def _which_leader(date: Optional[str], title: str, desc: str):
    blob = f"{title}\n{desc}".lower()
    if re.search(r"අගමැති|prime minister|\bpm\b|harini|amarasuriya", blob):
        return "Harini Amarasuriya", "Prime Minister"
    return "Anura Kumara Dissanayake", "President"


def parse_srilanka_video(leader_config: dict, start_date: str, end_date: str,
                         limit: Optional[int] = None) -> List[Speech]:
    print("== Sri Lanka -- video (PMD YouTube, English auto-caption) ==")
    entries = _list_channel()
    print(f"  {len(entries)} unique channel videos")

    speeches: List[Speech] = []
    stats = {"short": 0, "not_speech": 0, "no_caption": 0, "out_of_range": 0}
    by: dict = {}

    for i, ent in enumerate(entries, 1):
        vid = ent["id"]
        if i % 25 == 0:
            print(f"  [{i}/{len(entries)}] kept={len(speeches)} no_caption={stats['no_caption']}")
        try:
            with _ydl({}) as y:
                v = y.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
        except Exception:
            v = None
        if not v:
            continue

        title = clean_text(v.get("title") or ent.get("title") or "")
        desc = clean_text((v.get("description") or "")[:600])
        dur = v.get("duration") or 0
        up = v.get("upload_date")
        date = f"{up[:4]}-{up[4:6]}-{up[6:]}" if up and len(up) == 8 else None

        if dur and dur < MIN_DURATION:
            stats["short"] += 1
            continue
        if _NON_SPEECH_CUE.search(f"{title} {desc}"):
            stats["not_speech"] += 1
            continue
        if not in_date_range(date, start_date, end_date):
            stats["out_of_range"] += 1
            continue

        cap = _english_caption(vid)
        if len(cap) < 200:
            stats["no_caption"] += 1
            if not dur or dur < 600:
                # short + no caption -> almost certainly a news-bulletin clip
                continue
            # a long speech YouTube simply didn't caption -- keep, flagged
            cap = "[NO ENGLISH AUTO-CAPTION AVAILABLE FOR THIS VIDEO]"

        leader, role = _which_leader(date, title, desc)

        title_en = ""
        if re.search(r"[\u0d80-\u0dff]", title):          # Sinhala block
            try:
                title_en = translate_to_english(title, "si") or ""
            except Exception:
                title_en = ""
        title_en = title_en or title

        speeches.append(Speech(
            country="Sri Lanka",
            leader=leader,
            role=role,
            date=date,
            title=title_en,
            full_text=cap,
            language="Sinhala",
            source_url=f"https://www.youtube.com/watch?v={vid}",
            likely_speech=classify_as_speech(title_en),
            content_type=classify_content_type(title_en),
            notes=(f"VIDEO. Transcript is YouTube's automatic Sinhala "
                   f"speech-recognition, auto-translated to English by YouTube "
                   f"-- no punctuation, machine-translation errors, suitable for "
                   f"thematic/word-frequency analysis only, NOT verbatim. "
                   f"Original video title (Sinhala): {title!r}. "
                   f"Duration {dur//60}m. Source: PMD YouTube channel."),
        ))
        by[leader] = by.get(leader, 0) + 1
        if limit and len(speeches) >= limit:
            break

    print(f"\n  Sri Lanka video done: {len(speeches)} kept {by} | short={stats['short']} "
          f"not_speech={stats['not_speech']} no_caption={stats['no_caption']} "
          f"out_of_range={stats['out_of_range']}")
    return speeches
