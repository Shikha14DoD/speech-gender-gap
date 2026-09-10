"""
Tanzania -- VIDEO route.  State House (Ikulu) YouTube channel
`@ikulutanzania255`: heavy coverage of President Samia Suluhu Hassan's
speeches, plus event coverage, interviews and news features.

The channel is very large (~2,900 uploads), so -- per the project scope
choice -- this route keeps only videos whose TITLE marks a full address
(`HOTUBA YA ...`, `SPEECH BY ...`, `STATEMENT BY ...`, `... REMARKS`,
`ADDRESSING THE NATION`, `SALAMU ZA MWAKA MPYA`, ...).  Filtering is done
on the cheap flat channel listing first; only the survivors get a full
metadata extract + caption download.

The speeches are in Swahili with no manual captions; YouTube
auto-generates Swahili speech-recognition captions and offers them
machine-translated to English.  This scraper pulls that English
auto-caption via yt-dlp -- rough (no punctuation, ASR + MT errors),
usable for thematic / word-frequency analysis only, NOT verbatim.  Every
row says so in `notes`.

Companion: `scraper_tanzania.py` (text) and `merge_tanzania.py`.
"""

import os
import re
import glob
import time
import tempfile
import datetime as dt
from typing import List, Optional

from src.utils import clean_text, Speech
from src.text_processing import in_date_range, classify_as_speech, classify_content_type
from src.translate_helper import translate_to_english

# yt-dlp needs a JS runtime for YouTube; node ships with the machine
os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + r"C:\nvm4w\nodejs"
import yt_dlp  # noqa: E402

CHANNEL = "https://www.youtube.com/@ikulutanzania255"
YDL_COMMON = {"quiet": True, "no_warnings": True, "skip_download": True,
              "noprogress": True, "js_runtimes": {"node": {}}, "ignoreerrors": True}

MAJALIWA_END = "2025-11-13"
MIN_DURATION = 240

# title marks a full prepared address / statement
_SPEECH_TITLE = re.compile(
    r"\bhotuba\b|\bkhutba\b|speech by|statement by|keynote|key ?note|"
    r"full speech|acceptance speech|welcom(?:e|ing) remarks|"
    r"\bremarks (?:by|for|at|during)|address(?:ing)?(?: the| to)?"
    r"(?: the)? (?:nation|citizens|parliament|general assembly|summit)|"
    r"salamu za mwaka mpya|new year (?:message|address|greetings)|"
    r"state of the nation",
    re.I,
)
# drop even when the title matched
_NON_SPEECH_CUE = re.compile(
    r"\bsong\b|\bwimbo\b|\bnyimbo\b|anthem|wimbo wa taifa|trailer|promo|teaser|"
    r"theme (?:song|music)|music video|\bmakala\b|documentary|full video:? *$",
    re.I,
)

_TITLE_DATE = re.compile(
    r"\|\s*(\d{1,2})\s+([A-Za-z]{3,})\.?,?\s+(\d{4})"          # | 13 AUGUST, 2026
    r"|\|\s*([A-Za-z]{3,})\.?\s+(\d{1,2}),?\s+(\d{4})",        # | AUGUST 13, 2026
)
_MONTHS = {m[:3].lower(): i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}
# Swahili month names occasionally appear
_MONTHS.update({"jan": 1, "feb": 2, "mac": 3, "apr": 4, "mei": 5, "jun": 6,
                "jul": 7, "ago": 8, "sep": 9, "okt": 10, "nov": 11, "des": 12})


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


def _title_date(title: str) -> Optional[str]:
    m = _TITLE_DATE.search(title)
    if not m:
        return None
    if m.group(1):
        d, mon, y = m.group(1), m.group(2), m.group(3)
    else:
        mon, d, y = m.group(4), m.group(5), m.group(6)
    mo = _MONTHS.get(mon[:3].lower())
    if not mo:
        return None
    try:
        return dt.date(int(y), mo, int(d)).isoformat()
    except ValueError:
        return None


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


def _english_caption(video_id: str) -> str:
    """Download YouTube's English (auto-translated) auto-caption as plain
    text via yt-dlp (it retries + rotates player clients)."""
    for attempt in range(3):
        tmp = tempfile.mkdtemp(prefix="tzcap_")
        try:
            with _ydl({"writeautomaticsub": True, "writesubtitles": False,
                       "subtitleslangs": ["en", "en-orig", "sw-en", "a.en"],
                       "subtitlesformat": "vtt/srv3/best",
                       "outtmpl": os.path.join(tmp, "%(id)s.%(ext)s")}) as y:
                y.download([f"https://www.youtube.com/watch?v={video_id}"])
            files = (glob.glob(os.path.join(tmp, "*.en.vtt"))
                     or glob.glob(os.path.join(tmp, "*.en*.vtt"))
                     or glob.glob(os.path.join(tmp, "*.vtt")))
            if files:
                with open(files[0], encoding="utf-8", errors="ignore") as fh:
                    txt = _vtt_to_text(fh.read())
                if len(txt) > 60:
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


