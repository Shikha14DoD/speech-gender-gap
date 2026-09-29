"""
Latvia -- VIDEO route (Andris Kulbergs).

No official Latvian government YouTube channel was found for the Prime
Minister (mk.gov.lv has no video section of its own). Speeches exist on
YouTube from three kinds of uploader, in descending order of how "official"
they are:
  1. His own channel ("Andris Kulbergs", handle @andriskulbergsapvienotaiss8040
     -- named for his party, Apvienotais Saraksts / United List) -- he
     uploads his own remarks himself.
  2. The event organiser's own channel (e.g. LATO / Latvian Transatlantic
     Organisation for a Riga Conference closing address, NATO's own channel
     for a NATO HQ joint appearance) -- a first-party recording of the event,
     just not uploaded by the Latvian government.
  3. Third-party news channels (DRM News, DWS News, APT) re-uploading a
     press conference or public remarks.

Candidates below were found via web search (this site has no browsable
"speeches" listing to crawl) and verified individually (real duration,
correct speaker, date in range) before use, the same practice as the
Marshall Islands and Micronesia scrapers' hand-checked source lists.

Cross-checked against the TEXT route's mk.gov.lv press-feed rows
(scraper_latvia.py) by date + topic: one video (the 20 August Riga border-
control appearance) covers the same event as an existing text row and is
DROPPED here rather than duplicated -- the text row stays because this
video's Latvian-language transcript would need machine translation anyway,
while the video versions kept below are either English-spoken or clearly not
already covered in text.
"""

import glob
import os
import re
import tempfile
import time
import datetime as dt
from typing import List, Optional

from src.utils import clean_text, Speech
from src.text_processing import classify_as_speech, classify_content_type, in_date_range

os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + r"C:\nvm4w\nodejs"
import yt_dlp  # noqa: E402

YDL_COMMON = {"quiet": True, "no_warnings": True, "skip_download": True, "noprogress": True,
              "js_runtimes": {"node": {}}, "remote_components": ["ejs:github"], "ignoreerrors": True}

# (video id, uploader tier note) -- the 20 Aug border-control appearance
# (-pT6fWcanJY) is deliberately excluded: same event as an existing text row.
_CANDIDATES = [
    ("FMVcMkV0Izc", "third-party news re-upload (DRM News)"),
    ("CAfk9xRA3xI", "the event organiser's own channel (LATO / Latvian Transatlantic Organisation)"),
    ("o16qXjm_Qi4", "third-party news re-upload (APT)"),
    ("LEH9UN2g6i0", "third-party news re-upload (DWS News)"),
    ("fiDIP2FVPlM", "NATO's own channel (joint appearance with the NATO Secretary General)"),
    ("Qmo80F8aTdg", "his own YouTube channel"),
]


def _ydl(opts):
    o = dict(YDL_COMMON)
    o.update(opts)
    return yt_dlp.YoutubeDL(o)


def _spoken_language(info: dict) -> str:
    for k in (info.get("automatic_captions") or {}):
        if k.endswith("-orig"):
            return k[:-5].split("-")[0]
    return (info.get("language") or "?").split("-")[0]


def _vtt_to_text(vtt: str) -> str:
    lines = []
    for ln in vtt.splitlines():
        ln = ln.strip()
        if (not ln or ln == "WEBVTT" or ln.startswith(("Kind:", "Language:", "NOTE"))
                or "-->" in ln or re.match(r"^\d+$", ln)):
            continue
        ln = re.sub(r"<[^>]+>", "", ln)
        ln = re.sub(r"&nbsp;", " ", ln)
        if lines and lines[-1] == ln:
            continue
        lines.append(ln)
    return clean_text(" ".join(lines))


def _caption(video_id: str, lang: str) -> str:
    for attempt in range(3):
        tmp = tempfile.mkdtemp(prefix="lvcap_")
        try:
            with _ydl({"writeautomaticsub": True, "writesubtitles": False,
                       "subtitleslangs": [lang], "subtitlesformat": "vtt/best",
                       "outtmpl": os.path.join(tmp, "%(id)s.%(ext)s")}) as y:
                y.download([f"https://www.youtube.com/watch?v={video_id}"])
            files = glob.glob(os.path.join(tmp, f"*.{lang}*.vtt")) or glob.glob(os.path.join(tmp, "*.vtt"))
            if files:
                with open(files[0], encoding="utf-8", errors="ignore") as fh:
                    txt = _vtt_to_text(fh.read())
                if len(txt) > 200:
                    return txt
        except Exception:
            pass
        finally:
            for f in glob.glob(os.path.join(tmp, "*")):
                try:
                    os.remove(f)
                except OSError:
                    pass
            try:
                os.rmdir(tmp)
            except OSError:
                pass
        time.sleep(4 * (attempt + 1))
    return ""


def parse_latvia_video(leader_config: dict, start_date: str, end_date: str,
                       limit: Optional[int] = None) -> List[Speech]:
    print("== Latvia -- video (his own channel, event organisers, third-party news) ==")
    speeches: List[Speech] = []
    for vid, provenance in _CANDIDATES:
        with _ydl({}) as y:
            info = y.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
        if not info:
            continue
        upload = info.get("upload_date")
        date_iso = f"{upload[:4]}-{upload[4:6]}-{upload[6:8]}" if upload else None
        if not date_iso or not in_date_range(date_iso, start_date, end_date):
            continue
        lang = _spoken_language(info)
        if lang not in ("en", "lv"):
            continue
        text = _caption(vid, lang)
        if len(text) < 400:
            continue
        title = clean_text(info.get("title") or "")
        speeches.append(Speech(
            country=leader_config["country"], leader=leader_config["leader"], role=leader_config["role"],
            date=date_iso, title=title, full_text=text,
            language="English" if lang == "en" else "Latvian",
            source_url=f"https://www.youtube.com/watch?v={vid}",
            likely_speech=classify_as_speech(title), content_type=classify_content_type(title),
            notes=(f"Video source, {provenance}. Auto-generated speech-recognition caption; "
                   "not verbatim -- punctuation and some words may be wrong." +
                  (" Spoken in English (native ASR)." if lang == "en" else
                   " Latvian speech-recognition caption kept for translation "
                   "(translate_deepl.py --source LV).")),
        ))
        time.sleep(1)
        if limit and len(speeches) >= limit:
            break
    print(f"  {len(speeches)} kept before dedupe")
    return _dedupe(speeches)


def _dedupe(speeches: List[Speech]) -> List[Speech]:
    """Two channels covered the same 17 June NATO HQ press point with
    Kulbergs from different starting points -- 40% word overlap confirmed by
    reading both openings. Keep the longer/fuller recording per same-day
    overlap, same principle as the Thailand video route."""
    def words(t):
        return set(re.findall(r"[a-z]{5,}", t.lower()))
    kept: List[Speech] = []
    for s in sorted(speeches, key=lambda s: -len(s.full_text)):
        ws = words(s.full_text)
        dup = False
        for k in kept:
            if s.date == k.date:
                wk = words(k.full_text)
                if ws and wk and len(ws & wk) / len(ws | wk) >= 0.35:
                    print(f"  [dedupe] dropping {s.title[:50]!r} as a shorter cut of {k.title[:50]!r}")
                    dup = True
                    break
        if not dup:
            kept.append(s)
    return sorted(kept, key=lambda s: s.date)
