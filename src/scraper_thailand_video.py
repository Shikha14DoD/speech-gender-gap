"""
Thailand -- VIDEO route (Srettha Thavisin, Anutin Charnvirakul).

Source: the Thai government's own official YouTube channel, "ไทยคู่ฟ้า
ทำเนียบรัฐบาล" (Thai Khu Fah, Government House), handle @thaigovernment. This
is NOT the same as NBT World (the government's English-language TV channel,
which only posts 2-3 minute news clips about the PM) -- this channel records
full events, including the PM's own keynote speeches, in whichever language
he actually spoke (many are in English).

Candidates are filtered on the cheap flat channel listing first (title
carries a Thai speech-marker word: ปาฐกถา/สุนทรพจน์/ถ้อยแถลง/อภิปรายทั่วไป
"General Debate", or duration ≥5 minutes), then each survivor's real metadata
and caption are fetched. A few early full-scan attempts against a much larger,
noisier candidate set (third-party news re-uploads found via keyword search)
made yt-dlp hang indefinitely on a handful of videos (a live-in-progress
stream, an age-gated one); those aren't used here, but the timeout guard is
kept as a safety net in case this channel ever produces one too.

Language handling (same principle as Tanzania's video route): don't assume
the audio is Thai. YouTube's recogniser marks the language it actually heard
with a `<lang>-orig` key in `automatic_captions`; a video recognised in
neither Thai nor English is dropped as unreliable ASR. For Thai-language
speeches the Thai auto-caption is kept as `original_text` (the translation
pipeline's `translate_deepl.py --source TH` supports it directly), not
YouTube's own rough auto-translated English track -- a machine translation of
a machine transcription is two error-prone steps instead of one.
"""

import concurrent.futures
import glob
import os
import re
import tempfile
import time
import datetime as dt
from typing import List, Optional

from src.utils import clean_text, Speech
from src.text_processing import in_date_range, classify_as_speech, classify_content_type

os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + r"C:\nvm4w\nodejs"
import yt_dlp  # noqa: E402

CHANNEL = "https://www.youtube.com/@thaigovernment/videos"
YDL_COMMON = {"quiet": True, "no_warnings": True, "skip_download": True, "noprogress": True,
              "js_runtimes": {"node": {}}, "remote_components": ["ejs:github"], "ignoreerrors": True}
MIN_DURATION = 300      # 5 minutes -- this channel's clips are already curated
                        # (event recordings, not random news reactions), so a
                        # lower floor than the third-party route is safe
MAX_DURATION = 5400     # 90 minutes -- guards against a stray marathon livestream
CHANNEL_PLAYLISTEND = 1200     # newest-first; the channel is very active, so
                               # this comfortably covers back past 2024-01-01
                               # without paying for the full multi-year history

_SPEECH_TITLE = re.compile(r"ปาฐกถา|กล่าวสุนทรพจน์|กล่าวคำปราศรัย|กล่าวถ้อยแถลง|"
                           r"General Debate|อภิปรายทั่วไป", re.I)

# Tenures (see scraper_thailand.py) -- Paetongtarn's window is explicitly out
# of scope for this batch, same rule as the text route.
_TENURES = [
    ("2023-08-22", "2024-08-14", "Srettha Thavisin"),
    ("2024-08-15", "2025-09-06", None),
    ("2025-09-07", "2099-12-31", "Anutin Charnvirakul"),
]


def _with_timeout(fn, timeout_s, *args, **kwargs):
    """Safety net: run a yt-dlp call in its own one-shot worker thread and
    give up after `timeout_s` rather than letting one bad video stall the
    whole scrape (observed on a different, noisier candidate set -- kept
    here in case this channel ever serves up a live-in-progress video)."""
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    fut = ex.submit(fn, *args, **kwargs)
    try:
        return fut.result(timeout=timeout_s)
    except concurrent.futures.TimeoutError:
        print(f"    [warn] timed out after {timeout_s}s, skipping")
        return None
    finally:
        ex.shutdown(wait=False)


def _ydl(opts):
    o = dict(YDL_COMMON)
    o.update(opts)
    return yt_dlp.YoutubeDL(o)


_LISTING_CACHE = "data/processed/thailand_video_channel_listing.json"