def _english_title(title: str) -> str:
    if not re.search(r"[a-z]", title, re.I) or _looks_swahili(title):
        try:
            tr = translate_to_english(title, "sw") or ""
        except Exception:
            tr = ""
        if tr and "TRANSLATION FAILED" not in tr:
            return clean_text(tr)
    return title


_SW_WORDS = re.compile(r"\b(rais|hotuba|wakati|katika|wa|ya|na|kwa|akizindua|"
                       r"akifungua|mkoani|sherehe|maadhimisho|kitaifa)\b", re.I)


def _looks_swahili(t: str) -> bool:
    return len(_SW_WORDS.findall(t)) >= 2


def _which_leader(date: Optional[str], title: str, desc: str):
    blob = f"{title}\n{desc}".lower()
    if re.search(r"waziri mkuu|prime minister|majaliwa|nchemba", blob):
        if date and date >= MAJALIWA_END:
            return "Mwigulu Nchemba", "Prime Minister"
        return "Kassim Majaliwa", "Prime Minister"
    return "Samia Suluhu Hassan", "President"


def parse_tanzania_video(leader_config: dict, start_date: str, end_date: str,
                         limit: Optional[int] = None) -> List[Speech]:
    print("== Tanzania -- video (Ikulu YouTube, English auto-caption) ==")
    entries = _list_channel()
    cand = [e for e in entries
            if _SPEECH_TITLE.search(e.get("title") or "")
            and not _NON_SPEECH_CUE.search(e.get("title") or "")]
    print(f"  {len(entries)} channel videos -> {len(cand)} speech-titled candidates")

    speeches: List[Speech] = []
    stats = {"short": 0, "not_speech": 0, "no_caption": 0, "out_of_range": 0, "meta_fail": 0}
    by: dict = {}

    for i, ent in enumerate(cand, 1):
        vid = ent["id"]
        if i % 20 == 0:
            print(f"  [{i}/{len(cand)}] kept={len(speeches)} "
                  f"no_caption={stats['no_caption']} oor={stats['out_of_range']}")
        try:
            with _ydl({}) as y:
                v = y.extract_info(f"https://www.youtube.com/watch?v={vid}",
                                   download=False)
        except Exception:
            v = None
        if not v:
            stats["meta_fail"] += 1
            continue

        title = clean_text(v.get("title") or ent.get("title") or "")
        desc = clean_text((v.get("description") or "")[:600])
        dur = v.get("duration") or 0
        up = v.get("upload_date")
        date = (f"{up[:4]}-{up[4:6]}-{up[6:]}" if up and len(up) == 8
                else _title_date(title))

        if _NON_SPEECH_CUE.search(f"{title}\n{desc}"):
            stats["not_speech"] += 1
            continue
        if dur and dur < MIN_DURATION:
            stats["short"] += 1
            continue
        if not in_date_range(date, start_date, end_date):
            stats["out_of_range"] += 1
            continue

        cap = _english_caption(vid)
        if len(cap) < 200:
            stats["no_caption"] += 1
            if not dur or not (600 <= dur <= 9000):
                continue
            cap = ("[NO ENGLISH AUTO-CAPTION AVAILABLE FOR THIS VIDEO -- "
                   "the audio is Swahili; not recoverable via this route]")

        leader, role = _which_leader(date, title, desc)
        title_en = _english_title(title)

        speeches.append(Speech(
            country="Tanzania",
            leader=leader,
            role=role,
            date=date,
            title=title_en,
            full_text=cap,
            language="Swahili",
            source_url=f"https://www.youtube.com/watch?v={vid}",
            likely_speech=classify_as_speech(title_en),
            content_type=classify_content_type(title_en),
            notes=(f"VIDEO. Transcript is YouTube's automatic Swahili "
                   f"speech-recognition, auto-translated to English by YouTube "
                   f"-- no punctuation, machine-translation errors, suitable for "
                   f"thematic/word-frequency analysis only, NOT verbatim. "
                   f"Original video title (Swahili): {title!r}. "
                   f"Duration {dur // 60}m. Source: Ikulu YouTube channel."),
        ))
        by[leader] = by.get(leader, 0) + 1
        if limit and len(speeches) >= limit:
            break

    print(f"\n  Tanzania video done: {len(speeches)} kept {by} | short={stats['short']} "
          f"not_speech={stats['not_speech']} no_caption={stats['no_caption']} "
          f"out_of_range={stats['out_of_range']} meta_fail={stats['meta_fail']}")
    return speeches