def _list_channel() -> List[dict]:
    # the flat listing of ~3000 videos is slow (paginated through YouTube's
    # API, several minutes) -- cache it on disk so a later rerun (e.g. after
    # fixing a bug downstream) doesn't have to pay that cost again
    if os.path.exists(_LISTING_CACHE):
        import json
        with open(_LISTING_CACHE, encoding="utf-8") as f:
            ents = json.load(f)
        print(f"  channel listing: {len(ents)} videos (from cache)")
        return ents
    try:
        with _ydl({"extract_flat": True, "playlistend": CHANNEL_PLAYLISTEND}) as y:
            info = y.extract_info(CHANNEL, download=False)
    except Exception as e:
        print(f"  [warn] channel listing failed: {e}")
        return []
    ents = [{"id": e["id"], "title": e.get("title"), "duration": e.get("duration")}
            for e in (info.get("entries") or []) if e and e.get("id")]
    print(f"  channel listing: {len(ents)} videos")
    import json
    with open(_LISTING_CACHE, "w", encoding="utf-8") as f:
        json.dump(ents, f)
    return ents


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
        tmp = tempfile.mkdtemp(prefix="thcap_")
        try:
            def _dl():
                with _ydl({"writeautomaticsub": True, "writesubtitles": False,
                           "subtitleslangs": [lang], "subtitlesformat": "vtt/best",
                           "outtmpl": os.path.join(tmp, "%(id)s.%(ext)s")}) as y:
                    y.download([f"https://www.youtube.com/watch?v={video_id}"])
            _with_timeout(_dl, 90)
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
        time.sleep(5 * (attempt + 1))
    return ""


def _which_leader(date_iso: Optional[str], title: str) -> Optional[str]:
    if re.search(r"เศรษฐา|srettha", title, re.I):
        return "Srettha Thavisin"
    if re.search(r"อนุทิน|anutin", title, re.I):
        return "Anutin Charnvirakul"
    if not date_iso:
        return None
    for start, end, name in _TENURES:
        if start <= date_iso <= end:
            return name
    return None


def _dedupe(speeches: List[Speech]) -> List[Speech]:
    """Guard against the same event being uploaded twice by this channel."""
    def words(t):
        return set(re.findall(r"[ก-๙a-z]{4,}", t.lower()))
    kept: List[Speech] = []
    for s in sorted(speeches, key=lambda s: -len(s.full_text)):
        ws = words(s.full_text)
        dup = False
        for k in kept:
            try:
                d = abs((dt.date.fromisoformat(s.date) - dt.date.fromisoformat(k.date)).days)
            except ValueError:
                d = 99
            wk = words(k.full_text)
            if d <= 1 and ws and wk and len(ws & wk) / len(ws | wk) >= 0.6:
                dup = True
                break
        if not dup:
            kept.append(s)
    return sorted(kept, key=lambda s: s.date)


def parse_thailand_video(leader_config: dict, start_date: str, end_date: str,
                         limit: Optional[int] = None) -> List[Speech]:
    print("== Thailand -- video (official @thaigovernment YouTube channel) ==")
    entries = _list_channel()
    candidates = [e for e in entries if _SPEECH_TITLE.search(e.get("title") or "")]
    print(f"  {len(candidates)} speech-titled candidates")

    speeches: List[Speech] = []
    stats = {"short": 0, "meta_fail": 0, "wrong_lang": 0, "no_caption": 0, "out_of_range": 0}
    for i, ent in enumerate(candidates, 1):
        vid = ent["id"]
        dur = ent.get("duration") or 0
        if dur < MIN_DURATION or dur > MAX_DURATION:
            stats["short"] += 1
            continue

        def _extract():
            with _ydl({}) as y:
                return y.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
        try:
            v = _with_timeout(_extract, 60)
        except Exception:
            v = None
        if not v:
            stats["meta_fail"] += 1
            continue
        upload = v.get("upload_date")
        date_iso = f"{upload[:4]}-{upload[4:6]}-{upload[6:8]}" if upload else None
        if not date_iso or not in_date_range(date_iso, start_date, end_date):
            stats["out_of_range"] += 1
            continue
        title = clean_text(v.get("title") or "")
        who = _which_leader(date_iso, title)
        if who is None:
            continue
        lang = _spoken_language(v)
        if lang not in ("th", "en"):
            stats["wrong_lang"] += 1
            continue
        text = _caption(vid, lang)
        if len(text) < 400:
            stats["no_caption"] += 1
            continue
        notes = ("Sourced from the Thai government's official YouTube channel "
                 "(\"ไทยคู่ฟ้า ทำเนียบรัฐบาล\" / @thaigovernment, Government House). "
                 "Auto-generated speech-recognition caption; not verbatim -- "
                 "punctuation and some words may be wrong.")
        speeches.append(Speech(
            country=leader_config["country"], leader=who, role=leader_config["role"],
            date=date_iso, title=title, full_text=text,
            language="English" if lang == "en" else "Thai",
            source_url=f"https://www.youtube.com/watch?v={vid}",
            likely_speech=classify_as_speech(title), content_type=classify_content_type(title),
            notes=notes + (" Spoken in English (native ASR, not translated)." if lang == "en" else
                          " Thai speech-recognition caption kept for translation "
                          "(translate_deepl.py --source TH), not YouTube's own rough "
                          "auto-translated English track."),
        ))
        if i % 15 == 0:
            print(f"  [{i}/{len(candidates)}] kept={len(speeches)} "
                  f"short={stats['short']} wrong_lang={stats['wrong_lang']} "
                  f"no_caption={stats['no_caption']} oor={stats['out_of_range']}")
        if limit and len(speeches) >= limit:
            break

    print(f"  done: {len(speeches)} kept before dedupe, {stats}")
    return _dedupe(speeches)
