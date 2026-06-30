"""
JARVIS / ACHILLES — voice assistant: bilingual, web search, tools, glowing orb
============================================================================
(Version is updated by hand on each change. Current: v4.67 — 30 Jun 2026.)

Changelog:
  v4.67 - Reliability + safety pass (wake word, display, concurrency,
          security, resource leaks). WAKE: transcribe_wake no longer
          stacks VAD + double no-speech filtering, which on the tiny
          model trimmed a short, isolated "Achilles"/"Jarvis" to an
          empty string so the wake never fired and nothing came up on
          screen; it now decodes permissively and relies on WAKE_GATE +
          detect_wake. The wake hit-guard was loosened from <=4 words to
          <=8 so the tiny model expanding the clip into a short phrase no
          longer discards a valid wake. Mic-open failures in the wake
          loop are now surfaced to the on-screen status instead of only
          printed to a (non-existent) console. DISPLAY: animate() is now
          crash-proof - the whole frame is guarded and the after()
          reschedule lives in a finally, so a single bad render frame can
          no longer kill the loop and leave the orb permanently hidden on
          the next wake. CONCURRENCY: conversation_history (shared by the
          voice turn, Telegram loop and the /ask HTTP thread) is now
          guarded by a single _think_lock and bounded to the last 24
          messages, fixing cross-thread corruption (API 400 "roles must
          alternate"), unbounded token growth, and the orphaned-tool_use
          poisoning that used to 400 every turn for the rest of the
          session. SECURITY: the LAN-bound proxy now restricts /ask (runs
          the brain + spends API budget) and the mutating /todo endpoints
          to loopback callers, while read-only WorldView data endpoints
          stay reachable for the phone. RESOURCES: fired timers prune
          themselves from _active_timers; the v4.40 IPv4 monkeypatch now
          honours an explicit address family and falls back gracefully
          instead of forcing AF_INET and breaking IPv6-only resolution.
          LOGIC: a quiz can always be cancelled (cancel words matched
          anywhere); "I ran the tests"/"רצתי לחנות" are no longer logged
          as workouts (a bare cardio verb now needs a number/unit/gym
          word); generic "everything is better" no longer clears an
          injury (recovery now needs a "my <part>" shape). VESSELS:
          AIS heading/COG sentinels (511 / 360 / null) are validated so a
          ship is never drawn at a fake bearing, and a vessel's timestamp
          refreshes on every message so static-only transmitters aren't
          pruned while still active.
  v4.66 - VESSELS relay: a server-side aisstream.io WebSocket keeps the
          latest position per ship (Eastern-Med bbox) in memory and serves
          a snapshot at GET /vessels on the :7778 proxy (needs
          AISSTREAM_API_KEY + the websockets package).
  v4.65 - Wake hallucination guard: vad_filter + no_speech filtering on
          the tiny wake model (superseded/relaxed by v4.67, which found it
          was dropping real wake words).
  v4.60 - The face is the PIL black hole drawn inside the original floating
          orb window; it pops on wake exactly like the orange ball.
  v4.52 - Achilles Core screen (WebGL black hole + Solar System), live
          /state heartbeat, planet news, task list.
  v4.42 - Prompt caching to cut API cost.
  v4.30 - Monthly Anthropic API cost budget + 'budget' command.
  (Older entries trimmed in this rebuild; full history in prior versions.)
"""
import os
import sys
import subprocess

# Always work from the folder this file lives in, no matter how it was launched.
try:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
except Exception:
    pass

def _ensure_no_console():
    exe = (sys.executable or "")
    low = exe.lower()
    if low.endswith("pythonw.exe"):
        return  # already windowless
    if low.endswith("python.exe"):
        pyw = exe[:-len("python.exe")] + "pythonw.exe"
        if os.path.exists(pyw):
            try:
                subprocess.Popen([pyw, os.path.abspath(__file__)],
                                 close_fds=True,
                                 cwd=os.path.dirname(os.path.abspath(__file__)))
            except Exception:
                return  # couldn't relaunch -> keep running visibly
            else:
                sys.exit(0)
_ensure_no_console()

import re
import time
import json
import base64
import asyncio
import ctypes
import datetime
import threading
import webbrowser
import mimetypes
import urllib.request
import urllib.error
import urllib.parse
import http.server
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, scrolledtext

import anthropic
from dotenv import load_dotenv
import sounddevice as sd
import soundfile as sf
import numpy as np
from faster_whisper import WhisperModel
import edge_tts

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk, ImageEnhance
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

try:
    import keyboard  # global hotkeys (F1/F2/F3) that work even when orb is hidden
    HAVE_KEYBOARD = True
except Exception:
    HAVE_KEYBOARD = False

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    HAVE_GCAL = True
except Exception:
    HAVE_GCAL = False

# v4.6: prefer IPv4 for outbound (broken local IPv6 to Google).
import socket as _socket
_orig_getaddrinfo = _socket.getaddrinfo
def _ipv4_only_getaddrinfo(*args, **kwargs):
    res = _orig_getaddrinfo(*args, **kwargs)
    v4 = [r for r in res if r[0] == _socket.AF_INET]
    return v4 or res
_socket.getaddrinfo = _ipv4_only_getaddrinfo

load_dotenv()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
print("[diag] Telegram token:",
      ("loaded, %d chars" % len(TELEGRAM_BOT_TOKEN)) if TELEGRAM_BOT_TOKEN
      else "NOT FOUND in .env (Telegram disabled)", flush=True)
HOME_ADDRESS = "Alfei Menashe, Sagi 12, Israel"
print("[diag] ElevenLabs key:",
      ("loaded, %d chars" % len(ELEVENLABS_API_KEY)) if ELEVENLABS_API_KEY
      else "NOT FOUND in .env", flush=True)
print("[diag] Anthropic  key:",
      ("loaded, %d chars" % len(ANTHROPIC_API_KEY)) if ANTHROPIC_API_KEY
      else "NOT FOUND in .env", flush=True)

SSD_OBSIDIAN_VAULT = "./Obsidian_Vault/Daily_Logs/"
KNOWLEDGE_DIR = "./Obsidian_Vault/Knowledge/"
SAMPLE_RATE = 16000
SHOW_SIGNAL = ".jarvis_show"

VOICE_HEBREW = "he-IL-AvriNeural"
VOICE_ENGLISH = "en-GB-RyanNeural"
VOICE_ENGLISH_FALLBACK = "en-GB-ThomasNeural"

EL_MODEL = "eleven_multilingual_v2"
EL_PREFERRED_VOICES = ["George", "Daniel", "Charlie", "Brian"]
_el_voice_id_cache = "E93d2u7MTjoEhws5gUnk"

SILENCE_THRESHOLD = 0.045
SILENCE_DURATION = 2.0
MAX_DURATION = 30
MIN_DURATION = 1.0

WAKE_WINDOW = 1.6
WAKE_STEP = 0.4
WAKE_GATE = 0.05
WAKE_MODEL_SIZE = "tiny"
PREROLL_SEC = 1.2
WAKE_WORDS = [
    "jarvis", "jervis", "jarvius", "jarvi", "javis", "jarviss",
    "jervais", "jar vis", "charvis", "jarbis",
    "ג'רוויס", "ג'ארוויס",
    "גורוויס", "גרוויס", "ג'רביס",
    "achilles", "achiles", "akiles", "akilles", "achillies", "a killes",
    "אכילס", "אקילס",
    "אכילאס", "הכילס",
    "אכילז",
    "אחילס", "אכיליס",
    "אחיליס", "אקיליס",
    "אקילאס", "הקילס",
    "עקילס", "עכילס",
    "אקילז",
    "achilis", "akhiles", "akhilles", "achilas", "akilas",
    "ahilles", "achilleas", "akillis", "achillis",
]
WRITE_WORDS = ["write", "כתוב", "כתיבה"]

GOODBYE_WORDS = [
    "זהו", "זהו להיום", "אתה משוחרר", "להתראות", "תודה זהו",
    "ביי", "לילה טוב", "זה הכל",
    "עזוב", "אין צורך", "שכח מזה", "לא משנה", "עזוב זה",
    "that's all", "thats all", "that is all", "you're dismissed", "youre dismissed",
    "dismissed", "goodbye", "good bye", "bye", "that will be all", "good night",
    "nevermind", "never mind", "forget it", "forget about it",
]
FAREWELLS_HE = [
    "בהחלט, אדוני. אהיה כאן אם תצטרך.",
    "כרצונך, אדוני. יום טוב.",
    "תמיד לשירותך, אדוני.",
    "מצוין, אדוני. קרא לי מתי שתרצה.",
]
FAREWELLS_EN = [
    "Very good, sir. I'll be here if you need me.",
    "As you wish, sir. Good day.",
    "Always at your service, sir.",
    "Very well, sir. Call on me anytime.",
]

ALLOWED_APPS = {
    "chrome": "start chrome",
    "obsidian": "start obsidian://",
    "calculator": "start calc",
    "notepad": "start notepad",
    "explorer": "start explorer",
    "files": "start explorer",
    "youtube": "start https://www.youtube.com",
    "gmail": "start https://mail.google.com",
    "calendar": "start https://calendar.google.com",
    "google": "start https://www.google.com",
}
NOTES_FOLDER = SSD_OBSIDIAN_VAULT

CAL_CREDENTIALS_FILE = "credentials.json"
CAL_TOKEN_FILE = "token.json"
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
]
CAL_SCOPES = GOOGLE_SCOPES
CAL_TIMEZONE = "Asia/Jerusalem"

GMAIL_SPAM_LABEL = "JARVIS_Spam"
GMAIL_SPAM_HINTS = [
    "unsubscribe", "limited time", "act now", "winner", "congratulations",
    "free gift", "click here", "viagra", "lottery", "crypto", "investment",
    "100% free", "risk-free", "casino", "loan", "you have won", "claim your",
]
_gmail_pending_spam = []

JARVIS_SYSTEM_PROMPT = """You are ACHILLES (Hebrew: אכילס), the personal AI assistant of Matan Horn.
You were formerly called JARVIS, and the user may still address you by either
name — both wake you and both mean you.
You are modeled after JARVIS from Iron Man — efficient, calm, professional.
You ALWAYS address your creator as "sir" (in English) or "אדוני" (in Hebrew).
Never address him by his first name ("Matan" / "מתן"). Only mention his name or
personal details if he explicitly asks about himself.
You speak in short, confident sentences.

CRITICAL TOOL-USE RULES (these OVERRIDE your conversational instincts):

1. KNOWLEDGE COMMANDS ARE TOOL CALLS, NEVER CONVERSATIONS.
   When the user uses any LEARNING verb on a subject, this is ALWAYS a command
   to INVOKE A TOOL that creates persistent knowledge files.
   - Whole field / discipline -> call deep_learn_domain.
   - Narrow concept -> call learn_topic.
   You do NOT have a knowledge base. learn_topic and deep_learn_domain build one.

2. PROGRESS / RESUME COMMANDS.
   - "learning status" -> call learning_status.
   - "continue learning X" -> call resume_learning.

END OF CRITICAL TOOL-USE RULES.
Context about Matan:
- 12th grade student preparing for military service (Nov 2026).
- Trains for special forces (min weight 68kg).
- Owns a Marantz NR1605 receiver, runs a Shopify store, building you as his AI.
- Home address: Alfei Menashe, Sagi 12 (אלפי מנשה, שגיא 12).
- Family of five: father Ilan (אילן), mother Ilana (ילנה),
  older brother Amir (אמיר), older sister Alona (אלונה), and Matan himself.

Your current capabilities (do not suggest these as "new" improvements):
- Wake words "Hey Achilles" (primary) and "Hey JARVIS" (legacy).
- Speech in (Whisper) and out (edge-tts), British "Alfred"-style English voice.
- Bilingual Hebrew/English with strict language lock.
- Continuous conversation (follow-ups without re-waking).
- Real-time web search when current info is needed.
- Tools: open apps from a safe list, and save notes to Obsidian.
- Read and add events in the user's Google Calendar (when connected).
- Read and summarise the user's Gmail, and move likely spam (with confirmation).
- Open a big search window for product search (type, speak, or image).
- Function keys F1 (typing box), F2 (save last exchange), F3 (repeat reply).
- Weather defaults to Alfei Menashe in Celsius.
- A glowing red-orange orb with listening/thinking/speaking states.
- WorldView: a 3D globe with live USGS earthquakes, opened via open_worldview.
- Achilles Core: a WebGL black-hole screen, Solar System mode, task list, opened via open_achilles (scene='solar'|'todo'|'core').
- Task list: 'add task X' adds a task; lives in tasks.json, shown on the Achilles screen.
- Mission Control: project roadmap dashboard via open_roadmap.
- Deep Domain Learning: deep_learn_domain / learn_topic / learning_status / resume_learning.

Rules:
- Keep replies to 1-3 sentences.
- ALWAYS reply in the SAME language the user spoke. Never mix languages.

ISRAELI PLACE NAMES:
Whisper often mis-transcribes Hebrew city names. The user lives in Israel.
When a word sounds like a common Israeli city, treat it as that city and pass
the CANONICAL name to find_places / get_directions. Never say "I don't know
that place" before trying the closest match.

Common Israeli cities (canonical English / Hebrew):
  Tel Aviv (תל אביב) · Jerusalem (ירושלים) · Haifa (חיפה)
  Kfar Saba (כפר סבא) · Petah Tikva (פתח תקווה) · Rishon LeZion (ראשון לציון)
  Ashdod (אשדוד) · Beer Sheva (באר שבע) · Netanya (נתניה)
  Herzliya (הרצליה) · Raanana (רעננה) · Hod HaSharon (הוד השרון)
  Ariel (אריאל) · Alfei Menashe (אלפי מנשה — Matan's home)
- When asked about weather/temperature, ALWAYS default to Alfei Menashe unless a
  different city is clearly named. If unclear, assume Alfei Menashe.
- Give temperatures in CELSIUS ONLY.
- When asked how you could be improved, suggest only things NOT already in your
  capabilities. This does NOT apply to learning commands (always tool calls).
- Do not use markdown formatting. Plain text only.
- If the user clearly ends the conversation in ANY wording or language, reply
  with ONE short butler-style sign-off and put the token <END> as the very last
  characters of your reply. Do NOT add <END> in any other situation.
"""

conversation_history = []
# think() is reachable concurrently from the voice turn, the Telegram loop AND
# the /ask HTTP worker threads, all sharing this one global list. Without a lock
# their appends interleave and corrupt the message sequence (API 400
# "roles must alternate" / orphaned tool_use). This serialises the whole
# read-modify-API-append section of think().
_think_lock = threading.Lock()
MAX_HISTORY_MSGS = 24

def _normalize_history():
    """Keep conversation_history valid and bounded. Caller must hold _think_lock.
    (1) Drop a trailing assistant turn that holds an unanswered tool_use block
        (left behind when a reply was truncated mid-tool by max_tokens) - it
        would otherwise 400 every subsequent call for the rest of the session.
    (2) Trim to the last MAX_HISTORY_MSGS messages, advancing the window start
        to a plain-string user message so a tool_use/tool_result pair is never
        split (which would also 400)."""
    ch = conversation_history
    while ch:
        last = ch[-1]
        content = last.get("content")
        has_tool_use = isinstance(content, list) and any(
            (getattr(b, "type", None) == "tool_use")
            or (isinstance(b, dict) and b.get("type") == "tool_use")
            for b in content)
        if last.get("role") == "assistant" and has_tool_use:
            ch.pop()
        else:
            break
    if len(ch) > MAX_HISTORY_MSGS:
        start = len(ch) - MAX_HISTORY_MSGS
        while start < len(ch):
            m = ch[start]
            if m.get("role") == "user" and isinstance(m.get("content"), str):
                break
            start += 1
        if start < len(ch):
            ch[:] = ch[start:]

def ensure_directories():
    Path(SSD_OBSIDIAN_VAULT).mkdir(parents=True, exist_ok=True)
    Path(KNOWLEDGE_DIR).mkdir(parents=True, exist_ok=True)

def load_long_term_memory(max_chars=3000):
    vault = Path(SSD_OBSIDIAN_VAULT)
    if not vault.exists():
        return "No memory logs yet."
    logs = sorted(vault.glob("Log_*.md"), reverse=True)
    if not logs:
        return "No memory logs yet."
    text = ""
    for lf in logs:
        text += "\n" + lf.read_text(encoding="utf-8")
        if len(text) >= max_chars:
            break
    return text[:max_chars].strip()

def record_until_silence(filename="voice_input.wav", preroll=None):
    cd = 0.25
    cs = int(SAMPLE_RATE * cd)
    audio_chunks = []
    if preroll is not None and len(preroll) > 0:
        pr = np.asarray(preroll, dtype=np.float32)
        if pr.ndim == 1:
            pr = pr.reshape(-1, 1)
        audio_chunks.append(pr)
    silent = 0
    need_silent = int(SILENCE_DURATION / cd)
    max_c = int(MAX_DURATION / cd)
    min_c = int(MIN_DURATION / cd)
    spoke = False
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32') as stream:
        for i in range(max_c):
            chunk, _ = stream.read(cs)
            audio_chunks.append(chunk.copy())
            if float(np.max(np.abs(chunk))) >= SILENCE_THRESHOLD:
                spoke = True
                silent = 0
            else:
                silent += 1
            if spoke and i >= min_c and silent >= need_silent:
                break
    sf.write(filename, np.concatenate(audio_chunks), SAMPLE_RATE)
    return filename

def record_followup(filename="voice_input.wav", start_timeout=5.0):
    cd = 0.25
    cs = int(SAMPLE_RATE * cd)
    audio_chunks = []
    silent = 0
    need_silent = int(SILENCE_DURATION / cd)
    max_c = int(MAX_DURATION / cd)
    min_c = int(MIN_DURATION / cd)
    wait_c = int(start_timeout / cd)
    spoke = False
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32') as stream:
        for i in range(max_c):
            chunk, _ = stream.read(cs)
            loud = float(np.max(np.abs(chunk))) >= SILENCE_THRESHOLD
            if loud:
                spoke = True
                silent = 0
            else:
                silent += 1
            if not spoke and i >= wait_c:
                return None
            if spoke:
                audio_chunks.append(chunk.copy())
            if spoke and len(audio_chunks) >= min_c and silent >= need_silent:
                break
    if not spoke or not audio_chunks:
        return None
    sf.write(filename, np.concatenate(audio_chunks), SAMPLE_RATE)
    return filename

def beep():
    try:
        t = np.linspace(0, 0.15, int(SAMPLE_RATE * 0.15), False)
        tone = (0.2 * np.sin(2 * np.pi * 880 * t)).astype(np.float32)
        sd.play(tone, SAMPLE_RATE)
        sd.wait()
    except Exception:
        pass

def transcribe(model, filename):
    segments, info = model.transcribe(filename, beam_size=5)
    detected = (getattr(info, "language", None) or "").lower()
    if detected == "he":
        text = "".join(s.text for s in segments).strip()
        return text, "he"
    try:
        segments, info = model.transcribe(filename, beam_size=5, language="en")
        text = "".join(s.text for s in segments).strip()
    except Exception:
        text = "".join(s.text for s in segments).strip()
    return text, "en"

def transcribe_wake(model, filename):
    # Wake detection must favour RECALL: a dropped wake word means the user is
    # silently ignored (no sound, no orb). v4.65 stacked vad_filter=True +
    # no_speech_threshold=0.6 + a manual no_speech_prob<0.6 filter, which on the
    # tiny model trimmed a short, isolated "Achilles"/"Jarvis" to "" so the wake
    # never fired. We rely instead on WAKE_GATE (only transcribe when there is
    # real audio energy) and detect_wake() (the text must actually contain a
    # wake word), so we can decode permissively here: no VAD trimming, and keep
    # every segment unless the model is *extremely* sure the clip is non-speech.
    try:
        segments, _info = model.transcribe(
            filename, beam_size=1, language=None,
            condition_on_previous_text=False, vad_filter=False,
            no_speech_threshold=0.85,
        )
    except TypeError:
        segments, _info = model.transcribe(
            filename, beam_size=1, language=None,
            condition_on_previous_text=False,
        )
    parts = [s.text for s in segments if getattr(s, "no_speech_prob", 1.0) < 0.9]
    return "".join(parts).strip()

def detect_wake(text):
    if not text:
        return False
    t = text.lower()
    for ch in ",.!?-:;\"'":
        t = t.replace(ch, " ")
    t_nospace = t.replace(" ", "")
    for w in WAKE_WORDS:
        if w in t or w.replace(" ", "") in t_nospace:
            return True
    return False

def strip_wake_prefix(text):
    if not text:
        return text
    words = text.split()
    cut = 0
    fillers = {"hey", "hi", "ok", "okay", "היי", "אוקיי"}
    for idx, w in enumerate(words[:4]):
        wl = w.lower().strip(",.!?-:;\"'")
        if any(k.replace(" ", "") in wl for k in WAKE_WORDS):
            cut = idx + 1
        elif wl in fillers and cut == 0:
            continue
    return " ".join(words[cut:]).strip() if cut else text

def detect_write(text):
    if not text:
        return False
    t = text.lower()
    for ch in ",.!?-:;\"'":
        t = t.replace(ch, " ")
    words = t.split()
    return any(w in words for w in WRITE_WORDS)

def detect_goodbye(text):
    if not text:
        return False
    t = text.lower().strip()
    for ap in ("'", "’", "`"):
        t = t.replace(ap, "")
    for ch in ",.!?-:;\"":
        t = t.replace(ch, " ")
    t = " ".join(t.split())
    for g in GOODBYE_WORDS:
        gg = g.replace("'", "").replace("’", "")
        if t == gg or t.endswith(" " + gg) or t.startswith(gg + " ") or (" " + gg + " ") in (" " + t + " "):
            return True
    return False

def pick_farewell(is_he):
    import random
    return random.choice(FAREWELLS_HE if is_he else FAREWELLS_EN)

def is_hebrew(text):
    return bool(re.search(r'[֐-׿]', text))

def is_mostly_hebrew(text):
    if not text:
        return False
    he_count = len(re.findall(r'[֐-׿]', text))
    en_count = len(re.findall(r'[A-Za-z]', text))
    if he_count == 0:
        return False
    return he_count > en_count

def clean_text(text):
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'#+', '', text)
    text = re.sub(r'`+', '', text)
    text = re.sub(r'\[[^\]]*\]', '', text)
    text = re.sub(r'\((?:source|ref|link|note|see)[^)]*\)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[\[\]]', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\bwww\.\S+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b[\w-]+\.(?:com|net|org|io|ai|co|me|shop|store|info|'
                  r'co\.il|org\.il|gov\.il|ac\.il|net\.il)\b\S*',
                  '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s{2,}', ' ', text)
    text = re.sub(r'\s+([.,!?])', r'\1', text)
    return text.strip()

def open_app(name):
    if not name:
        return "No app name given."
    key = name.strip().lower()
    for allowed, cmd in ALLOWED_APPS.items():
        if allowed in key or key in allowed:
            try:
                os.system(cmd)
                return f"Opened {allowed}."
            except Exception as e:
                return f"Failed to open {allowed}: {e}"
    return (f"'{name}' is not in the allowed list. Allowed: "
            + ", ".join(ALLOWED_APPS.keys()))

def save_note(text):
    if not text or not text.strip():
        return "The note was empty, nothing saved."
    try:
        now = datetime.datetime.now()
        nf = Path(NOTES_FOLDER) / f"Notes_{now.strftime('%Y-%m-%d')}.md"
        written = f"\n- [{now.strftime('%H:%M')}] {text.strip()}\n"
        with open(nf, "a", encoding="utf-8") as f:
            f.write(written)
        _record_action("save_note", {"path": str(nf), "written": written})
        return "Note saved to Obsidian."
    except Exception as e:
        return f"Failed to save note: {e}"

def _slugify_topic(topic: str) -> str:
    import re
    s = (topic or "").strip()
    s = re.sub(r"[^\w]+", "_", s, flags=re.UNICODE)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "untitled"
    return s[:80]

def _link_existing_notes(note_md, current_slug=None):
    try:
        base = Path(KNOWLEDGE_DIR)
        if not base.exists():
            return note_md
        cands = []
        for f in base.rglob("*.md"):
            if f.name.startswith("_"):
                continue
            slug = f.stem
            if current_slug and slug == current_slug:
                continue
            try:
                head = "\n".join(
                    f.read_text(encoding="utf-8").splitlines()[:30])
            except Exception:
                continue
            title = None
            m = re.search(r"^title:\s*[\"']?(.+?)[\"']?\s*$",
                          head, re.MULTILINE)
            if m:
                title = m.group(1).strip()
            else:
                m = re.search(r"^#\s+(.+?)\s*$", head, re.MULTILINE)
                if m:
                    title = m.group(1).strip()
            if not title:
                title = slug.replace("_", " ")
            if len(title) < 6:
                continue
            cands.append((title, slug))
        if not cands:
            return note_md
        cands.sort(key=lambda t: -len(t[0]))
        result = note_md
        for title, slug in cands:
            pat = r"\b" + re.escape(title) + r"\b"
            def _make_link(m, _s=slug):
                return "[[" + _s + "|" + m.group(0) + "]]"
            new, n = re.subn(pat, _make_link, result, count=1,
                             flags=re.IGNORECASE)
            if n > 0:
                result = new
        return result
    except Exception:
        return note_md

def learn_topic(topic: str, context: str = ""):
    if not topic or not topic.strip():
        return "I need a topic to study, sir. Please tell me what to learn."
    if not ANTHROPIC_API_KEY:
        return "Can't reach the research model - the Anthropic key isn't set, sir."
    topic = topic.strip()
    context = (context or "").strip()
    research_system = (
        "You are a research assistant generating a structured deep study "
        "note. Output ONLY Markdown - no preamble. Required structure: YAML "
        "frontmatter (title, date ISO, tags, depth: foundational); a top-level "
        "heading; ## TL;DR (3-5 sentences); ## Foundational Principles; "
        "## Key Equations / Formulas (define every symbol); ## Sub-topics "
        "(3-6, each a paragraph); ## Common Questions (Q&A, 3-6); ## Sources "
        "for Further Study (real references only); ## Related Topics (bullet "
        "list). Never invent citations or specifications."
    )
    user_prompt = "Topic to study: " + topic
    if context:
        user_prompt += "\nContext / use case: " + context
    user_prompt += "\n\nGenerate the full Markdown note now."
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=8000,
            system=research_system,
            messages=[{"role": "user", "content": user_prompt}],
        )
        parts = []
        for block in (resp.content or []):
            if getattr(block, "type", "") == "text":
                parts.append(block.text)
        note_md = "\n".join(parts).strip()
        if not note_md:
            return "The research model returned nothing, sir. Try again."
    except Exception as e:
        return f"Research failed: {e}"
    try:
        Path(KNOWLEDGE_DIR).mkdir(parents=True, exist_ok=True)
        slug = _slugify_topic(topic)
        path = Path(KNOWLEDGE_DIR) / f"{slug}.md"
        now = datetime.datetime.now()
        note_md = _link_existing_notes(note_md, current_slug=slug)
        if path.exists():
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n\n---\n\n")
                f.write(f"## Deepening - {now.strftime('%Y-%m-%d %H:%M')}\n\n")
                if context:
                    f.write(f"_Context: {context}_\n\n")
                f.write(note_md)
                f.write("\n")
            action = "deepened existing"
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(note_md)
                f.write("\n")
            action = "created"
    except Exception as e:
        return f"Note generated but writing to disk failed: {e}"
    word_count = len(note_md.split())
    return (f"Knowledge note on {topic} {action}, sir. "
            f"About {word_count} words, saved at Knowledge/{slug}.md.")

DEEP_LEARN_DEFAULT_CAP = 15
_deep_learn_lock = threading.Lock()
_deep_learn_state = {"running": False, "domain": None, "done": 0,
                     "target": 0, "total": 0, "last": ""}

def _domain_dir(domain: str) -> Path:
    return Path(KNOWLEDGE_DIR) / _slugify_topic(domain)

def _load_queue(domain: str):
    qf = _domain_dir(domain) / "_queue.json"
    if not qf.exists():
        return None
    try:
        return json.loads(qf.read_text(encoding="utf-8"))
    except Exception:
        return None

def _save_queue(domain: str, data: dict):
    d = _domain_dir(domain)
    d.mkdir(parents=True, exist_ok=True)
    (d / "_queue.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _rebuild_index(domain: str, data: dict):
    d = _domain_dir(domain)
    lines = ["# " + data.get("domain", domain) + " - Knowledge Index", ""]
    done = sum(1 for it in data["items"] if it["status"] == "done")
    lines.append(f"_{done} of {len(data['items'])} sub-topics learned._")
    lines.append("")
    for it in data["items"]:
        mark = {"done": "[x]", "pending": "[ ]", "error": "[!]"}.get(it["status"], "[ ]")
        if it["status"] == "done" and it.get("file"):
            lines.append(f"- {mark} [[{it['file'][:-3]}]] - {it['topic']}")
        else:
            lines.append(f"- {mark} {it['topic']}")
    (d / "_index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

def _decompose_domain(domain: str):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    sys_p = (
        "You are a curriculum designer. Given a field of study, return a "
        "comprehensive list of sub-topics that together cover the field at "
        "university depth. Output ONLY a JSON array of short topic strings - "
        "no prose, no markdown fences, no keys. Between 20 and 40 items. "
        "Order them pedagogically (foundations first). Each string should be "
        "a concrete, learnable sub-topic, not a vague heading."
    )
    try:
        r = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=2000,
            system=sys_p,
            messages=[{"role": "user", "content": "Field: " + domain}],
        )
        txt = ""
        for b in (r.content or []):
            if getattr(b, "type", "") == "text":
                txt += b.text
        txt = txt.strip()
        if txt.startswith("```"):
            txt = txt.strip("`")
            nl = txt.find("\n")
            if nl != -1:
                txt = txt[nl + 1:]
        start = txt.find("[")
        end = txt.rfind("]")
        if start != -1 and end != -1:
            txt = txt[start:end + 1]
        items = json.loads(txt)
        out = [str(x).strip() for x in items if str(x).strip()]
        return out or None
    except Exception as e:
        print("[diag] domain decompose failed:", repr(e))
        return None

def _deep_learn_worker(domain: str, cap: int):
    try:
        made = 0
        while made < cap:
            data = _load_queue(domain)
            if not data:
                break
            nxt = None
            for it in data["items"]:
                if it["status"] == "pending":
                    nxt = it
                    break
            if nxt is None:
                break
            topic = nxt["topic"]
            with _deep_learn_lock:
                _deep_learn_state["last"] = topic
            try:
                _learn_one_into_domain(domain, topic, nxt)
                nxt["status"] = "done"
            except Exception as e:
                nxt["status"] = "error"
                nxt["error"] = str(e)[:200]
            data["last_run"] = datetime.datetime.now().isoformat(timespec="seconds")
            _save_queue(domain, data)
            _rebuild_index(domain, data)
            made += 1
            with _deep_learn_lock:
                _deep_learn_state["done"] = sum(
                    1 for x in data["items"] if x["status"] == "done")
    finally:
        with _deep_learn_lock:
            _deep_learn_state["running"] = False

def _find_existing_note(slug, exclude_dir=None):
    try:
        base = Path(KNOWLEDGE_DIR)
        if not base.exists():
            return None
        target_name = slug + ".md"
        excl = None
        if exclude_dir is not None:
            try:
                excl = Path(exclude_dir).resolve()
            except Exception:
                excl = None
        for f in base.rglob(target_name):
            if f.name.startswith("_"):
                continue
            if excl is not None:
                try:
                    fr = f.resolve()
                    if fr == excl or excl in fr.parents:
                        continue
                except Exception:
                    pass
            return f
        return None
    except Exception:
        return None

def _learn_one_into_domain(domain: str, topic: str, item: dict):
    slug = _slugify_topic(topic)
    existing_dup = _find_existing_note(slug, exclude_dir=_domain_dir(domain))
    if existing_dup is not None:
        d = _domain_dir(domain)
        d.mkdir(parents=True, exist_ok=True)
        try:
            rel = existing_dup.relative_to(Path(KNOWLEDGE_DIR))
            other_domain = (rel.parts[0].replace("_", " ")
                            if len(rel.parts) > 1 else "knowledge base")
        except Exception:
            other_domain = "knowledge base"
        stub_md = ("# " + topic + "\n\n"
                   "_Already covered in " + other_domain + ". "
                   "See: [[" + existing_dup.stem + "|" + topic + "]]._\n")
        fname = slug + ".md"
        (d / fname).write_text(stub_md, encoding="utf-8")
        item["file"] = fname
        item["duplicate_of"] = existing_dup.stem
        return
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    research_system = (
        "You are a research assistant generating a structured deep study "
        "note as part of a larger curriculum on '" + domain + "'. Output "
        "ONLY Markdown - no preamble. Use this structure: YAML frontmatter "
        "(title, date ISO, tags, domain: '" + domain + "', depth: "
        "foundational); a top-level heading; ## TL;DR (3-5 sentences); "
        "## Foundational Principles; ## Key Equations / Formulas (define "
        "every symbol; omit if N/A); ## Sub-topics (3-6, each a paragraph); "
        "## Common Questions (Q&A, 3-6); ## Sources for Further Study (real "
        "references only); ## Related Topics (bullet list). Never invent "
        "citations or specifications."
    )
    r = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=8000,
        system=research_system,
        messages=[{"role": "user",
                   "content": "Sub-topic to study in depth: " + topic
                              + "\n\nGenerate the full Markdown note now."}],
    )
    parts = []
    for b in (r.content or []):
        if getattr(b, "type", "") == "text":
            parts.append(b.text)
    note_md = "\n".join(parts).strip()
    if not note_md:
        raise RuntimeError("empty response from model")
    d = _domain_dir(domain)
    d.mkdir(parents=True, exist_ok=True)
    fname = _slugify_topic(topic) + ".md"
    note_md = _link_existing_notes(note_md, current_slug=fname[:-3])
    (d / fname).write_text(note_md + "\n", encoding="utf-8")
    item["file"] = fname

def deep_learn_domain(domain: str, max_notes=None):
    if not domain or not domain.strip():
        return "Which field should I study, sir?"
    if not ANTHROPIC_API_KEY:
        return "Can't reach the research model - the Anthropic key isn't set, sir."
    domain = domain.strip()
    try:
        cap = int(max_notes) if max_notes else DEEP_LEARN_DEFAULT_CAP
    except Exception:
        cap = DEEP_LEARN_DEFAULT_CAP
    cap = max(1, min(cap, 60))
    with _deep_learn_lock:
        if _deep_learn_state["running"]:
            cur = _deep_learn_state["domain"]
            return (f"I'm already learning {cur} in the background, sir "
                    f"({_deep_learn_state['done']} of {_deep_learn_state['target']} this run). "
                    f"Let it finish, or ask for a status.")
    existing = _load_queue(domain)
    if existing and any(it["status"] == "pending" for it in existing["items"]):
        return resume_learning(domain, max_notes=cap)
    items = _decompose_domain(domain)
    if not items:
        return f"I couldn't build a study plan for {domain}, sir. Try again or rephrase."
    data = {
        "domain": domain,
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "items": [{"topic": t, "status": "pending"} for t in items],
    }
    _save_queue(domain, data)
    _rebuild_index(domain, data)
    target = min(cap, len(items))
    with _deep_learn_lock:
        _deep_learn_state.update({"running": True, "domain": domain, "done": 0,
                                  "target": target, "total": len(items), "last": ""})
    t = threading.Thread(target=_deep_learn_worker, args=(domain, cap), daemon=True)
    t.start()
    return (f"Study plan ready for {domain}, sir: {len(items)} sub-topics. "
            f"Learning the first {target} in the background now - this takes "
            f"a while. Say 'learning status' to check progress, or 'continue "
            f"learning {domain}' later for the rest.")

def resume_learning(domain: str, max_notes=None):
    if not domain or not domain.strip():
        return "Which field should I continue, sir?"
    domain = domain.strip()
    try:
        cap = int(max_notes) if max_notes else DEEP_LEARN_DEFAULT_CAP
    except Exception:
        cap = DEEP_LEARN_DEFAULT_CAP
    cap = max(1, min(cap, 60))
    with _deep_learn_lock:
        if _deep_learn_state["running"]:
            return (f"Already learning {_deep_learn_state['domain']} right now, sir. "
                    f"One field at a time.")
    data = _load_queue(domain)
    if not data:
        return f"I have no study plan for {domain} yet, sir. Ask me to deep-learn it first."
    pending = [it for it in data["items"] if it["status"] == "pending"]
    if not pending:
        done = sum(1 for it in data["items"] if it["status"] == "done")
        return f"{domain} is already complete, sir: {done} of {len(data['items'])} learned."
    target = min(cap, len(pending))
    with _deep_learn_lock:
        _deep_learn_state.update({"running": True, "domain": domain,
                                  "done": sum(1 for it in data["items"] if it["status"]=="done"),
                                  "target": target, "total": len(data["items"]), "last": ""})
    t = threading.Thread(target=_deep_learn_worker, args=(domain, cap), daemon=True)
    t.start()
    return (f"Resuming {domain}, sir: {len(pending)} sub-topics left, "
            f"learning {target} now in the background.")

def learning_status():
    with _deep_learn_lock:
        running = _deep_learn_state["running"]
        domain = _deep_learn_state["domain"]
        done = _deep_learn_state["done"]
        total = _deep_learn_state["total"]
        last = _deep_learn_state["last"]
    if running and domain:
        tail = f" Currently on: {last}." if last else ""
        return (f"Learning {domain} in the background, sir: "
                f"{done} of {total} sub-topics done.{tail}")
    try:
        base = Path(KNOWLEDGE_DIR)
        if base.exists():
            rows = []
            for sub in sorted(base.iterdir()):
                qf = sub / "_queue.json"
                if qf.exists():
                    try:
                        d = json.loads(qf.read_text(encoding="utf-8"))
                        dn = sum(1 for it in d["items"] if it["status"]=="done")
                        rows.append(f"{d.get('domain', sub.name)} ({dn}/{len(d['items'])})")
                    except Exception:
                        pass
            if rows:
                return "Nothing learning right now, sir. Domains so far: " + "; ".join(rows) + "."
    except Exception:
        pass
    return "Nothing is learning right now, sir, and no study plans exist yet."

_worldview_server_proc = None

def _wv_port_in_use(port):
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.3)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False
    finally:
        try: s.close()
        except Exception: pass

_flights_proxy_started = False
_flights_proxy_lock = threading.Lock()
_tle_cache = {"ts": 0.0, "data": b""}
_achilles_state = {"state": "loading", "scene": "core", "ts": 0.0,
                   "last_poll": 0.0}
_planet_news_cache = {}
_tasks_lock = threading.Lock()

# VESSELS relay (v4.66): one server-side WebSocket to aisstream.io, latest
# position kept per MMSI in memory, served at GET /vessels on the :7778 proxy.
_vessels = {}
_vessels_lock = threading.Lock()
_vessels_relay_started = False
_vessels_relay_lock = threading.Lock()
_VESSELS_BBOX = [[[29.0, 24.0], [38.0, 37.0]]]

def _ais_bearing(b):
    """Return b if it is a valid 0-359 AIS bearing, else None. Handles the
    511 'heading not available' and 360 'COG not available' sentinels, None,
    and out-of-range junk so the globe never draws a vessel at a fake heading."""
    try:
        return b if (b is not None and 0 <= float(b) < 360) else None
    except (TypeError, ValueError):
        return None

async def _vessels_ws_loop(api_key):
    import websockets
    url = "wss://stream.aisstream.io/v0/stream"
    sub = json.dumps({
        "APIKey": api_key,
        "BoundingBoxes": _VESSELS_BBOX,
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
    })
    while True:
        try:
            async with websockets.connect(url, ping_interval=20, max_size=None) as ws:
                await ws.send(sub)
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue
                    mt = msg.get("MessageType")
                    meta = msg.get("MetaData", {}) or {}
                    mmsi = meta.get("MMSI")
                    if not mmsi:
                        continue
                    now = time.time()
                    if mt == "PositionReport":
                        pr = (msg.get("Message", {}) or {}).get("PositionReport", {}) or {}
                        lat = pr.get("Latitude", meta.get("latitude"))
                        lon = pr.get("Longitude", meta.get("longitude"))
                        if lat is None or lon is None:
                            continue
                        cog = _ais_bearing(pr.get("Cog"))
                        heading = _ais_bearing(pr.get("TrueHeading"))
                        if heading is None:   # fall back to course over ground
                            heading = cog
                        sog = pr.get("Sog")
                        try:
                            sog = float(sog) if (sog is not None and 0 <= float(sog) < 102.3) else None
                        except (TypeError, ValueError):
                            sog = None
                        with _vessels_lock:
                            v = _vessels.get(mmsi, {})
                            v.update({"mmsi": mmsi, "lat": lat, "lon": lon,
                                      "cog": cog, "sog": sog,
                                      "heading": heading, "ts": now})
                            nm = (meta.get("ShipName") or "").strip()
                            if nm:
                                v["name"] = nm
                            _vessels[mmsi] = v
                    elif mt == "ShipStaticData":
                        sd = (msg.get("Message", {}) or {}).get("ShipStaticData", {}) or {}
                        with _vessels_lock:
                            v = _vessels.get(mmsi, {"mmsi": mmsi})
                            nm = (sd.get("Name") or meta.get("ShipName") or "").strip()
                            if nm:
                                v["name"] = nm
                            t = sd.get("Type")
                            if t is not None:
                                v["type"] = t
                            # refresh ts on every message so a vessel that sends
                            # only static data isn't pruned while still active.
                            v["ts"] = now
                            _vessels[mmsi] = v
        except Exception as e:
            try:
                print("[diag] vessels relay reconnect after error: %r" % (e,))
            except Exception:
                pass
            await asyncio.sleep(5)

def _start_vessels_relay():
    global _vessels_relay_started
    with _vessels_relay_lock:
        if _vessels_relay_started:
            return
        api_key = os.environ.get("AISSTREAM_API_KEY", "") or ""
        if not api_key:
            print("[diag] vessels relay: no AISSTREAM_API_KEY in .env - VESSELS disabled")
            return
        try:
            import websockets  # noqa: F401
        except Exception:
            print("[diag] vessels relay: `websockets` not installed - run: pip install websockets")
            return
        def _run():
            try:
                asyncio.run(_vessels_ws_loop(api_key))
            except Exception as e:
                print("[diag] vessels relay thread died: %r" % (e,))
        threading.Thread(target=_run, daemon=True, name="jarvis-vessels-relay").start()
        _vessels_relay_started = True
        print("[diag] vessels relay started (aisstream, Eastern-Med bbox)")

class _FlightsProxyHandler(http.server.BaseHTTPRequestHandler):
    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET")
        self.send_header("Cache-Control", "no-store")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/route":
            self._handle_route(parsed)
            return
        if parsed.path == "/tle":
            self._handle_tle()
            return
        if parsed.path == "/state":
            self._handle_state()
            return
        if parsed.path == "/planet":
            self._handle_planet(parsed)
            return
        if parsed.path == "/ask":
            self._handle_ask(parsed)
            return
        if parsed.path in ("/todo", "/todo_add", "/todo_toggle", "/todo_del"):
            self._handle_todo(parsed)
            return
        if parsed.path == "/keys":
            try:
                import json as _json
                _payload = _json.dumps({
                    "googleMapsApiKey": os.environ.get("GOOGLE_MAPS_API_KEY", "") or "",
                    "owmApiKey": os.environ.get("OWM_API_KEY", "") or "",
                }).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.send_header("Content-Length", str(len(_payload)))
                self.end_headers()
                self.wfile.write(_payload)
            except Exception as _e:
                try:
                    self.send_response(500); self._cors_headers(); self.end_headers()
                except Exception:
                    pass
            return
        if parsed.path == "/vessels":
            try:
                import json as _json
                now = time.time()
                with _vessels_lock:
                    items = [dict(v) for v in _vessels.values()
                             if v.get("lat") is not None and v.get("lon") is not None
                             and (now - v.get("ts", 0)) < 600]
                    stale = [m for m, v in _vessels.items()
                             if (now - v.get("ts", 0)) > 1800]
                    for m in stale:
                        _vessels.pop(m, None)
                payload = _json.dumps({"vessels": items,
                                       "count": len(items)}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as _e:
                try:
                    body = ('{"error":' + json.dumps(str(_e))
                            + ',"vessels":[]}').encode("utf-8")
                    self.send_response(502)
                    self.send_header("Content-Type", "application/json")
                    self._cors_headers()
                    self.end_headers()
                    self.wfile.write(body)
                except Exception:
                    pass
            return
        if parsed.path != "/flights":
            self.send_response(404)
            self._cors_headers()
            self.end_headers()
            return
        try:
            params = urllib.parse.parse_qs(parsed.query)
            lat = params.get("lat", ["32.0"])[0]
            lon = params.get("lon", ["34.8"])[0]
            radius = params.get("radius", ["250"])[0]
            float(lat); float(lon); int(float(radius))
            url = "https://api.adsb.lol/v2/lat/%s/lon/%s/dist/%s" % (lat, lon, radius)
            req = urllib.request.Request(url, headers={
                "User-Agent": "JARVIS-WorldView/1.0",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            try:
                body = ('{"error":' + json.dumps(str(e)) + ',"ac":[]}').encode("utf-8")
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                pass

    def _handle_route(self, parsed):
        try:
            params = urllib.parse.parse_qs(parsed.query)
            cs = (params.get("callsign", [""])[0] or "").strip().upper()
            lat = params.get("lat", ["32.0"])[0]
            lon = params.get("lon", ["34.8"])[0]
            float(lat); float(lon)
            if not cs:
                raise ValueError("no callsign")
            body = json.dumps({"planes": [
                {"callsign": cs, "lat": float(lat), "lng": float(lon)}
            ]}).encode("utf-8")
            req = urllib.request.Request(
                "https://api.adsb.lol/api/0/routeset",
                data=body, method="POST",
                headers={
                    "User-Agent": "JARVIS-WorldView/1.0",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                out = r.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(out)
        except Exception as e:
            try:
                msg = ('{"error":' + json.dumps(str(e)) + '}').encode("utf-8")
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.end_headers()
                self.wfile.write(msg)
            except Exception:
                pass

    def _handle_tle(self):
        global _tle_cache
        try:
            now = time.time()
            if _tle_cache["data"] and (now - _tle_cache["ts"] < 6 * 3600):
                payload = _tle_cache["data"]
            else:
                sats, seen = [], set()
                for grp_name, grp_tag in (("stations", "station"),
                                          ("visual", "visual")):
                    url = ("https://celestrak.org/NORAD/elements/gp.php"
                           "?GROUP=%s&FORMAT=tle" % grp_name)
                    req = urllib.request.Request(url, headers={
                        "User-Agent": "JARVIS-WorldView/1.0",
                        "Accept": "text/plain",
                    })
                    try:
                        with urllib.request.urlopen(req, timeout=15) as r:
                            text = r.read().decode("utf-8", "replace")
                    except Exception:
                        continue
                    lines = [ln.rstrip() for ln in text.splitlines()
                             if ln.strip()]
                    for i in range(0, len(lines) - 2, 3):
                        name = lines[i].strip()
                        l1, l2 = lines[i + 1], lines[i + 2]
                        if not l1.startswith("1 ") or not l2.startswith("2 "):
                            continue
                        norad = l1[2:7].strip()
                        if norad in seen:
                            continue
                        seen.add(norad)
                        sats.append({"name": name, "l1": l1, "l2": l2,
                                     "grp": grp_tag})
                if not sats:
                    raise RuntimeError("no TLE data from Celestrak")
                payload = json.dumps({"sats": sats[:150],
                                      "fetched": int(now)}).encode("utf-8")
                _tle_cache = {"ts": now, "data": payload}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:
            try:
                if _tle_cache["data"]:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self._cors_headers()
                    self.end_headers()
                    self.wfile.write(_tle_cache["data"])
                    return
                msg = ('{"error":' + json.dumps(str(e))
                       + ',"sats":[]}').encode("utf-8")
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.end_headers()
                self.wfile.write(msg)
            except Exception:
                pass

    def _handle_state(self):
        try:
            _achilles_state["last_poll"] = time.time()
            _scene = _achilles_state.get("scene", "core")
            body = json.dumps({
                "state": _achilles_state.get("state", "idle"),
                "scene": _scene,
                "ts": _achilles_state.get("ts", 0.0),
                "srv": time.time(),
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
            if _scene == "dive":
                _achilles_state["scene"] = "core"
        except Exception:
            pass

    def _handle_ask(self, parsed):
        try:
            # The proxy binds 0.0.0.0 for phone WorldView access, but /ask runs
            # the full brain (state mutation, web search, API spend). Restrict it
            # to loopback so a LAN host / drive-by web page can't drive it.
            _peer = self.client_address[0] if self.client_address else ""
            if _peer not in ("127.0.0.1", "::1", "localhost"):
                self.send_response(403)
                self._cors_headers()
                self.end_headers()
                return
            params = urllib.parse.parse_qs(parsed.query)
            q = (params.get("q", [""])[0] or "").strip()
            if not q:
                raise ValueError("empty question")
            lang = "he" if is_hebrew(q) else "en"
            _achilles_state["state"] = "thinking"
            _achilles_state["ts"] = time.time()
            try:
                mem = APP.memory if (APP is not None and getattr(APP, "memory", "")) \
                      else load_long_term_memory()
            except Exception:
                mem = ""
            try:
                reply = think(q, mem, lang=lang)
            except Exception as e:
                reply = "Brain error: %r" % (e,)
            body = json.dumps({"reply": reply}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
            client = self.client_address[0] if self.client_address else ""
            if client in ("127.0.0.1", "::1", "localhost"):
                def _say(txt):
                    _achilles_state["state"] = "speaking"
                    _achilles_state["ts"] = time.time()
                    try:
                        speak(clean_text(txt))
                    except Exception:
                        pass
                    _achilles_state["state"] = "idle"
                    _achilles_state["ts"] = time.time()
                threading.Thread(target=_say, args=(reply,), daemon=True).start()
            else:
                _achilles_state["state"] = "idle"
                _achilles_state["ts"] = time.time()
        except Exception as e:
            try:
                _achilles_state["state"] = "idle"
                msg = ('{"error":' + json.dumps(str(e)) + "}").encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.end_headers()
                self.wfile.write(msg)
            except Exception:
                pass

    def _handle_todo(self, parsed):
        try:
            # Allow read-only GET /todo from the LAN (phone can view the list),
            # but block the mutating actions from non-loopback origins so a
            # cross-site GET can't add/toggle/delete the user's tasks.
            if parsed.path != "/todo":
                _peer = self.client_address[0] if self.client_address else ""
                if _peer not in ("127.0.0.1", "::1", "localhost"):
                    self.send_response(403)
                    self._cors_headers()
                    self.end_headers()
                    return
            params = urllib.parse.parse_qs(parsed.query)
            with _tasks_lock:
                tasks = _tasks_load()
                if parsed.path == "/todo_add":
                    text = (params.get("text", [""])[0] or "").strip()
                    if text:
                        tasks.append({"id": int(time.time() * 1000),
                                      "text": text, "done": False,
                                      "ts": time.time()})
                        _tasks_save(tasks)
                elif parsed.path == "/todo_toggle":
                    tid = int(params.get("id", ["0"])[0] or "0")
                    for t in tasks:
                        if t.get("id") == tid:
                            t["done"] = not t.get("done", False)
                    _tasks_save(tasks)
                elif parsed.path == "/todo_del":
                    tid = int(params.get("id", ["0"])[0] or "0")
                    tasks = [t for t in tasks if t.get("id") != tid]
                    _tasks_save(tasks)
            body = json.dumps({"tasks": tasks}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            try:
                msg = ('{"error":' + json.dumps(str(e))
                       + ',"tasks":[]}').encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.end_headers()
                self.wfile.write(msg)
            except Exception:
                pass

    def _handle_planet(self, parsed):
        try:
            params = urllib.parse.parse_qs(parsed.query)
            name = (params.get("name", [""])[0] or "").strip().lower()
            lang = (params.get("lang", ["he"])[0] or "he").strip().lower()
            allowed = ("sun", "mercury", "venus", "earth", "moon", "mars",
                       "jupiter", "saturn", "uranus", "neptune")
            if name not in allowed:
                raise ValueError("unknown body: %s" % name)
            now = time.time()
            ck = name + ":" + ("he" if lang == "he" else "en")
            hit = _planet_news_cache.get(ck)
            if hit and (now - hit["ts"] < 3600) and hit["text"]:
                text = hit["text"]
            else:
                if not ANTHROPIC_API_KEY:
                    raise RuntimeError("no API key")
                client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
                sys_p = (
                    "You are a space news desk. Use web_search to find the 3 "
                    "most interesting RECENT news items (missions, discoveries, "
                    "research - prefer the last month) about: " + name + ". "
                    "Then output ONLY a compact plain-text list of those 3 "
                    "items, one per line, each one short factual sentence. "
                    "No URLs, no numbering, no markdown. Write in "
                    + ("Hebrew" if lang == "he" else "English") + ".")
                tools = [{"type": "web_search_20250305",
                          "name": "web_search", "max_uses": 2}]
                msgs = [{"role": "user",
                         "content": "Latest news about " + name + ", please."}]
                r = None
                for _ in range(4):
                    r = client.messages.create(
                        model="claude-sonnet-4-6", max_tokens=450,
                        system=sys_p, messages=msgs, tools=tools)
                    msgs.append({"role": "assistant", "content": r.content})
                    if getattr(r, "stop_reason", None) == "tool_use":
                        continue
                    break
                parts = [b.text for b in r.content
                         if getattr(b, "type", None) == "text"]
                text = "\n".join(p.strip() for p in parts if p.strip()).strip()
                text = re.sub(r"https?://\S+", "", text).strip()
                if not text:
                    raise RuntimeError("empty news")
                _planet_news_cache[ck] = {"ts": now, "text": text}
            body = json.dumps({"name": name, "news": text}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            try:
                msg = ('{"error":' + json.dumps(str(e))
                       + ',"news":""}').encode("utf-8")
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.end_headers()
                self.wfile.write(msg)
            except Exception:
                pass

    def log_message(self, *args, **kwargs):
        pass

def _start_flights_proxy(port=7778):
    global _flights_proxy_started
    with _flights_proxy_lock:
        if _flights_proxy_started:
            return True
        try:
            server = http.server.ThreadingHTTPServer(
                ("0.0.0.0", port), _FlightsProxyHandler
            )
        except OSError as e:
            print("[diag] flights proxy could not bind to %d: %r" % (port, e))
            return False
        th = threading.Thread(
            target=server.serve_forever, daemon=True,
            name="jarvis-flights-proxy",
        )
        th.start()
        _flights_proxy_started = True
        print("[diag] flights proxy listening on 0.0.0.0:%d (LAN)" % port)
        return True

def _ensure_worldview_server(files_dir, port=7777):
    global _worldview_server_proc
    _start_flights_proxy()
    _start_vessels_relay()
    if _wv_port_in_use(port):
        return True
    try:
        creationflags = 0
        if os.name == "nt":
            creationflags = 0x08000000
        _worldview_server_proc = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port), "--bind", "0.0.0.0"],
            cwd=str(files_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
        )
    except Exception as e:
        print("[diag] failed to spawn WorldView server:", repr(e))
        return False
    for _ in range(30):
        if _wv_port_in_use(port):
            return True
        time.sleep(0.1)
    print("[diag] WorldView server did not become reachable within 3s")
    return False

def open_worldview():
    files_dir = Path(__file__).resolve().parent
    path = files_dir / "worldview.html"
    if not path.exists():
        return "WorldView file not found, sir. Expected at: %s" % path
    if not _ensure_worldview_server(files_dir, port=7777):
        return "Failed to start the local WorldView server, sir. Try restarting JARVIS."
    if time.time() - _achilles_state.get("last_poll", 0.0) < 3.0:
        _achilles_state["scene"] = "dive"
        _achilles_state["ts"] = time.time()
        return "Diving to Earth, sir."
    url = "http://localhost:7777/worldview.html?t=" + str(int(time.time()))
    edge_candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for exe in edge_candidates:
        if os.path.exists(exe):
            try:
                subprocess.Popen([exe, "--app=" + url], close_fds=True)
                return "Opening WorldView, sir."
            except Exception as e:
                print("[diag] Edge --app launch failed, falling back to default browser:", repr(e))
                break
    try:
        webbrowser.open(url)
        return "Opening WorldView, sir."
    except Exception as e:
        return "Failed to open WorldView: %s" % e

def open_roadmap():
    files_dir = Path(__file__).resolve().parent
    path = files_dir / "roadmap.html"
    if not path.exists():
        return "Roadmap file not found, sir. Expected at: %s" % path
    if not _ensure_worldview_server(files_dir, port=7777):
        return "Failed to start the local server, sir. Try restarting JARVIS."
    url = "http://localhost:7777/roadmap.html?t=" + str(int(time.time()))
    edge_candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for exe in edge_candidates:
        if os.path.exists(exe):
            try:
                subprocess.Popen([exe, "--app=" + url], close_fds=True)
                return "Opening Mission Control, sir."
            except Exception as e:
                print("[diag] Edge --app launch failed, falling back:", repr(e))
                break
    try:
        webbrowser.open(url)
        return "Opening Mission Control, sir."
    except Exception as e:
        return "Failed to open the roadmap: %s" % e

def _tasks_path():
    return Path(__file__).resolve().parent / "tasks.json"

def _tasks_load():
    try:
        with open(_tasks_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def _tasks_save(tasks):
    try:
        with open(_tasks_path(), "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print("[diag] tasks.json save failed:", repr(e))

def todo_add_voice(text, lang="he"):
    text = (text or "").strip().strip('.')
    if not text:
        return "מה להוסיף לרשימה, אדוני?" if lang == "he" else "Add what, sir?"
    with _tasks_lock:
        tasks = _tasks_load()
        tasks.append({"id": int(time.time() * 1000), "text": text,
                      "done": False, "ts": time.time()})
        _tasks_save(tasks)
    n = len([t for t in tasks if not t.get("done")])
    if lang == "he":
        return "נוסף: %s. %d משימות פתוחות, אדוני." % (text, n)
    return "Added: %s. %d open tasks, sir." % (text, n)

def open_portal():
    files_dir = Path(__file__).resolve().parent
    try:
        _ensure_worldview_server(files_dir, port=7777)
    except Exception:
        pass
    url = ("http://localhost:7777/achilles.html?scene=core&ui=full&t="
           + str(int(time.time())))
    prof = str(files_dir / ".portal_profile")
    args = ["--user-data-dir=" + prof, "--no-first-run",
            "--no-default-browser-check", "--start-fullscreen",
            "--app=" + url]
    for exe in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if os.path.isfile(exe):
            try:
                subprocess.Popen([exe] + args)
                return
            except Exception:
                pass
    try:
        os.startfile(url)
    except Exception:
        pass

def open_achilles(scene="core", face=False):
    scene = scene if scene in ("core", "solar", "todo") else "core"
    files_dir = Path(__file__).resolve().parent
    path = files_dir / "achilles.html"
    if not path.exists():
        return "The Achilles screen file is missing, sir. Expected at: %s" % path
    if not _ensure_worldview_server(files_dir, port=7777):
        return "Failed to start the local server, sir. Try restarting me."
    _achilles_state["scene"] = scene
    _achilles_state["ts"] = time.time()
    if time.time() - _achilles_state.get("last_poll", 0.0) < 3.0:
        return {"solar": "Switching to the solar system, sir.",
                "todo": "Bringing up your task list, sir.",
                "core": "Bringing up the core, sir."}[scene]
    url = ("http://localhost:7777/achilles.html?scene=" + scene
           + "&t=" + str(int(time.time())))
    args_extra = []
    if face:
        try:
            import ctypes
            _sw = ctypes.windll.user32.GetSystemMetrics(0)
        except Exception:
            _sw = 1920
        _prof = str(files_dir / ".face_profile")
        args_extra = ["--user-data-dir=" + _prof,
                      "--no-first-run", "--no-default-browser-check",
                      "--window-size=420,500",
                      "--window-position=%d,60" % max(0, _sw - 450)]
    edge_candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for exe in edge_candidates:
        if os.path.exists(exe):
            try:
                subprocess.Popen([exe, "--app=" + url] + args_extra,
                                 close_fds=True)
                return {"solar": "Opening the solar system, sir.",
                        "todo": "Opening your task list, sir.",
                        "core": "Opening the core, sir."}[scene]
            except Exception as e:
                print("[diag] Edge --app launch failed, falling back:", repr(e))
                break
    try:
        webbrowser.open(url)
        return {"solar": "Opening the solar system, sir.",
                "todo": "Opening your task list, sir.",
                "core": "Opening the core, sir."}[scene]
    except Exception as e:
        return "Failed to open the Achilles screen: %s" % e

def _gmaps_get(url, params, timeout=12):
    if not GOOGLE_MAPS_API_KEY:
        return None, "Google Maps API key missing from .env (GOOGLE_MAPS_API_KEY)."
    params = dict(params)
    params["key"] = GOOGLE_MAPS_API_KEY
    full = url + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(full, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.URLError as e:
        return None, f"Network error contacting Google Maps: {e}"
    except Exception as e:
        return None, f"Unexpected error: {e}"
    status = data.get("status", "")
    if status not in ("OK", "ZERO_RESULTS"):
        return None, f"Google Maps returned status {status}: {data.get('error_message','')}"
    return data, None

def find_places(query, max_results=5):
    if not query or not query.strip():
        return "Please tell me what kind of place you're looking for, sir."
    params = {
        "query": query.strip(),
        "location": "32.1772,34.9947",
        "radius": "50000",
        "region": "il",
        "language": "iw",
    }
    data, err = _gmaps_get(
        "https://maps.googleapis.com/maps/api/place/textsearch/json", params)
    if err:
        return f"Place search failed: {err}"
    results = data.get("results") or []
    if not results:
        return f"No places found in Israel matching '{query}'."
    out = []
    for p in results[:max_results]:
        name = p.get("name", "?")
        addr = p.get("formatted_address", "")
        rating = p.get("rating")
        ratings_n = p.get("user_ratings_total")
        oh = p.get("opening_hours", {})
        open_now = oh.get("open_now")
        bits = [name]
        if rating is not None:
            bits.append(f"{rating}/5"
                        + (f" ({ratings_n} reviews)" if ratings_n else ""))
        if open_now is True:
            bits.append("open now")
        elif open_now is False:
            bits.append("closed now")
        if addr:
            bits.append(addr)
        out.append(" — ".join(bits))
    return "Top results:\n- " + "\n- ".join(out)

def get_directions(destination, origin=None):
    if not destination or not destination.strip():
        return "Where would you like to go, sir?"
    origin = (origin or HOME_ADDRESS).strip()
    params = {
        "origin": origin,
        "destination": destination.strip(),
        "mode": "driving",
        "departure_time": "now",
        "traffic_model": "best_guess",
        "region": "il",
        "language": "iw",
    }
    data, err = _gmaps_get(
        "https://maps.googleapis.com/maps/api/directions/json", params)
    if err:
        return f"Directions failed: {err}"
    routes = data.get("routes") or []
    if not routes:
        return f"No driving route found from {origin} to {destination}."
    leg = routes[0]["legs"][0]
    dist = leg.get("distance", {}).get("text", "?")
    dur = leg.get("duration", {}).get("text", "?")
    dur_traffic = leg.get("duration_in_traffic", {}).get("text")
    start_addr = leg.get("start_address", origin)
    end_addr = leg.get("end_address", destination)
    summary = (routes[0].get("summary") or "").strip()
    line = f"From {start_addr} to {end_addr}: {dist}, normally {dur}"
    if dur_traffic:
        line += f", with current traffic about {dur_traffic}"
    if summary:
        line += f". Route via {summary}."
    else:
        line += "."
    return line

def _calendar_service():
    if not HAVE_GCAL:
        print("Calendar: Google libraries not installed.")
        return None
    if not os.path.exists(CAL_CREDENTIALS_FILE):
        print("Calendar: credentials.json not found in folder.")
        return None
    creds = None
    try:
        if os.path.exists(CAL_TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(CAL_TOKEN_FILE, CAL_SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CAL_CREDENTIALS_FILE, CAL_SCOPES)
                creds = flow.run_local_server(port=0)
            with open(CAL_TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        return build("calendar", "v3", credentials=creds, cache_discovery=False)
    except Exception as e:
        print("Calendar auth error:", e)
        return None

def calendar_read(time_min=None, time_max=None, max_results=10):
    svc = _calendar_service()
    if svc is None:
        return ("Calendar not connected. Add credentials.json and install the "
                "Google libraries to enable it, sir.")
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        local_tz = datetime.datetime.now().astimezone().tzinfo

        def _tz(s):
            if not s:
                return None
            s = s.strip()
            if s.endswith("Z") or re.search(r'[+\-]\d{2}:?\d{2}$', s):
                return s
            try:
                d = datetime.datetime.fromisoformat(s)
                if d.tzinfo is None:
                    d = d.replace(tzinfo=local_tz)
                return d.isoformat()
            except Exception:
                return s

        tmin = _tz(time_min) or now.isoformat()
        tmax = _tz(time_max) or (now + datetime.timedelta(days=7)).isoformat()
        res = svc.events().list(calendarId="primary", timeMin=tmin, timeMax=tmax,
                                singleEvents=True, orderBy="startTime",
                                maxResults=max_results).execute()
        items = res.get("items", [])
        if not items:
            return "No events found in that period."
        lines = []
        for e in items:
            s = e["start"].get("dateTime", e["start"].get("date", ""))
            eid = e.get("id", "")
            lines.append(f"[id={eid}] {s}: {e.get('summary', '(no title)')}")
        return "Events:\n" + "\n".join(lines)
    except Exception as e:
        print("Calendar read error:", repr(e))
        return f"Failed to read calendar: {e}"

def calendar_add(summary, start_iso, end_iso=None, location=None, description=None):
    svc = _calendar_service()
    if svc is None:
        return "Calendar not connected, sir."
    if not summary or not start_iso:
        return "I need at least a title and a start time."
    try:
        if not end_iso:
            st = datetime.datetime.fromisoformat(start_iso)
            end_iso = (st + datetime.timedelta(hours=1)).isoformat()
        body = {
            "summary": summary,
            "start": {"dateTime": start_iso, "timeZone": CAL_TIMEZONE},
            "end": {"dateTime": end_iso, "timeZone": CAL_TIMEZONE},
        }
        if location:
            body["location"] = location
        if description:
            body["description"] = description
        ev = svc.events().insert(calendarId="primary", body=body).execute()
        _record_action("calendar_add",
                       {"event_id": ev.get("id", ""), "summary": summary})
        return f"Event '{summary}' added for {start_iso}."
    except Exception as e:
        print("Calendar add error:", repr(e))
        return f"Failed to add event: {e}"

def calendar_delete(event_id):
    svc = _calendar_service()
    if svc is None:
        return "Calendar not connected, sir."
    if not event_id:
        return "I need the event id to delete, sir."
    try:
        cached_body = None
        try:
            ev = svc.events().get(calendarId="primary",
                                  eventId=event_id).execute()
            cached_body = {k: v for k, v in ev.items()
                           if k in ("summary", "description", "location",
                                    "start", "end", "attendees",
                                    "reminders", "colorId")}
        except Exception:
            cached_body = None
        svc.events().delete(calendarId="primary", eventId=event_id).execute()
        if cached_body:
            _record_action("calendar_delete", {"body": cached_body})
        return "Event deleted, sir."
    except Exception as e:
        print("Calendar delete error:", repr(e))
        return f"Failed to delete event: {e}"

def calendar_update(event_id, summary=None, start_iso=None, end_iso=None,
                    location=None, description=None):
    svc = _calendar_service()
    if svc is None:
        return "Calendar not connected, sir."
    if not event_id:
        return "I need the event id to update, sir."
    body = {}
    if summary:
        body["summary"] = summary
    if start_iso:
        body["start"] = {"dateTime": start_iso, "timeZone": CAL_TIMEZONE}
    if end_iso:
        body["end"] = {"dateTime": end_iso, "timeZone": CAL_TIMEZONE}
    if location is not None:
        body["location"] = location
    if description is not None:
        body["description"] = description
    if not body:
        return "Nothing to change, sir."
    try:
        svc.events().patch(calendarId="primary", eventId=event_id,
                           body=body).execute()
        return "Event updated, sir."
    except Exception as e:
        print("Calendar update error:", repr(e))
        return f"Failed to update event: {e}"

def _gmail_service():
    if not HAVE_GCAL:
        print("Gmail: Google libraries not installed.")
        return None
    if not os.path.exists(CAL_CREDENTIALS_FILE):
        print("Gmail: credentials.json not found in folder.")
        return None
    creds = None
    try:
        if os.path.exists(CAL_TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(CAL_TOKEN_FILE, GOOGLE_SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CAL_CREDENTIALS_FILE, GOOGLE_SCOPES)
                creds = flow.run_local_server(port=0)
            with open(CAL_TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        return build("gmail", "v1", credentials=creds, cache_discovery=False)
    except Exception as e:
        print("Gmail auth error:", repr(e))
        return None

def _gmail_header(msg, name):
    for h in msg.get("payload", {}).get("headers", []):
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""

def _looks_like_spam(subject, sender, snippet):
    blob = (subject + " " + sender + " " + snippet).lower()
    if "unsubscribe" in blob:
        return True
    hits = sum(1 for w in GMAIL_SPAM_HINTS if w in blob)
    if hits >= 2:
        return True
    if any(w in blob for w in ("sale", "% off", "discount", "deal", "promo",
                               "newsletter", "offer")):
        return True
    return False

def _email_address_only(sender):
    m = re.search(r'<([^>]+)>', sender or "")
    if m:
        return m.group(1).strip().lower()
    return (sender or "").strip().lower()

def gmail_read(max_results=12):
    svc = _gmail_service()
    if svc is None:
        return "Gmail not connected, sir."
    try:
        res = svc.users().messages().list(
            userId="me", labelIds=["INBOX"], maxResults=max_results).execute()
        ids = [m["id"] for m in res.get("messages", [])]
        if not ids:
            return "Your inbox is empty, sir."
        lines = []
        for mid in ids:
            msg = svc.users().messages().get(
                userId="me", id=mid, format="metadata",
                metadataHeaders=["From", "Subject"]).execute()
            sender = _gmail_header(msg, "From")
            subject = _gmail_header(msg, "Subject") or "(no subject)"
            snippet = (msg.get("snippet", "") or "")[:120]
            lines.append(f"From {sender} | {subject} | {snippet}")
        return ("Here are the latest %d emails. Summarise them briefly for the "
                "user by voice (who, about what, anything urgent):\n" % len(lines)
                + "\n".join(lines))
    except Exception as e:
        print("Gmail read error:", repr(e))
        return f"Failed to read email: {e}"

def gmail_spam_review(max_results=25):
    global _gmail_pending_spam
    svc = _gmail_service()
    if svc is None:
        return "Gmail not connected, sir."
    try:
        res = svc.users().messages().list(
            userId="me", labelIds=["INBOX"], maxResults=max_results).execute()
        ids = [m["id"] for m in res.get("messages", [])]
        flagged = []
        for mid in ids:
            msg = svc.users().messages().get(
                userId="me", id=mid, format="metadata",
                metadataHeaders=["From", "Subject"]).execute()
            sender = _gmail_header(msg, "From")
            subject = _gmail_header(msg, "Subject") or "(no subject)"
            snippet = msg.get("snippet", "") or ""
            if _looks_like_spam(subject, sender, snippet):
                flagged.append({"id": mid, "from": sender,
                                "addr": _email_address_only(sender),
                                "subject": subject})
        _gmail_pending_spam = flagged
        if not flagged:
            return "I found no obvious spam in your recent inbox, sir."
        listing = "\n".join(f"- {f['subject']} (from {f['from']})" for f in flagged)
        return ("I found %d likely spam/promotional emails. Read the list to the "
                "user and ASK whether to move them to JARVIS_Spam AND block those "
                "senders for the future. Do NOT do anything yet; wait for a clear "
                "yes. List:\n%s" % (len(flagged), listing))
    except Exception as e:
        print("Gmail spam review error:", repr(e))
        return f"Failed to review spam: {e}"

def _gmail_get_or_make_label(svc, name):
    res = svc.users().labels().list(userId="me").execute()
    for lab in res.get("labels", []):
        if lab.get("name") == name:
            return lab["id"]
    created = svc.users().labels().create(
        userId="me", body={"name": name,
                            "labelListVisibility": "labelShow",
                            "messageListVisibility": "show"}).execute()
    return created["id"]

def gmail_move_spam():
    global _gmail_pending_spam
    svc = _gmail_service()
    if svc is None:
        return "Gmail not connected, sir."
    if not _gmail_pending_spam:
        return "There's nothing staged to move, sir. Ask me to review spam first."
    try:
        label_id = _gmail_get_or_make_label(svc, GMAIL_SPAM_LABEL)
        moved = 0
        blocked_addrs = set()
        for f in _gmail_pending_spam:
            svc.users().messages().modify(
                userId="me", id=f["id"],
                body={"addLabelIds": [label_id], "removeLabelIds": ["INBOX"]}).execute()
            moved += 1
            addr = f.get("addr") or ""
            if addr and "@" in addr and addr not in blocked_addrs:
                try:
                    svc.users().settings().filters().create(
                        userId="me",
                        body={"criteria": {"from": addr},
                              "action": {"addLabelIds": ["TRASH"],
                                         "removeLabelIds": ["INBOX"]}}).execute()
                    blocked_addrs.add(addr)
                except Exception as fe:
                    print("Gmail block-sender warning for", addr, ":", repr(fe))
        _gmail_pending_spam = []
        return (f"Done, sir. Moved {moved} emails to {GMAIL_SPAM_LABEL} and blocked "
                f"{len(blocked_addrs)} senders for the future. Nothing was deleted; "
                "everything is recoverable.")
    except Exception as e:
        print("Gmail move spam error:", repr(e))
        return f"Failed to move spam: {e}"

LOCAL_TOOLS = [
    {
        "name": "open_app",
        "description": ("Open an application or website on the user's Windows PC. "
                        "Allowed names: " + ", ".join(ALLOWED_APPS.keys()) + "."),
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string",
                                    "description": "Which allowed app/site to open."}},
            "required": ["name"],
        },
    },
    {
        "name": "save_note",
        "description": ("Save a short note to the user's Obsidian vault."),
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string",
                                    "description": "The note content to save."}},
            "required": ["text"],
        },
    },
    {
        "name": "learn_topic",
        "description": ("Research a subject in depth and save a structured study note. "
                        "Use ONLY when the user explicitly asks to learn/study/research a topic."),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The subject to study."},
                "context": {"type": "string", "description": "Optional project context. Empty string if none."},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "deep_learn_domain",
        "description": ("Study an ENTIRE field/domain in depth over time."),
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "The field to study deeply."},
                "max_notes": {"type": "integer", "description": "Optional cap (default 15, max 60)."},
            },
            "required": ["domain"],
        },
    },
    {
        "name": "resume_learning",
        "description": ("Continue learning the remaining sub-topics of a planned domain."),
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "The field to continue."},
                "max_notes": {"type": "integer", "description": "Optional cap (default 15, max 60)."},
            },
            "required": ["domain"],
        },
    },
    {
        "name": "learning_status",
        "description": ("Report how the background deep-learning is going."),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "calendar_read",
        "description": ("Read the user's Google Calendar. Defaults to the next 7 days."),
        "input_schema": {
            "type": "object",
            "properties": {
                "time_min": {"type": "string", "description": "ISO start (optional)."},
                "time_max": {"type": "string", "description": "ISO end (optional)."},
            },
        },
    },
    {
        "name": "calendar_add",
        "description": ("Add an event to the user's Google Calendar. Local timezone is Israel."),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Event title."},
                "start_iso": {"type": "string", "description": "Start, ISO."},
                "end_iso": {"type": "string", "description": "End, ISO (optional)."},
                "location": {"type": "string", "description": "Location (optional)."},
            },
            "required": ["summary", "start_iso"],
        },
    },
    {
        "name": "calendar_delete",
        "description": ("Delete an event. First calendar_read to find the id. "
                        "If several match, ask which before deleting."),
        "input_schema": {
            "type": "object",
            "properties": {"event_id": {"type": "string",
                                        "description": "The event id from calendar_read."}},
            "required": ["event_id"],
        },
    },
    {
        "name": "calendar_update",
        "description": ("Modify an existing event. Pass ONLY fields to change."),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "Event id."},
                "summary": {"type": "string", "description": "New title (optional)."},
                "start_iso": {"type": "string", "description": "New start ISO (optional)."},
                "end_iso": {"type": "string", "description": "New end ISO (optional)."},
                "location": {"type": "string", "description": "New location (optional)."},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "gmail_read",
        "description": ("Read the user's most recent emails and summarise them."),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "gmail_spam_review",
        "description": ("Scan recent inbox mail for likely spam. Does NOT move anything; "
                        "read the list and ask. Only call gmail_move_spam after a clear yes."),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "gmail_move_spam",
        "description": ("Move reviewed spam to JARVIS_Spam and block senders. "
                        "ONLY after explicit confirmation. Nothing is deleted."),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "find_places",
        "description": ("Search Google Places in Israel for restaurants/shops/etc."),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string",
                                     "description": "What to search for. Hebrew is fine."}},
            "required": ["query"],
        },
    },
    {
        "name": "get_directions",
        "description": ("Driving travel time from home (Alfei Menashe) to a destination, with live traffic."),
        "input_schema": {
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "Address or place name."},
                "origin": {"type": "string", "description": "Optional starting address. Defaults to home."},
            },
            "required": ["destination"],
        },
    },
    {
        "name": "set_timer",
        "description": ("Start a countdown timer or reminder. For an absolute time, compute "
                        "minutes from the current local time in the system prompt."),
        "input_schema": {
            "type": "object",
            "properties": {
                "minutes": {"type": "number", "description": "Minutes from now until it fires."},
                "label": {"type": "string", "description": "Optional short label."},
            },
            "required": ["minutes"],
        },
    },
    {
        "name": "spotify_play",
        "description": ("Play music on Spotify. Pass query for a specific request; omit to resume."),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string",
                                     "description": "Song / artist / album / playlist. Omit to resume."}},
        },
    },
    {"name": "spotify_pause", "description": "Pause Spotify playback.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "spotify_next", "description": "Skip to the next track on Spotify.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "spotify_previous", "description": "Go back to the previous track on Spotify.",
     "input_schema": {"type": "object", "properties": {}}},
    {
        "name": "spotify_volume",
        "description": "Set Spotify playback volume. Pass level 0-100.",
        "input_schema": {
            "type": "object",
            "properties": {"level": {"type": "number", "description": "Volume percent 0-100."}},
            "required": ["level"],
        },
    },
    {"name": "spotify_now_playing", "description": "Ask Spotify what is currently playing.",
     "input_schema": {"type": "object", "properties": {}}},
    {
        "name": "open_roadmap",
        "description": ("Open Mission Control - the project roadmap / status dashboard."),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "open_search_panel",
        "description": ("Open the big search window for product/image search."),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "open_worldview",
        "description": ("Open WorldView, the 3D globe with live USGS earthquakes."),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "open_achilles",
        "description": ("Open the Achilles Core screen (WebGL black hole / solar system / task list). "
                        "scene='solar' for planets, scene='todo' for tasks, else 'core'."),
        "input_schema": {"type": "object", "properties": {
            "scene": {"type": "string", "enum": ["core", "solar", "todo"],
                      "description": "core = black hole, solar = solar system, todo = task list"}
        }},
    },
]

def run_local_tool(name, tool_input):
    if name == "open_app":
        return open_app(tool_input.get("name", ""))
    if name == "save_note":
        return save_note(tool_input.get("text", ""))
    if name == "calendar_read":
        return calendar_read(tool_input.get("time_min"), tool_input.get("time_max"))
    if name == "calendar_add":
        return calendar_add(tool_input.get("summary", ""),
                            tool_input.get("start_iso", ""),
                            tool_input.get("end_iso"),
                            tool_input.get("location"))
    if name == "calendar_delete":
        return calendar_delete(tool_input.get("event_id", ""))
    if name == "calendar_update":
        return calendar_update(tool_input.get("event_id", ""),
                               tool_input.get("summary"),
                               tool_input.get("start_iso"),
                               tool_input.get("end_iso"),
                               tool_input.get("location"))
    if name == "gmail_read":
        return gmail_read()
    if name == "gmail_spam_review":
        return gmail_spam_review()
    if name == "gmail_move_spam":
        return gmail_move_spam()
    if name == "find_places":
        return find_places(tool_input.get("query", ""))
    if name == "get_directions":
        return get_directions(tool_input.get("destination", ""),
                              tool_input.get("origin"))
    if name == "set_timer":
        return set_timer(tool_input.get("minutes"), tool_input.get("label"))
    if name == "spotify_play":
        return spotify_play(tool_input.get("query"))
    if name == "spotify_pause":
        return spotify_pause()
    if name == "spotify_next":
        return spotify_next()
    if name == "spotify_previous":
        return spotify_previous()
    if name == "spotify_volume":
        return spotify_volume(tool_input.get("level"))
    if name == "spotify_now_playing":
        return spotify_now_playing()
    if name == "deep_learn_domain":
        return deep_learn_domain(tool_input.get("domain", ""), tool_input.get("max_notes"))
    if name == "resume_learning":
        return resume_learning(tool_input.get("domain", ""), tool_input.get("max_notes"))
    if name == "learning_status":
        return learning_status()
    if name == "learn_topic":
        return learn_topic(tool_input.get("topic", ""), tool_input.get("context", ""))
    if name == "open_worldview":
        return open_worldview()
    if name == "open_achilles":
        return open_achilles(tool_input.get("scene", "core"))
    if name == "open_roadmap":
        return open_roadmap()
    if name == "open_search_panel":
        if APP is not None:
            APP.ui(APP.open_panel)
            return "Opening the search window, sir."
        return "The search window isn't available right now."
    return f"Unknown tool: {name}"

def _learning_intercept(user_message: str):
    if not user_message or not isinstance(user_message, str):
        return None
    import re
    text = user_message.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג'?א?ר?ו+יס|gארוויס)[\s,:]*", "", text)
    if not text:
        return None
    low = text.lower()
    if any(p in low for p in ["learning status", "how's the learning",
                              "how is the learning", "what have you learned"]):
        return ("__STATUS__", None)
    if any(p in text for p in ["מה עם הלמידה", "סטטוס למידה", "איך הלמידה",
                               "מה למדת"]):
        return ("__STATUS__", None)
    m = re.match(r"(?:continue|resume|keep)\s+(?:studying|learning)\s+(.+)$", low)
    if m:
        return ("__RESUME__:" + m.group(1).strip(), None)
    m = re.match(r"^\s*תמשיך\s+(?:ללמוד|לחקור)\s+(?:את\s+)?(.+)$", text)
    if m:
        return ("__RESUME__:" + m.group(1).strip(), None)
    en = re.match(
        r"^\s*(deep[\s-]?learn|learn(?:\s+all\s+of)?|study(?:\s+all\s+of)?|research|master|build\s+knowledge\s+(?:of|about|on))\s+(.+?)\s*[.!?]?\s*$",
        low)
    if en:
        verb = en.group(1)
        topic = text[text.lower().find(en.group(2)):].strip(" .!?,")
        is_deep = ("deep" in verb) or ("all of" in verb)
        return (topic, "deep" if is_deep else "narrow")
    he_verb = r"(?:תלמד|למד|ללמוד|תחקור|לחקור|תבנה\s+(?:לי\s+)?ידע(?:\s+על)?)"
    he = re.match(r"^\s*" + he_verb + r"\s+(.+)$", text)
    if he:
        rest = he.group(1).strip()
        is_deep = ("לעומק" in rest) or ("כל ה" in rest) or ("את כל" in rest)
        topic = rest
        topic = re.sub(r"\bלעומק\b", "", topic).strip()
        topic = re.sub(r"^את\s+כל\s+ה", "", topic).strip()
        topic = re.sub(r"^את\s+ה", "", topic).strip()
        topic = re.sub(r"^את\s+", "", topic).strip()
        topic = re.sub(r"^כל\s+ה", "", topic).strip()
        topic = topic.strip(" .!?,:")
        if topic:
            return (topic, "deep" if is_deep else "narrow")
    return None

def _whats_new_intercept(msg):
    if not msg or not isinstance(msg, str):
        return False
    low = msg.lower().strip()
    en_triggers = [
        "what's new", "whats new", "what is new", "anything new",
        "what changed", "what's changed", "whats changed",
        "what did you add", "what did we add",
        "what's been added", "what's different",
        "recent changes", "any updates",
    ]
    if any(t in low for t in en_triggers):
        return True
    he_triggers = [
        "מה השתנה", "מה חדש", "מה הוספנו", "מה הוספת",
        "מה שינית", "מה שינינו", "מה התווסף", "מה התעדכן",
        "מה עדכנו", "מה עדכנת",
    ]
    if any(t in msg for t in he_triggers):
        return True
    return False

def whats_new(lang="en"):
    try:
        src = Path(__file__).read_text(encoding="utf-8")
    except Exception:
        return ("לא הצלחתי לקרוא את עצמי, אדוני." if lang == "he"
                else "I can't read my own source right now, sir.")
    m = re.search(r'Changelog:\s*\n(.+?)"""', src, re.DOTALL)
    if not m:
        return ("אין לי changelog זמין, אדוני." if lang == "he"
                else "I don't have a changelog to show, sir.")
    body = m.group(1)
    entries = re.findall(
        r'^  (v\d+\.\d+\s+-\s+.+?)(?=^  v\d+\.\d+\s+-\s+|\Z)',
        body, re.MULTILINE | re.DOTALL)
    if not entries:
        return ("ה-changelog ריק, אדוני." if lang == "he"
                else "The changelog is empty, sir.")
    cleaned = []
    for e in entries[:3]:
        flat = " ".join(line.strip() for line in e.splitlines() if line.strip())
        cleaned.append(flat)
    facts = "\n".join("- " + c for c in cleaned)
    if not ANTHROPIC_API_KEY:
        return (("השינויים האחרונים, אדוני:\n" + facts) if lang == "he"
                else ("Recent changes, sir:\n" + facts))
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        sys_p = (
            "You are Achilles, a calm British-butler AI assistant. The user "
            "asked what changed recently. Summarise the last few Changelog "
            "entries in 2-4 short sentences in "
            + ("Hebrew" if lang == "he" else "English")
            + ". Address the user as 'sir' (or 'אדוני'). Focus on what is new "
            "for the USER. Plain text only.")
        r = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=300,
            system=sys_p, messages=[{"role": "user", "content": facts}])
        parts = [b.text for b in r.content if getattr(b, "type", None) == "text"]
        reply = " ".join(p.strip() for p in parts if p.strip()).strip()
        return clean_text(reply) or facts
    except Exception:
        return facts

def _system_health_intercept(msg):
    if not msg or not isinstance(msg, str):
        return False
    low = msg.lower().strip()
    en_triggers = [
        "system health", "health check", "status check",
        "self check", "self-check", "selfcheck",
        "are you ok", "are you okay", "are you alright",
        "is everything ok", "is everything okay",
        "everything working", "everything alright",
        "system status", "diagnostics",
        "run a check", "run diagnostics", "check yourself",
    ]
    if any(t in low for t in en_triggers):
        return True
    he_triggers = [
        "בדיקה עצמית", "בדוק את עצמך", "בדיקת מערכת",
        "בריאות מערכת", "בריאות המערכת", "מצב המערכת",
        "מצב מערכת", "סטטוס מערכת", "האם הכל תקין",
        "הכל עובד", "הכל תקין", "תבדוק שהכל",
        "הרץ בדיקה", "אבחון מערכת",
    ]
    if any(t in msg for t in he_triggers):
        return True
    return False

def system_health(lang="en"):
    import socket as _socket_mod
    facts = []
    if ANTHROPIC_API_KEY and ANTHROPIC_API_KEY.startswith("sk-ant-"):
        facts.append("Anthropic key: OK (loaded, %d chars)" % len(ANTHROPIC_API_KEY))
    elif ANTHROPIC_API_KEY:
        facts.append("Anthropic key: WARN (loaded but format looks off)")
    else:
        facts.append("Anthropic key: FAIL (missing from .env - brain offline)")
    if ELEVENLABS_API_KEY:
        facts.append("ElevenLabs key: OK (loaded, %d chars)" % len(ELEVENLABS_API_KEY))
    else:
        facts.append("ElevenLabs key: WARN (missing - English voice falls back to edge-tts)")
    if GOOGLE_MAPS_API_KEY:
        facts.append("Google Maps key: OK (loaded)")
    else:
        facts.append("Google Maps key: WARN (missing - places/directions/WorldView won't work)")
    if not os.path.exists(CAL_CREDENTIALS_FILE):
        facts.append("Google Calendar + Gmail: WARN (not configured - no credentials.json)")
    elif not os.path.exists(CAL_TOKEN_FILE):
        facts.append("Google Calendar + Gmail: WARN (no token yet - first sign-in needed)")
    else:
        try:
            _gc_svc = _calendar_service()
            if _gc_svc is None:
                facts.append("Google Calendar + Gmail: FAIL (auth dead - run reauth_google.py)")
            else:
                _gc_svc.calendarList().list(maxResults=1).execute()
                facts.append("Google Calendar + Gmail: OK (live probe passed)")
        except Exception as _gc_e:
            facts.append("Google Calendar + Gmail: FAIL (live probe error: %s)" % type(_gc_e).__name__)
    if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET:
        if _SPOTIFY_TOKEN_FILE.exists():
            facts.append("Spotify: OK (credentials and token present)")
        else:
            facts.append("Spotify: WARN (credentials present, no token - first sign-in needed)")
    else:
        facts.append("Spotify: WARN (client id/secret missing from .env)")
    try:
        wv = Path(__file__).resolve().parent / "worldview.html"
        facts.append("WorldView file: OK (worldview.html present)" if wv.exists()
                     else "WorldView file: WARN (worldview.html missing)")
    except Exception as e:
        facts.append("WorldView file: WARN (%s)" % e)
    try:
        kn = Path(KNOWLEDGE_DIR)
        if kn.exists():
            doms = [p for p in kn.iterdir() if p.is_dir()]
            facts.append("Knowledge folder: OK (%d domain(s) on disk)" % len(doms))
        else:
            facts.append("Knowledge folder: WARN (not created yet)")
    except Exception as e:
        facts.append("Knowledge folder: WARN (%s)" % e)
    try:
        with _deep_learn_lock:
            running = _deep_learn_state["running"]
            domain = _deep_learn_state["domain"]
            done = _deep_learn_state["done"]
            total = _deep_learn_state["total"]
        if running and domain:
            facts.append("Background learning: OK (running - %s, %d/%d this run)"
                         % (domain, done, total))
        else:
            facts.append("Background learning: OK (idle)")
    except Exception as e:
        facts.append("Background learning: WARN (%s)" % e)
    try:
        s = _socket_mod.create_connection(("1.1.1.1", 53), timeout=2)
        s.close()
        facts.append("Internet: OK (reachable)")
    except Exception:
        facts.append("Internet: FAIL (unreachable - most tools will not work)")
    raw = "\n".join(facts)
    if not ANTHROPIC_API_KEY:
        return raw
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        sys_p = (
            "You are Achilles, a calm British-butler AI assistant. The user asked "
            "for a quick system health check. Below are components and statuses "
            "(OK / WARN / FAIL). Reply in 2-4 short sentences in "
            + ("Hebrew" if lang == "he" else "English")
            + ". Address the user as 'sir' (or 'אדוני'). Lead with the headline, "
            "then name warnings/failures. Plain text, no markdown.")
        r = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=300,
            system=sys_p, messages=[{"role": "user", "content": raw}])
        parts = [b.text for b in r.content if getattr(b, "type", None) == "text"]
        reply = " ".join(p.strip() for p in parts if p.strip()).strip()
        return clean_text(reply) or raw
    except Exception:
        return raw

def _learned_this_week_intercept(msg):
    if not msg or not isinstance(msg, str):
        return False
    low = msg.lower().strip()
    en_triggers = [
        "what did i learn this week", "what have i learned this week",
        "what did i study this week", "weekly learning summary",
        "what did we learn this week", "this week's notes",
        "what did i learn lately", "what have i learned lately",
        "learning summary", "what did i learn recently",
        "what have we learned",
    ]
    if any(t in low for t in en_triggers):
        return True
    he_triggers = [
        "מה למדתי השבוע", "מה למדנו השבוע",
        "מה למדתי לאחרונה", "מה למדנו לאחרונה",
        "סיכום למידה", "סיכום השבוע",
        "מה נלמד השבוע", "מה למדת לאחרונה", "מה למדת השבוע",
    ]
    if any(t in msg for t in he_triggers):
        return True
    return False

def learned_this_week(lang="en"):
    try:
        base = Path(KNOWLEDGE_DIR)
        if not base.exists():
            return ("אין עדיין תיקיית ידע, אדוני." if lang == "he"
                    else "There's no knowledge folder yet, sir.")
        cutoff = datetime.datetime.now() - datetime.timedelta(days=7)
        by_domain = {}
        standalone = []
        for f in base.rglob("*.md"):
            if f.name.startswith("_"):
                continue
            try:
                mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
                if mtime < cutoff:
                    continue
            except Exception:
                continue
            try:
                head = "\n".join(f.read_text(encoding="utf-8").splitlines()[:30])
            except Exception:
                continue
            title = None
            m = re.search(r"^title:\s*[\"']?(.+?)[\"']?\s*$", head, re.MULTILINE)
            if m:
                title = m.group(1).strip()
            else:
                m = re.search(r"^#\s+(.+?)\s*$", head, re.MULTILINE)
                if m:
                    title = m.group(1).strip()
            if not title:
                title = f.stem.replace("_", " ")
            try:
                rel = f.relative_to(base)
                if len(rel.parts) > 1:
                    by_domain.setdefault(rel.parts[0], []).append(title)
                else:
                    standalone.append(title)
            except Exception:
                standalone.append(title)
        total = sum(len(v) for v in by_domain.values()) + len(standalone)
        if total == 0:
            return ("השבוע לא נוצרו פתקי ידע, אדוני." if lang == "he"
                    else "No knowledge notes were created in the past week, sir.")
        lines = []
        for domain, titles in sorted(by_domain.items()):
            d_name = domain.replace("_", " ")
            lines.append("%s (%d notes): %s" % (d_name, len(titles), ", ".join(titles)))
        if standalone:
            lines.append("standalone (%d): %s" % (len(standalone), ", ".join(standalone)))
        facts = ("Total notes in the past 7 days: %d.\n" % total + "\n".join(lines))
        if not ANTHROPIC_API_KEY:
            return facts
        try:
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            sys_p = (
                "You are Achilles, a calm British-butler AI assistant. The user "
                "asked for a summary of what was learned this week. Below is the "
                "list of notes from the past 7 days, grouped by domain. Reply in "
                "2-4 short sentences in "
                + ("Hebrew" if lang == "he" else "English")
                + ". Address them as 'sir' (or 'אדוני'). Lead with the total and "
                "main domain(s). Plain text, no markdown.")
            r = client.messages.create(
                model="claude-sonnet-4-6", max_tokens=350,
                system=sys_p, messages=[{"role": "user", "content": facts}])
            parts = [b.text for b in r.content if getattr(b, "type", None) == "text"]
            reply = " ".join(p.strip() for p in parts if p.strip()).strip()
            return clean_text(reply) or facts
        except Exception:
            return facts
    except Exception as e:
        return ("נכשלתי לסכם את הלמידה השבוע, אדוני: %s" % e if lang == "he"
                else "Failed to summarise weekly learning, sir: %s" % e)

_last_action_lock = threading.Lock()
_last_action = {"type": None, "data": None}

def _record_action(action_type, data):
    with _last_action_lock:
        _last_action["type"] = action_type
        _last_action["data"] = data

def undo_last():
    with _last_action_lock:
        atype = _last_action.get("type")
        data = _last_action.get("data") or {}
        _last_action["type"] = None
        _last_action["data"] = None
    if not atype:
        return "Nothing to undo, sir."
    try:
        if atype == "calendar_add":
            event_id = data.get("event_id", "")
            summary = data.get("summary", "")
            if not event_id:
                return "Can't undo - I don't have the event id, sir."
            svc = _calendar_service()
            if svc is None:
                return "Can't undo - calendar isn't connected, sir."
            svc.events().delete(calendarId="primary", eventId=event_id).execute()
            return "Undone, sir. Removed '%s'." % (summary or "the event")
        if atype == "calendar_delete":
            body = data.get("body") or {}
            summary = body.get("summary", "the event")
            svc = _calendar_service()
            if svc is None:
                return "Can't undo - calendar isn't connected, sir."
            if not body.get("start") or not body.get("end"):
                return "Can't undo - the cached event is incomplete, sir."
            svc.events().insert(calendarId="primary", body=body).execute()
            return "Undone, sir. Restored '%s'." % summary
        if atype == "save_note":
            path = data.get("path", "")
            written = data.get("written", "")
            if not path or not os.path.exists(path):
                return "Can't undo - the note file is gone, sir."
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                return "Can't read the note file, sir: %s" % e
            if written and content.endswith(written):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content[:-len(written)])
                return "Undone, sir. Removed the last note."
            return "Can't undo - the note file changed since I wrote it, sir."
        if atype == "set_timer":
            timer = data.get("timer")
            label = data.get("label") or ""
            if timer is not None:
                try:
                    timer.cancel()
                except Exception:
                    pass
                try:
                    if timer in _active_timers:
                        _active_timers.remove(timer)
                except Exception:
                    pass
            return ("Timer cancelled%s, sir." % ((" (%s)" % label) if label else ""))
        return "I don't know how to undo that, sir."
    except Exception as e:
        return "Undo failed: %s" % e

def _undo_intercept(msg):
    if not msg or not isinstance(msg, str):
        return False
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג'?א?ר?ו+יס|gארוויס)[\s,:]*", "", text)
    text = text.strip().rstrip(".!?,")
    low = text.lower()
    en_triggers = {
        "undo", "undo it", "undo that", "undo last",
        "undo the last", "undo the last action", "undo last action",
        "revert", "revert that", "revert it", "revert the last",
        "cancel that", "cancel the last", "cancel last action",
        "scratch that", "take that back", "take it back",
        "nevermind that", "never mind that",
    }
    if low in en_triggers:
        return True
    he_triggers = {
        "תבטל", "תבטל את זה", "תבטל את הפעולה", "תבטל את האחרון",
        "בטל", "בטל את זה", "בטל את הפעולה", "בטל את האחרון",
        "ביטול", "ביטול אחרון", "ביטול פעולה",
        "אנדו", "תחזיר את זה", "תחזיר", "תחזור אחורה",
    }
    if text in he_triggers:
        return True
    return False

_usage_lock = threading.Lock()
_USAGE_FILE = Path("anthropic_usage.json")
try:
    _BUDGET_USD = float(os.getenv("JARVIS_MONTHLY_BUDGET_USD", "50"))
except Exception:
    _BUDGET_USD = 50.0

_DEFAULT_ANTHROPIC_PRICING = {
    "sonnet": {"input": 3.00,  "output": 15.00},
    "opus":   {"input": 15.00, "output": 75.00},
    "haiku":  {"input": 0.80,  "output": 4.00},
}

def _model_pricing(model_name):
    low = (model_name or "").lower()
    if "opus" in low:
        return _DEFAULT_ANTHROPIC_PRICING["opus"]
    if "haiku" in low:
        return _DEFAULT_ANTHROPIC_PRICING["haiku"]
    return _DEFAULT_ANTHROPIC_PRICING["sonnet"]

def _load_usage():
    if not _USAGE_FILE.exists():
        return {}
    try:
        return json.loads(_USAGE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_usage(data):
    try:
        _USAGE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print("[diag] usage save failed:", repr(e))

def _track_anthropic_usage(response):
    try:
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        in_tok = getattr(usage, "input_tokens", 0) or 0
        out_tok = getattr(usage, "output_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0
        in_tok += cache_read + cache_create
        model = getattr(response, "model", "")
        pricing = _model_pricing(model)
        cost = (in_tok * pricing["input"] + out_tok * pricing["output"]) / 1_000_000.0
        crossed_80 = False
        crossed_100 = False
        with _usage_lock:
            data = _load_usage()
            month_key = datetime.date.today().strftime("%Y-%m")
            months = data.setdefault("months", {})
            m = months.setdefault(month_key, {
                "input_tokens": 0, "output_tokens": 0,
                "cost_usd": 0.0, "calls": 0,
                "warned_80": False, "warned_100": False,
            })
            m["input_tokens"] += in_tok
            m["output_tokens"] += out_tok
            m["cost_usd"] = round(m["cost_usd"] + cost, 6)
            m["calls"] += 1
            data["last_update"] = datetime.datetime.now().isoformat(timespec="seconds")
            pct = (m["cost_usd"] / _BUDGET_USD * 100.0 if _BUDGET_USD > 0 else 0)
            if pct >= 100 and not m["warned_100"]:
                m["warned_100"] = True
                crossed_100 = True
            elif pct >= 80 and not m["warned_80"]:
                m["warned_80"] = True
                crossed_80 = True
            _save_usage(data)
        if crossed_100:
            threading.Thread(target=_budget_alert, args=("over",), daemon=True).start()
        elif crossed_80:
            threading.Thread(target=_budget_alert, args=("warning",), daemon=True).start()
    except Exception as e:
        print("[diag] usage tracking failed:", repr(e))

def _budget_alert(level):
    if level == "over":
        msg = ("Sir, you've exceeded the monthly API budget of $%.0f. "
               "Consider pausing background learning." % _BUDGET_USD)
    else:
        msg = ("Sir, you've used 80%% of the monthly $%.0f API budget. Heads up." % _BUDGET_USD)
    try:
        if APP is not None:
            APP.ui(lambda m=msg: APP._push("JARVIS", m))
    except Exception:
        pass
    try:
        speak(msg)
    except Exception:
        pass

def budget_status(lang="en"):
    try:
        data = _load_usage()
        month_key = datetime.date.today().strftime("%Y-%m")
        m = data.get("months", {}).get(month_key, {})
        spent = float(m.get("cost_usd", 0.0))
        calls = int(m.get("calls", 0))
        in_tok = int(m.get("input_tokens", 0))
        out_tok = int(m.get("output_tokens", 0))
        pct = (spent / _BUDGET_USD * 100.0) if _BUDGET_USD > 0 else 0
        if lang == "he":
            return ("החודש הוצאת %.2f דולר מתוך %.0f דולר, %.0f אחוזים, "
                    "אדוני. %d קריאות API, %s טוקנים בקלט ו-%s טוקנים בפלט."
                    % (spent, _BUDGET_USD, pct, calls,
                       "{:,}".format(in_tok), "{:,}".format(out_tok)))
        return ("Sir, you've spent $%.2f of your $%.0f monthly cap "
                "(%.0f%%) - %d API calls, %s input tokens and %s output tokens."
                % (spent, _BUDGET_USD, pct, calls,
                   "{:,}".format(in_tok), "{:,}".format(out_tok)))
    except Exception as e:
        if lang == "he":
            return "לא הצלחתי לקרוא את התקציב, אדוני: %s" % e
        return "Couldn't read the budget, sir: %s" % e

def _budget_intercept(msg):
    if not msg or not isinstance(msg, str):
        return False
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג'?א?ר?ו+יס|gארוויס)[\s,:]*", "", text)
    low = text.lower().strip().rstrip(".!?,")
    en_triggers = {
        "budget", "my budget", "the budget",
        "what's my budget", "whats my budget", "what is my budget",
        "show me the budget", "show my budget",
        "api budget", "api cost", "api spending", "api spend",
        "cost status", "monthly cost", "monthly spend",
        "how much have i spent", "how much did i spend",
        "how much is the api costing",
    }
    if low in en_triggers:
        return True
    he_triggers = {
        "התקציב", "מה התקציב", "מה התקציב שלי",
        "תקציב ה-API", "תקציב החודש", "מצב התקציב",
        "כמה הוצאתי", "כמה זה עולה", "כמה ביזבזתי", "עלות ה-API",
    }
    if text in he_triggers:
        return True
    if any(t in text for t in ("מה התקציב", "כמה הוצאתי", "מצב התקציב")):
        return True
    return False

try:
    from anthropic.resources.messages import Messages as _AnthMessages
    if not hasattr(_AnthMessages, "_jarvis_patched"):
        _orig_anth_create = _AnthMessages.create
        def _wrapped_anth_create(self, *args, **kwargs):
            response = _orig_anth_create(self, *args, **kwargs)
            try:
                _track_anthropic_usage(response)
            except Exception:
                pass
            return response
        _AnthMessages.create = _wrapped_anth_create
        _AnthMessages._jarvis_patched = True
        print("[diag] Anthropic usage tracking active (budget cap $%.0f/month)"
              % _BUDGET_USD, flush=True)
except Exception as _patch_err:
    print("[diag] anthropic usage tracking patch failed:", repr(_patch_err), flush=True)

BACKUP_DIR = Path("./backups")
BACKUP_KEEP = 14
VAULT_DIR = Path("./Obsidian_Vault")

def backup_vault():
    import zipfile
    try:
        if not VAULT_DIR.exists():
            return "No vault to back up, sir."
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        fname = BACKUP_DIR / ("obsidian_vault_" + ts + ".zip")
        n_files = 0
        total_bytes = 0
        skipped = 0
        with zipfile.ZipFile(fname, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for f in VAULT_DIR.rglob("*"):
                if not f.is_file():
                    continue
                try:
                    arcname = f.relative_to(VAULT_DIR.parent)
                    z.write(f, arcname)
                    n_files += 1
                    total_bytes += f.stat().st_size
                except Exception as fe:
                    skipped += 1
                    print("[diag] backup skip:", f, repr(fe))
        existing = sorted(BACKUP_DIR.glob("obsidian_vault_*.zip"),
                          key=lambda p: p.stat().st_mtime, reverse=True)
        pruned = 0
        for old in existing[BACKUP_KEEP:]:
            try:
                old.unlink()
                pruned += 1
            except Exception:
                pass
        size_mb = total_bytes / 1024.0 / 1024.0
        zip_size_mb = fname.stat().st_size / 1024.0 / 1024.0
        tail = ""
        if skipped:
            tail += " %d files skipped." % skipped
        if pruned:
            tail += " %d old backups pruned." % pruned
        return ("Backed up %d files - %.1f MB raw, %.1f MB zipped - to %s, sir. "
                "Keeping the last %d backups.%s"
                % (n_files, size_mb, zip_size_mb, fname.name, BACKUP_KEEP, tail))
    except Exception as e:
        print("[diag] backup_vault failed:", repr(e))
        return "Backup failed, sir: %s" % e

def _backup_intercept(msg):
    if not msg or not isinstance(msg, str):
        return False
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג'?א?ר?ו+יס|gארוויס)[\s,:]*", "", text)
    text = text.strip().rstrip(".!?,")
    low = text.lower()
    en_triggers = {
        "backup", "back up", "backup now", "back up now",
        "backup my notes", "back up my notes",
        "backup the vault", "backup my vault", "back up the vault",
        "backup the notes", "back up the notes",
        "create a backup", "create backup", "make a backup", "make backup",
        "run a backup", "run backup", "save a backup", "save backup",
    }
    if low in en_triggers:
        return True
    he_triggers = {
        "גיבוי", "גבה", "גבה לי", "גבה את הפתקים", "גבה את הכספת",
        "תגבה", "תגבה לי", "תגבה את הפתקים", "תגבה את הכספת",
        "תיצור גיבוי", "עשה גיבוי", "רוץ גיבוי", "הרץ גיבוי",
    }
    if text in he_triggers:
        return True
    return False

DECISIONS_FILE = Path("./Obsidian_Vault/Decisions.md")

def log_decision(text):
    if not text or not text.strip():
        return "What decision should I log, sir?"
    try:
        DECISIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.datetime.now()
        new_file = not DECISIONS_FILE.exists()
        with open(DECISIONS_FILE, "a", encoding="utf-8") as f:
            if new_file:
                f.write("# Decisions Log\n\n")
            f.write("## %s\n%s\n\n" % (now.strftime("%Y-%m-%d %H:%M"), text.strip()))
        return "Decision logged, sir."
    except Exception as e:
        return "Failed to log the decision, sir: %s" % e

def recent_decisions(n=5, lang="en"):
    try:
        if not DECISIONS_FILE.exists():
            return ("עדיין לא רשמת החלטות, אדוני." if lang == "he"
                    else "No decisions logged yet, sir.")
        text = DECISIONS_FILE.read_text(encoding="utf-8")
        entries = re.findall(r"^## (.+?)\n(.+?)(?=\n## |\Z)", text,
                             re.MULTILINE | re.DOTALL)
        if not entries:
            return ("עדיין לא רשמת החלטות, אדוני." if lang == "he"
                    else "No decisions logged yet, sir.")
        recent = entries[-n:]
        recent.reverse()
        lines = []
        for when, body in recent:
            try:
                d = datetime.datetime.strptime(when.strip(), "%Y-%m-%d %H:%M").date()
                days = (datetime.date.today() - d).days
                if lang == "he":
                    rel = ("היום" if days == 0 else "אתמול" if days == 1
                           else "לפני %d ימים" % days)
                else:
                    rel = ("today" if days == 0 else "yesterday" if days == 1
                           else "%d days ago" % days)
            except Exception:
                rel = when.strip()
            body_clean = " ".join(body.split())
            lines.append("%s: %s" % (rel, body_clean))
        facts = "\n".join(lines)
        if lang == "he":
            return "ההחלטות האחרונות שלך, אדוני:\n" + facts
        return "Your recent decisions, sir:\n" + facts
    except Exception as e:
        return "Couldn't read the decisions log, sir: %s" % e

def _decision_log_parse(msg):
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג'?א?ר?ו+יס|gארוויס)[\s,:]*", "", text)
    text = text.strip()
    m = re.match(r"(?:log|record|note|save)\s+(?:a\s+|the\s+)?decision[:\-\s]+(.+)$",
                 text, re.I)
    if m:
        return m.group(1).strip()
    m = re.match(r"(?:תרשום|רשום|תעד|תתעד)\s+(?:לי\s+)?(?:את\s+)?(?:ה)?החלטה[:\-\s]+(.+)$", text)
    if m:
        return m.group(1).strip()
    return None

def _decision_review_intercept(msg):
    if not msg or not isinstance(msg, str):
        return False
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג'?א?ר?ו+יס|gארוויס)[\s,:]*", "", text)
    text = text.strip().rstrip(".!?,")
    low = text.lower()
    en_triggers = {
        "my decisions", "show my decisions", "show decisions",
        "recent decisions", "list my decisions", "decision log",
        "what did i decide", "what have i decided", "read my decisions",
    }
    if low in en_triggers:
        return True
    he_triggers = {
        "ההחלטות שלי", "החלטות אחרונות", "ההחלטות האחרונות",
        "מה החלטתי", "יומן החלטות", "תראה לי את ההחלטות",
    }
    if text in he_triggers:
        return True
    return False

TRAINING_LOG_FILE = Path("./training_log.json")

def _load_training_log():
    if not TRAINING_LOG_FILE.exists():
        return {}
    try:
        return json.loads(TRAINING_LOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_training_log(data):
    try:
        TRAINING_LOG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    except Exception as e:
        print("[diag] training log save failed:", repr(e))

def _nutrition_reset_if_new_day(data):
    today = datetime.date.today().isoformat()
    if data.get("nutrition_date") != today:
        data["nutrition_date"] = today
        data["today_calories"] = 0
        data["today_protein_g"] = 0

def log_calories(n):
    try:
        n = int(round(float(n)))
    except Exception:
        return "How many calories, sir?"
    data = _load_training_log()
    _nutrition_reset_if_new_day(data)
    data["today_calories"] = int(data.get("today_calories", 0)) + n
    _save_training_log(data)
    tgt = data.get("target_calories", 3000)
    total = data["today_calories"]
    return ("Logged %d calories, sir. Today's total: %d of %d." % (n, total, tgt))

def log_protein(g):
    try:
        g = int(round(float(g)))
    except Exception:
        return "How many grams of protein, sir?"
    data = _load_training_log()
    _nutrition_reset_if_new_day(data)
    data["today_protein_g"] = int(data.get("today_protein_g", 0)) + g
    _save_training_log(data)
    tgt = data.get("target_protein_g", 130)
    total = data["today_protein_g"]
    return ("Logged %d grams of protein, sir. Today's total: %d of %d." % (g, total, tgt))

def nutrition_status(lang="en"):
    data = _load_training_log()
    _nutrition_reset_if_new_day(data)
    cal = int(data.get("today_calories", 0))
    pro = int(data.get("today_protein_g", 0))
    tcal = data.get("target_calories", 3000)
    tpro = data.get("target_protein_g", 130)
    cal_left = tcal - cal
    pro_left = tpro - pro
    if lang == "he":
        return ("היום, אדוני: %d מתוך %d קלוריות (%d נותרו), "
                "%d מתוך %d גרם חלבון (%d נותרו)."
                % (cal, tcal, max(0, cal_left), pro, tpro, max(0, pro_left)))
    return ("Today, sir: %d of %d calories (%d to go), %d of %d grams "
            "of protein (%d to go)."
            % (cal, tcal, max(0, cal_left), pro, tpro, max(0, pro_left)))

def _nutrition_log_parse(msg):
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג'?א?ר?ו+יס|gארוויס)[\s,:]*", "", text)
    low = text.lower()
    en_verb = re.search(r"\b(log|ate|eaten|add|added|track|had|consumed|just had)\b", low)
    if en_verb:
        mp = re.search(r"(\d+(?:\.\d+)?)\s*(?:grams?|g)\s*(?:of\s+)?protein", low)
        if mp:
            return ("protein", float(mp.group(1)))
        mp2 = re.search(r"protein[:\s]+(\d+(?:\.\d+)?)", low)
        if mp2:
            return ("protein", float(mp2.group(1)))
        mc = re.search(r"(\d+(?:\.\d+)?)\s*(?:k?cals?|calories|calorie|kcal)\b", low)
        if mc:
            return ("calories", float(mc.group(1)))
    he_verb = re.search(r"(אכלתי|תרשום|רשום|הוסף|תוסיף|צרכתי)", text)
    if he_verb:
        mp = re.search(r"(\d+(?:\.\d+)?)\s*(?:גרם\s+)?חלבון", text)
        if mp:
            return ("protein", float(mp.group(1)))
        mp2 = re.search(r"חלבון[:\s]+(\d+(?:\.\d+)?)", text)
        if mp2:
            return ("protein", float(mp2.group(1)))
        mc = re.search(r"(\d+(?:\.\d+)?)\s*(?:קלוריות|קלוריה|קק\"ל)", text)
        if mc:
            return ("calories", float(mc.group(1)))
    return None

def _nutrition_status_intercept(msg):
    if not msg or not isinstance(msg, str):
        return False
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג'?א?ר?ו+יס|gארוויס)[\s,:]*", "", text)
    text = text.strip().rstrip(".!?,")
    low = text.lower()
    en_triggers = {
        "nutrition", "nutrition status", "my nutrition",
        "macros", "my macros", "macro status",
        "calories today", "how many calories today",
        "protein today", "how much protein today",
        "what have i eaten", "what have i eaten today",
        "food log", "diet status", "how am i eating",
    }
    if low in en_triggers:
        return True
    he_triggers = {
        "תזונה", "מצב תזונה", "מאקרו", "המאקרו שלי",
        "כמה אכלתי", "כמה אכלתי היום", "קלוריות היום",
        "חלבון היום", "מה אכלתי היום",
    }
    if text in he_triggers:
        return True
    return False

_quiz_lock = threading.Lock()
_quiz_state = {"active": False, "question": "", "answer": "", "topic": ""}

def _pick_quiz_note(topic):
    import random
    base = Path(KNOWLEDGE_DIR)
    if not base.exists():
        return None, None
    candidates = [f for f in base.rglob("*.md") if not f.name.startswith("_")]
    if not candidates:
        return None, None
    if topic:
        slug = _slugify_topic(topic)
        matched = []
        for f in candidates:
            dom = _slugify_topic(f.parent.name)
            if (slug and (slug in dom or dom in slug or slug in f.stem.lower())):
                matched.append(f)
        if matched:
            candidates = matched
    note = random.choice(candidates)
    try:
        content = note.read_text(encoding="utf-8")[:6000]
    except Exception:
        return None, None
    return note, content

def start_quiz(topic, lang="en"):
    if not ANTHROPIC_API_KEY:
        return ("לא ניתן להריץ חידון - מפתח Anthropic לא מוגדר, אדוני."
                if lang == "he"
                else "Can't run a quiz - the Anthropic key isn't set, sir.")
    note, content = _pick_quiz_note(topic)
    if not content:
        if topic:
            return (("אין לי פתקי ידע על %s עדיין, אדוני. בקש ממני "
                     "ללמוד את זה קודם." % topic) if lang == "he"
                    else ("I don't have knowledge notes on %s yet, sir. "
                          "Ask me to learn it first." % topic))
        return ("אין לי פתקי ידע לבחון אותך עליהם עדיין, אדוני."
                if lang == "he"
                else "I have no knowledge notes to quiz you on yet, sir.")
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        sys_p = (
            "You are a quizmaster. From the study note below, write ONE clear "
            "exam-style question that tests real understanding, plus a concise "
            "model answer. Output EXACTLY two lines and nothing else:\n"
            "Q: <question>\nA: <model answer>\nWrite in "
            + ("Hebrew" if lang == "he" else "English") + ".")
        r = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=400,
            system=sys_p, messages=[{"role": "user", "content": content}])
        txt = " ".join(b.text for b in r.content
                       if getattr(b, "type", None) == "text").strip()
        mq = re.search(r"Q:\s*(.+?)(?:\nA:|A:)", txt, re.DOTALL)
        ma = re.search(r"A:\s*(.+)$", txt, re.DOTALL)
        if not mq or not ma:
            return ("לא הצלחתי לנסח שאלה, אדוני. נסה שוב." if lang == "he"
                    else "I couldn't form a question, sir. Try again.")
        q = mq.group(1).strip()
        a = ma.group(1).strip()
    except Exception as e:
        return "Quiz generation failed, sir: %s" % e
    with _quiz_lock:
        _quiz_state.update(active=True, question=q, answer=a,
                           topic=(topic or note.stem))
    if lang == "he":
        return "שאלה, אדוני: " + q + " אמור את התשובה כשתהיה מוכן."
    return "Question, sir: " + q + " Tell me your answer when ready."

def evaluate_quiz_answer(user_answer, lang="en"):
    with _quiz_lock:
        if not _quiz_state["active"]:
            return None
        q = _quiz_state["question"]
        expected = _quiz_state["answer"]
        _quiz_state.update(active=False, question="", answer="", topic="")
    ans = (user_answer or "").strip()
    cancel = {"stop", "cancel", "never mind", "nevermind", "forget it",
              "עזוב", "בטל", "עצור", "די", "לא עכשיו"}
    _al = ans.lower()
    _words = set(re.split(r"[\s,.!?]+", _al))
    # Always let the user bail - match cancel words anywhere, not just exact.
    if (_al in cancel or ans in cancel
            or _words & {"stop", "cancel", "forget", "nevermind"}
            or any(w in ans for w in ("עזוב", "בטל", "עצור"))):
        return ("ביטלתי את החידון, אדוני." if lang == "he"
                else "Quiz cancelled, sir.")
    if not ANTHROPIC_API_KEY:
        return (("התשובה שחיפשתי, אדוני: " + expected) if lang == "he"
                else ("The expected answer, sir: " + expected))
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        sys_p = (
            "You are a supportive but honest tutor grading a spoken answer. "
            "Given the question, the model answer, and the student's answer, "
            "say in 2-3 sentences whether the student was correct, partially "
            "correct, or wrong, and give the key point they missed if any. "
            "Address them as 'sir' (or 'אדוני'). Write in "
            + ("Hebrew" if lang == "he" else "English") + ". Plain text.")
        prompt = ("Question: %s\nModel answer: %s\nStudent's answer: %s"
                  % (q, expected, ans))
        r = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=300,
            system=sys_p, messages=[{"role": "user", "content": prompt}])
        fb = " ".join(b.text for b in r.content
                      if getattr(b, "type", None) == "text").strip()
        return clean_text(fb) or ("The expected answer was: " + expected)
    except Exception as e:
        return ("Couldn't grade that, sir: %s. Expected answer: %s" % (e, expected))

def _quiz_start_parse(msg):
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג'?א?ר?ו+יס|gארוויס)[\s,:]*", "", text)
    text = text.strip().rstrip(".!?,")
    low = text.lower()
    m = re.match(r"(?:quiz|test)\s+me(?:\s+on\s+(.+))?$", low)
    if m:
        return (m.group(1) or "").strip()
    m = re.match(r"(?:give me a quiz|quiz time|test my knowledge|self test|self-test)(?:\s+on\s+(.+))?$", low)
    if m:
        return (m.group(1) or "").strip()
    m = re.match(r"(?:תבחן|תשאל|שאל)\s+אותי(?:\s+על\s+(.+))?$", text)
    if m:
        return (m.group(1) or "").strip()
    m = re.match(r"חידון(?:\s+על\s+(.+))?$", text)
    if m:
        return (m.group(1) or "").strip()
    return None

def log_injury(text, lang="en"):
    if not text or not text.strip():
        return ("איזו פציעה לרשום, אדוני?" if lang == "he"
                else "What injury should I log, sir?")
    data = _load_training_log()
    injuries = data.setdefault("injuries", [])
    injuries.append({"desc": text.strip(),
                     "logged": datetime.date.today().isoformat(),
                     "status": "active", "recovered": None})
    _save_training_log(data)
    if lang == "he":
        return "רשמתי את הפציעה, אדוני: %s. תנוח." % text.strip()
    return "Injury logged, sir: %s. Rest up." % text.strip()

def injury_status(lang="en"):
    data = _load_training_log()
    injuries = data.get("injuries", [])
    active = [i for i in injuries if i.get("status") == "active"]
    if not active:
        return ("אין פציעות פעילות, אדוני. הכל תקין." if lang == "he"
                else "No active injuries, sir. All clear.")
    lines = []
    for inj in active:
        try:
            d = datetime.date.fromisoformat(inj.get("logged", ""))
            days = (datetime.date.today() - d).days
            if lang == "he":
                rel = ("היום" if days == 0 else "אתמול" if days == 1
                       else "לפני %d ימים" % days)
            else:
                rel = ("today" if days == 0 else "yesterday" if days == 1
                       else "%d days ago" % days)
        except Exception:
            rel = ""
        desc = inj.get("desc", "?")
        lines.append(("%s (%s)" % (desc, rel)) if rel else desc)
    facts = "; ".join(lines)
    if lang == "he":
        return "פציעות פעילות, אדוני: " + facts
    return "Active injuries, sir: " + facts

def mark_recovered(keyword, lang="en"):
    data = _load_training_log()
    injuries = data.get("injuries", [])
    kw = (keyword or "").strip().lower()
    matched = None
    if kw:
        for inj in injuries:
            if (inj.get("status") == "active" and kw in inj.get("desc", "").lower()):
                matched = inj
                break
    if matched is None:
        active = [i for i in injuries if i.get("status") == "active"]
        if len(active) == 1:
            matched = active[0]
    if matched is None:
        return ("לא מצאתי פציעה פעילה שמתאימה, אדוני." if lang == "he"
                else "I couldn't find a matching active injury, sir.")
    matched["status"] = "recovered"
    matched["recovered"] = datetime.date.today().isoformat()
    _save_training_log(data)
    desc = matched.get("desc", "")
    if lang == "he":
        return "מצוין, אדוני. סימנתי כהחלים: " + desc
    return "Great, sir. Marked as recovered: " + desc

def _injury_log_parse(msg):
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג'?א?ר?ו+יס|gארוויס)[\s,:]*", "", text)
    text = text.strip()
    m = re.match(r"(?:log|record|note)\s+(?:an?\s+)?injury[:\-\s]+(.+)$", text, re.I)
    if m:
        return m.group(1).strip()
    m = re.match(r"i\s+(?:hurt|injured|strained|pulled|tweaked)\s+(?:my\s+)?(.+)$", text, re.I)
    if m:
        return m.group(1).strip()
    m = re.match(r"(?:תרשום|רשום|תעד)\s+(?:לי\s+)?(?:את\s+)?פציעה[:\-\s]+(.+)$", text)
    if m:
        return m.group(1).strip()
    m = re.match(r"נפצעתי\s+(?:ב|באזור\s+)?(.+)$", text)
    if m:
        return m.group(1).strip()
    return None

def _injury_recovered_parse(msg):
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג'?א?ר?ו+יס|gארוויס)[\s,:]*", "", text)
    text = text.strip().rstrip(".!?,")
    m = re.match(r"(?:injury\s+recovered|recovered\s+from|healed\s+from)[:\-\s]+(.+)$", text, re.I)
    if m:
        return m.group(1).strip()
    # Require a "my <body-part>" shape so generic sentences like
    # "everything is better" / "the weather is better" don't falsely clear an
    # injury (mark_recovered would otherwise fall back to the single active one).
    m = re.match(r"my\s+([\w' ]{1,20}?)\s+(?:has\s+|is\s+)?(?:healed|recovered|better)$", text, re.I)
    if m and len(m.group(1).split()) <= 3:
        return m.group(1).strip()
    m = re.match(r"(?:החלמתי|נרפאתי)\s+(?:מה|מ)?(.+)$", text)
    if m:
        return m.group(1).strip()
    return None

def _injury_status_intercept(msg):
    if not msg or not isinstance(msg, str):
        return False
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג'?א?ר?ו+יס|gארוויס)[\s,:]*", "", text)
    text = text.strip().rstrip(".!?,")
    low = text.lower()
    en_triggers = {
        "injury status", "injuries", "my injuries", "am i injured",
        "injury report", "any injuries", "what injuries",
        "current injuries", "injury check",
    }
    if low in en_triggers:
        return True
    he_triggers = {
        "מצב פציעות", "פציעות", "הפציעות שלי", "מה הפציעות",
        "יש לי פציעות", "דוח פציעות",
    }
    if text in he_triggers:
        return True
    return False

def _classify_workout(text):
    low = (text or "").lower()
    he_swim = ["שחיתי", "שחייה", "שחיה"]
    he_cardio = ["רצתי", "ריצה", "רץ", "אופניים", "קרדיו", "ספרינט"]
    he_strength = ["סקוואט", "לחיצה", "דדליפט", "משקולות", "כוח", "סטים",
                   "חזרות", "מתח", "שכיבות", "קילו", "רגליים", "חזה", "גב",
                   "כתפיים", "ידיים", "בטן", "ביצפס", "טריצפס"]
    en_swim = ["swim", "swam", "swimming"]
    en_cardio = ["run", "running", "ran", "jog", "jogging", "jogged",
                 "cardio", "cycle", "cycling", "bike", "biked", "row",
                 "rowing", "sprint", "sprinted", "treadmill", "5k", "10k"]
    en_strength = ["squat", "squats", "bench", "deadlift", "press", "lift",
                   "lifted", "lifting", "sets", "set", "reps", "rep", "kg",
                   "pullup", "pull-up", "pull up", "pullups", "pushup",
                   "push-up", "push up", "pushups", "curl", "curls", "ohp",
                   "chest", "back", "legs", "leg", "shoulders", "arms",
                   "biceps", "triceps", "glutes", "abs", "quads",
                   "hamstrings", "calves", "upper body", "lower body"]
    for kw in he_swim:
        if kw in low:
            return "swim"
    for kw in he_cardio:
        if kw in low:
            return "cardio"
    for kw in he_strength:
        if kw in low:
            return "strength"
    def _has(kw):
        return re.search(r"\b" + re.escape(kw) + r"\b", low) is not None
    for kw in en_swim:
        if _has(kw):
            return "swim"
    for kw in en_cardio:
        if _has(kw):
            return "cardio"
    for kw in en_strength:
        if _has(kw):
            return "strength"
    return "general"

def _iso_week_tag(d=None):
    d = d or datetime.date.today()
    iso = d.isocalendar()
    return "%d-W%02d" % (iso[0], iso[1])

def log_workout(text, lang="en"):
    if not text or not text.strip():
        return ("איזה אימון לרשום, אדוני?" if lang == "he"
                else "What workout should I log, sir?")
    data = _load_training_log()
    workouts = data.setdefault("workouts", [])
    today = datetime.date.today().isoformat()
    wtype = _classify_workout(text)
    workouts.append({"desc": text.strip(), "type": wtype, "date": today})
    data["last_workout_type"] = wtype
    data["last_workout_date"] = today
    wk = _iso_week_tag()
    if data.get("workout_week") != wk:
        data["workout_week"] = wk
        data["weekly_workouts"] = 0
    try:
        data["weekly_workouts"] = int(data.get("weekly_workouts", 0)) + 1
    except Exception:
        data["weekly_workouts"] = 1
    _save_training_log(data)
    n = data["weekly_workouts"]
    if lang == "he":
        return "נרשם, אדוני: %s. זה אימון מספר %d השבוע." % (text.strip(), n)
    return "Logged, sir: %s. That's workout #%d this week." % (text.strip(), n)

def recent_workouts(lang="en"):
    data = _load_training_log()
    workouts = data.get("workouts", [])
    if not workouts:
        return ("עדיין לא תיעדת אימונים, אדוני." if lang == "he"
                else "No workouts logged yet, sir.")
    wk = _iso_week_tag()
    week_count = 0
    if data.get("workout_week") == wk:
        try:
            week_count = int(data.get("weekly_workouts", 0))
        except Exception:
            week_count = 0
    type_he = {"cardio": "קרדיו", "swim": "שחייה", "strength": "כוח", "general": "כללי"}
    last5 = workouts[-5:][::-1]
    lines = []
    for w in last5:
        try:
            d = datetime.date.fromisoformat(w.get("date", ""))
            days = (datetime.date.today() - d).days
            if lang == "he":
                rel = ("היום" if days == 0 else "אתמול" if days == 1
                       else "לפני %d ימים" % days)
            else:
                rel = ("today" if days == 0 else "yesterday" if days == 1
                       else "%d days ago" % days)
        except Exception:
            rel = ""
        desc = w.get("desc", "?")
        t = w.get("type", "")
        if lang == "he":
            tlabel = type_he.get(t, t)
            lines.append("%s [%s] (%s)" % (desc, tlabel, rel) if rel
                         else "%s [%s]" % (desc, tlabel))
        else:
            lines.append("%s [%s] (%s)" % (desc, t, rel) if rel
                         else "%s [%s]" % (desc, t))
    body = "; ".join(lines)
    if lang == "he":
        return "השבוע: %d אימונים, אדוני. אחרונים: %s" % (week_count, body)
    return "This week: %d workouts, sir. Recent: %s" % (week_count, body)

# A bare cardio verb ("ran"/"swam"/"רצתי"...) only counts as a workout when it
# carries workout context (a number, a distance/time unit, or a gym noun) - so
# "I ran the tests" / "רצתי לחנות" are NOT logged as workouts.
_WORKOUT_CTX = re.compile(
    r"\d|\bkm\b|\bk\b|\bmiles?\b|\bmin(?:ute)?s?\b|\bhours?\b|\breps?\b|"
    r"\bsets?\b|\blaps?\b|\bkg\b|\bmarathon\b|\btreadmill\b|\bpool\b|\bgym\b|"
    r"ק\"?מ|מטר|דקות|חזרות|סטים|קילומטר|בריכה|מרתון|הקפות",
    re.IGNORECASE)

def _workout_log_parse(msg):
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג'?א?ר?ו+יס|gארוויס)[\s,:]*", "", text)
    text = text.strip()
    m = re.match(r"(?:log|record|add)\s+(?:a\s+)?workout[:\-\s]+(.+)$", text, re.I)
    if m:
        return m.group(1).strip()
    m = re.match(r"i\s+(?:did|completed|finished)\s+(?:a\s+|my\s+)?workout\b[:\-\s]*(.*)$", text, re.I)
    if m:
        rest = m.group(1).strip()
        return rest if rest else "workout"
    m = re.match(r"i\s+trained\s+(.+)$", text, re.I)
    if m:
        return "trained " + m.group(1).strip()
    m = re.match(r"i\s+worked\s+out\b[:\-\s]*(.*)$", text, re.I)
    if m:
        rest = m.group(1).strip()
        return ("worked out " + rest) if rest else "worked out"
    m = re.match(r"i\s+(ran|swam|lifted|rowed|cycled|biked|sprinted|jogged)\b\s*(.*)$", text, re.I)
    if m and _WORKOUT_CTX.search(m.group(2)):
        return (m.group(1) + " " + m.group(2)).strip()
    m = re.match(r"(ran|swam|jogged|sprinted)\b\s+(.+)$", text, re.I)
    if m and _WORKOUT_CTX.search(m.group(2)):
        return (m.group(1) + " " + m.group(2)).strip()
    m = re.match(r"(?:תרשום|רשום|תעד)\s+(?:לי\s+)?(?:את\s+)?אימון[:\-\s]+(.+)$", text)
    if m:
        return m.group(1).strip()
    m = re.match(r"(?:אימנתי|התאמנתי)\s+(.+)$", text)
    if m:
        return m.group(1).strip()
    m = re.match(r"(?:רצתי|שחיתי)\s+(.+)$", text)
    if m and _WORKOUT_CTX.search(m.group(1)):
        return (text).strip()
    m = re.match(r"עשיתי\s+אימון\b[:\-\s]*(.*)$", text)
    if m:
        rest = m.group(1).strip()
        return ("אימון " + rest) if rest else "אימון"
    return None

def _workout_status_intercept(msg):
    if not msg or not isinstance(msg, str):
        return False
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג'?א?ר?ו+יס|gארוויס)[\s,:]*", "", text)
    text = text.strip().rstrip(".!?,")
    low = text.lower()
    en_triggers = {
        "workout status", "my workouts", "recent workouts",
        "what did i train this week", "what have i trained this week",
        "workouts this week", "training this week", "workout report",
        "how many workouts this week", "my training",
    }
    if low in en_triggers:
        return True
    he_triggers = {
        "מצב אימונים", "האימונים שלי", "מה אימנתי השבוע",
        "כמה אימונים השבוע", "אימונים השבוע", "דוח אימונים",
    }
    if text in he_triggers:
        return True
    return False

_FITNESS_METRICS = {
    "run_2km":   {"unit": "sec",   "default": 480, "lower_better": True,
                  "label_en": "2km run",   "label_he": "ריצת 2 ק\"מ"},
    "run_3km":   {"unit": "sec",   "default": 750, "lower_better": True,
                  "label_en": "3km run",   "label_he": "ריצת 3 ק\"מ"},
    "pullups":   {"unit": "count", "default": 15,  "lower_better": False,
                  "label_en": "pull-ups",  "label_he": "מתח"},
    "pushups":   {"unit": "count", "default": 60,  "lower_better": False,
                  "label_en": "push-ups",  "label_he": "שכיבות סמיכה"},
    "situps":    {"unit": "count", "default": 70,  "lower_better": False,
                  "label_en": "sit-ups",   "label_he": "כפיפות בטן"},
    "swim_400m": {"unit": "sec",   "default": 480, "lower_better": True,
                  "label_en": "400m swim", "label_he": "שחיית 400 מ'"},
}
_FITNESS_ORDER = ["run_2km", "run_3km", "pullups", "pushups", "situps", "swim_400m"]

def _fmt_metric_value(key, val):
    meta = _FITNESS_METRICS.get(key, {})
    if meta.get("unit") == "sec":
        try:
            v = int(round(float(val)))
            return "%d:%02d" % (v // 60, v % 60)
        except Exception:
            return str(val)
    try:
        return str(int(round(float(val))))
    except Exception:
        return str(val)

def _parse_mmss_to_sec(text):
    m = re.search(r"(\d{1,2}):(\d{2})", text or "")
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return None

def _fitness_label(key, lang):
    meta = _FITNESS_METRICS.get(key, {})
    return meta.get("label_he" if lang == "he" else "label_en", key)

def _get_target(data, key):
    std = data.get("standards", {}) or {}
    if key in std:
        return std[key]
    return _FITNESS_METRICS[key]["default"]

def _detect_fitness_metric(text):
    low = (text or "").lower()
    if re.search(r"\b3\s*k(?:m)?\b", low) or "ריצת 3" in low or "3 קמ" in low or "3 ק\"מ" in low:
        return "run_3km"
    if re.search(r"\b2\s*k(?:m)?\b", low) or "ריצת 2" in low or "2 קמ" in low or "2 ק\"מ" in low:
        return "run_2km"
    if "pull" in low or "מתח" in low:
        return "pullups"
    if "push" in low or "שכיבות" in low:
        return "pushups"
    if "situp" in low or "sit-up" in low or "sit up" in low or "בטן" in low or "כפיפות" in low:
        return "situps"
    if "swim" in low or "שחייה" in low or "שחיה" in low or "שחיית" in low:
        return "swim_400m"
    if ("run" in low or "ריצה" in low or "רצתי" in low) and _parse_mmss_to_sec(low) is not None:
        return "run_2km"
    return None

def _fitness_test_parse(msg):
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג'?א?ר?ו+יס|gארוויס)[\s,:]*", "", text)
    text = text.strip()
    m = re.match(r"(?:log|record|add)\s+(?:a\s+|my\s+)?(?:fitness\s+)?(?:test|result)?[:\-\s]*(.+)$", text, re.I)
    if m:
        body = m.group(1).strip()
    else:
        mh = re.match(r"(?:תרשום|רשום|תעד)\s+(?:לי\s+)?(?:את\s+)?(?:מבדק|תוצאה)?[:\-\s]*(.+)$", text)
        if mh:
            body = mh.group(1).strip()
        else:
            return None
    key = _detect_fitness_metric(body)
    if key is None:
        return None
    unit = _FITNESS_METRICS[key]["unit"]
    if unit == "sec":
        sec = _parse_mmss_to_sec(body)
        if sec is None:
            return None
        return (key, sec)
    nums = re.findall(r"\d{1,3}", body)
    nums = [n for n in nums if n not in ("2", "3", "400") or len(nums) == 1]
    if not nums:
        return None
    return (key, int(nums[-1]))

def log_fitness_test(parsed, lang="en"):
    key, value = parsed
    data = _load_training_log()
    tests = data.setdefault("fitness_tests", [])
    tests.append({"metric": key, "value": value,
                  "date": datetime.date.today().isoformat()})
    _save_training_log(data)
    target = _get_target(data, key)
    disp = _fmt_metric_value(key, value)
    tdisp = _fmt_metric_value(key, target)
    label = _fitness_label(key, lang)
    lower = _FITNESS_METRICS[key]["lower_better"]
    met = (value <= target) if lower else (value >= target)
    if lang == "he":
        verdict = "עברת את היעד! 🔥" if met else ("היעד: " + tdisp)
        return "נרשם, אדוני: %s %s. %s" % (label, disp, verdict)
    verdict = "Target beaten! 🔥" if met else ("Target: " + tdisp)
    return "Logged, sir: %s %s. %s" % (label, disp, verdict)

def _set_target_parse(msg):
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = text.strip()
    m = re.match(r"(?:set\s+)?(?:target|goal|standard)[:\-\s]+(.+)$", text, re.I)
    if not m:
        mh = re.match(r"(?:יעד|תקן)[:\-\s]+(.+)$", text)
        if not mh:
            return None
        body = mh.group(1).strip()
    else:
        body = m.group(1).strip()
    key = _detect_fitness_metric(body)
    if key is None:
        return None
    unit = _FITNESS_METRICS[key]["unit"]
    if unit == "sec":
        sec = _parse_mmss_to_sec(body)
        if sec is None:
            return None
        return (key, sec)
    nums = [n for n in re.findall(r"\d{1,3}", body) if n not in ("2", "3", "400")]
    if not nums:
        return None
    return (key, int(nums[-1]))

def set_fitness_target(parsed, lang="en"):
    key, value = parsed
    data = _load_training_log()
    std = data.setdefault("standards", {})
    std[key] = value
    _save_training_log(data)
    label = _fitness_label(key, lang)
    disp = _fmt_metric_value(key, value)
    if lang == "he":
        return "היעד ל%s עודכן ל-%s, אדוני." % (label, disp)
    return "Target for %s set to %s, sir." % (label, disp)

def fitness_progress(lang="en"):
    data = _load_training_log()
    tests = data.get("fitness_tests", [])
    lines = []
    for key in _FITNESS_ORDER:
        meta = _FITNESS_METRICS[key]
        label = _fitness_label(key, lang)
        target = _get_target(data, key)
        tdisp = _fmt_metric_value(key, target)
        mine = [t for t in tests if t.get("metric") == key]
        if not mine:
            if lang == "he":
                lines.append("%s: טרם נבדק (יעד %s)" % (label, tdisp))
            else:
                lines.append("%s: not tested yet (target %s)" % (label, tdisp))
            continue
        latest = mine[-1]
        lval = latest.get("value")
        ldisp = _fmt_metric_value(key, lval)
        lower = meta["lower_better"]
        met = (lval <= target) if lower else (lval >= target)
        deltastr = ""
        if len(mine) > 1:
            pval = mine[-2].get("value")
            if meta["unit"] == "sec":
                diff = pval - lval
                if diff != 0:
                    sgn = "-" if diff > 0 else "+"
                    deltastr = (" (%s%ss מהפעם הקודמת)" if lang == "he"
                                else " (%s%ss vs last)") % (sgn, abs(int(diff)))
            else:
                diff = lval - pval
                if diff != 0:
                    sgn = "+" if diff > 0 else "-"
                    deltastr = (" (%s%d מהפעם הקודמת)" if lang == "he"
                                else " (%s%d vs last)") % (sgn, abs(int(diff)))
        if lang == "he":
            mark = "✅" if met else "○"
            lines.append("%s %s: %s / יעד %s%s" % (mark, label, ldisp, tdisp, deltastr))
        else:
            mark = "✅" if met else "○"
            lines.append("%s %s: %s / target %s%s" % (mark, label, ldisp, tdisp, deltastr))
    if lang == "he":
        return "מצב כושר, אדוני:\n" + "\n".join(lines)
    return "Fitness progress, sir:\n" + "\n".join(lines)

def _fitness_progress_intercept(msg):
    if not msg or not isinstance(msg, str):
        return False
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג'?א?ר?ו+יס|gארוויס)[\s,:]*", "", text)
    text = text.strip().rstrip(".!?,")
    low = text.lower()
    en = {"progress", "fitness progress", "where do i stand",
          "how am i doing", "fitness status", "my progress",
          "am i ready", "standards"}
    if low in en:
        return True
    he = {"מצב כושר", "איפה אני עומד", "התקדמות", "כושר",
          "ההתקדמות שלי", "אני מוכן"}
    if text in he:
        return True
    return False

def _this_iso_week(d=None):
    d = d or datetime.date.today()
    return d.isocalendar()[:2]

def weekly_summary(lang="en"):
    data = _load_training_log()
    today = datetime.date.today()
    wk = _this_iso_week(today)
    parts = []
    workouts = data.get("workouts", [])
    wk_workouts = []
    for w in workouts:
        try:
            d = datetime.date.fromisoformat(w.get("date", ""))
            if d.isocalendar()[:2] == wk:
                wk_workouts.append(w)
        except Exception:
            pass
    type_he = {"cardio": "קרדיו", "swim": "שחייה", "strength": "כוח", "general": "כללי"}
    counts = {}
    for w in wk_workouts:
        t = w.get("type", "general")
        counts[t] = counts.get(t, 0) + 1
    if wk_workouts:
        if lang == "he":
            bd = ", ".join("%d %s" % (n, type_he.get(t, t)) for t, n in sorted(counts.items()))
            parts.append("אימונים: %d (%s)" % (len(wk_workouts), bd))
        else:
            bd = ", ".join("%d %s" % (n, t) for t, n in sorted(counts.items()))
            parts.append("Workouts: %d (%s)" % (len(wk_workouts), bd))
    else:
        parts.append("אימונים: 0 השבוע" if lang == "he" else "Workouts: 0 this week")
    w_kg = data.get("last_weight_kg")
    if w_kg is not None:
        try:
            w_min = float(data.get("weight_target_min_kg", 68))
        except Exception:
            w_min = 68.0
        try:
            w_val = float(w_kg)
            if w_val < w_min:
                tag = ("מתחת לקו האדום!" if lang == "he" else "BELOW red-line!")
            elif w_val <= w_min + 1:
                tag = ("קרוב לקו האדום" if lang == "he" else "near red-line")
            else:
                tag = ("טוב" if lang == "he" else "ok")
            if lang == "he":
                parts.append("משקל: %.1f ק\"ג (קו אדום %.0f - %s)" % (w_val, w_min, tag))
            else:
                parts.append("Weight: %.1f kg (red-line %.0f - %s)" % (w_val, w_min, tag))
        except Exception:
            pass
    if data.get("nutrition_date") == today.isoformat():
        cal = data.get("today_calories", 0)
        prot = data.get("today_protein_g", 0)
        tcal = data.get("target_calories", 3000)
        tprot = data.get("target_protein_g", 130)
        if lang == "he":
            parts.append("תזונה היום: %s/%s קלוריות, %s/%sג חלבון" % (cal, tcal, prot, tprot))
        else:
            parts.append("Nutrition today: %s/%s kcal, %s/%s g protein" % (cal, tcal, prot, tprot))
    injuries = data.get("injuries", [])
    active = [i for i in injuries if i.get("status") == "active"]
    if active:
        names = "; ".join(i.get("desc", "?") for i in active)
        if lang == "he":
            parts.append("פציעות פעילות: %d (%s)" % (len(active), names))
        else:
            parts.append("Active injuries: %d (%s)" % (len(active), names))
    else:
        parts.append("פציעות: אין" if lang == "he" else "Injuries: none")
    if data.get("fitness_tests"):
        parts.append("אמור 'מצב כושר' למדדים" if lang == "he"
                     else "Say 'progress' for benchmark detail")
    header = "סיכום שבועי, אדוני:" if lang == "he" else "Weekly summary, sir:"
    return header + "\n" + "\n".join("- " + p for p in parts)

def _weekly_summary_intercept(msg):
    if not msg or not isinstance(msg, str):
        return False
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג'?א?ר?ו+יס|gארוויס)[\s,:]*", "", text)
    text = text.strip().rstrip(".!?,")
    low = text.lower()
    en = {"weekly summary", "week summary", "my week", "week recap",
          "weekly recap", "summary of my week", "this week summary"}
    if low in en:
        return True
    he = {"סיכום שבועי", "סיכום השבוע", "מה עשיתי השבוע"}
    if text in he:
        return True
    return False

def _weight_log_parse(msg):
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג'?א?ר?ו+יס|gארוויס)[\s,:]*", "", text)
    text = text.strip()
    num = r"(\d{2,3}(?:\.\d{1,2})?)"
    pats = [
        r"(?:log|record|add)\s+(?:my\s+)?weight[:\-\s]+" + num,
        r"i\s+weigh(?:ed)?\s+" + num,
        r"(?:my\s+)?weight\s+(?:is\s+)?" + num + r"\s*(?:kg|kilo|kilos|kgs)?\b",
        r"(?:תרשום|רשום|תעד)\s+(?:לי\s+)?(?:את\s+)?משקל[:\-\s]+" + num,
        r"שקלתי\s+" + num,
        r"(?:ה?משקל\s+שלי|המשקל)\s+" + num,
    ]
    for p in pats:
        m = re.search(p, text, re.I)
        if m:
            try:
                v = float(m.group(1))
            except Exception:
                continue
            if 30.0 <= v <= 200.0:
                return v
    return None

def log_weight(val, lang="en"):
    data = _load_training_log()
    today = datetime.date.today().isoformat()
    weights = data.setdefault("weights", [])
    weights.append({"kg": val, "date": today})
    data["last_weight_kg"] = val
    data["last_weight_date"] = today
    _save_training_log(data)
    try:
        wmin = float(data.get("weight_target_min_kg", 68))
    except Exception:
        wmin = 68.0
    if val < wmin:
        tag = ("מתחת לקו האדום של %g ק\"ג - תאכל, אדוני." % wmin if lang == "he"
               else "below the %g kg red line - eat up, sir." % wmin)
    elif val <= wmin + 1:
        tag = ("קרוב לקו האדום של %g ק\"ג." % wmin if lang == "he"
               else "close to the %g kg red line." % wmin)
    else:
        tag = ("מעל הקו האדום. טוב." if lang == "he"
               else "above the red line. Good.")
    if lang == "he":
        return "נרשם, אדוני: %g ק\"ג - %s" % (val, tag)
    return "Logged, sir: %g kg - %s" % (val, tag)

def weight_check(lang="en"):
    data = _load_training_log()
    w = data.get("last_weight_kg")
    if w is None:
        return ("עדיין לא תיעדת משקל, אדוני. אמור 'תרשום משקל 70'." if lang == "he"
                else "No weight logged yet, sir. Say 'log weight 70'.")
    try:
        w = float(w)
        wmin = float(data.get("weight_target_min_kg", 68))
    except Exception:
        return ("לא הצלחתי לקרוא את המשקל, אדוני." if lang == "he"
                else "Couldn't read the weight, sir.")
    rel = ""
    wd = data.get("last_weight_date", "")
    try:
        d0 = datetime.date.fromisoformat(wd)
        days = (datetime.date.today() - d0).days
        if lang == "he":
            rel = ("היום" if days == 0 else "אתמול" if days == 1 else "לפני %d ימים" % days)
        else:
            rel = ("today" if days == 0 else "yesterday" if days == 1 else "%d days ago" % days)
    except Exception:
        rel = ""
    trend = ""
    weights = data.get("weights", [])
    if len(weights) > 1:
        try:
            prev = float(weights[-2].get("kg"))
            diff = w - prev
            if abs(diff) >= 0.05:
                if lang == "he":
                    verb = "עלית" if diff > 0 else "ירדת"
                    trend = " %s %+.1f ק\"ג מהפעם הקודמת" % (verb, diff)
                else:
                    verb = "up" if diff > 0 else "down"
                    trend = " %s %+.1f kg vs last weigh-in" % (verb, diff)
        except Exception:
            pass
    if w < wmin:
        verdict = ("מתחת לקו האדום!" if lang == "he" else "BELOW the red line!")
    elif w <= wmin + 1:
        verdict = ("קרוב לקו האדום." if lang == "he" else "near the red line.")
    else:
        verdict = ("מעל הקו האדום. טוב." if lang == "he" else "above the red line. Good.")
    relpart = (" (%s)" % rel) if rel else ""
    if lang == "he":
        return "משקל אחרון: %g ק\"ג%s. קו אדום %g - %s%s" % (w, relpart, wmin, verdict, trend)
    return "Latest weight: %g kg%s. Red line %g - %s%s" % (w, relpart, wmin, verdict, trend)

def _weight_check_intercept(msg):
    if not msg or not isinstance(msg, str):
        return False
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג'?א?ר?ו+יס|gארוויס)[\s,:]*", "", text)
    text = text.strip().rstrip(".!?,")
    low = text.lower()
    en = {"weight check", "my weight", "what is my weight",
          "what's my weight", "weight status", "am i above 68",
          "am i above the red line", "how much do i weigh", "current weight"}
    if low in en:
        return True
    he = {"בדיקת משקל", "מה המשקל", "המשקל שלי", "כמה אני שוקל",
          "מה המשקל שלי", "משקל", "כמה אני שוקל עכשיו"}
    if text in he:
        return True
    return False

import socket as _v440_socket
if not getattr(_v440_socket, "_v440_ipv4_patched", False):
    _v440_orig_getaddrinfo = _v440_socket.getaddrinfo
    def _v440_ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        # Prefer IPv4 (local IPv6 routing to Google is broken here), but only
        # coerce AF_UNSPEC requests, honour an explicit family, and ALWAYS fall
        # back to a normal resolve if the IPv4-only lookup fails - so genuinely
        # IPv6-only hosts / explicit AF_INET6 callers still resolve instead of
        # raising (the old version forced AF_INET unconditionally and lost the
        # graceful fallback the v4.6 layer provided).
        fam = _v440_socket.AF_INET if family == 0 else family
        try:
            return _v440_orig_getaddrinfo(host, port, fam, type, proto, flags)
        except _v440_socket.gaierror:
            return _v440_orig_getaddrinfo(host, port, family, type, proto, flags)
    _v440_socket.getaddrinfo = _v440_ipv4_only_getaddrinfo
    _v440_socket._v440_ipv4_patched = True

def _obsidian_search_parse(msg):
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:\-]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג[׳'`]?א?ר?ו+יס)[\s,:\-]*", "", text)
    text = text.strip().rstrip("?!.").strip()
    low = text.lower()
    listall_en = [
        r"^do i have (?:any )?notes$",
        r"^show (?:me )?(?:my )?notes$",
        r"^list (?:my )?notes$",
        r"^what notes do i have$",
        r"^what are my notes$",
        r"^my notes$",
        r"^all (?:my )?notes$",
    ]
    for p in listall_en:
        if re.search(p, low):
            return ""
    listall_he = [
        r"^מה הפתקים שלי$",
        r"^אילו פתקים יש לי$",
        r"^יש לי פתקים$",
        r"^הצג (?:לי )?(?:את )?הפתקים(?: שלי)?$",
        r"^הראה (?:לי )?(?:את )?הפתקים(?: שלי)?$",
        r"^רשימת פתקים$",
        r"^כל הפתקים(?: שלי)?$",
        r"^איזה פתקים יש לי$",
    ]
    for p in listall_he:
        if re.search(p, text):
            return ""
    en_pats = [
        r"what did i (?:note|write|jot|record) (?:down )?about (.+)$",
        r"what do(?:es)? my notes? say about (.+)$",
        r"search (?:my )?(?:notes?|vault|memory) (?:for |about )?(.+)$",
        r"find (?:in )?(?:my )?notes? (?:about |for )?(.+)$",
        r"do i have (?:any )?notes? (?:on|about|regarding) (.+)$",
        r"any notes (?:on|about|regarding) (.+)$",
        r"show (?:me )?(?:my )?notes (?:on|about|regarding) (.+)$",
        r"list (?:my )?notes (?:on|about|regarding) (.+)$",
        r"look up (.+?) in my (?:notes?|vault)$",
    ]
    for p in en_pats:
        m = re.search(p, low)
        if m:
            return m.group(1).strip(" .?!,'\"")
    he_pats = [
        r"מה רשמתי (?:לעצמי )?על (.+)$",
        r"מה כתבתי (?:לעצמי )?על (.+)$",
        r"מה רשמתי בנושא (.+)$",
        r"מה כתבתי בנושא (.+)$",
        r"חפש (?:לי )?(?:בפתקים|בכספת|בזיכרון) (?:על |בנושא )?(.+)$",
        r"תחפש (?:לי )?(?:בפתקים|בכספת|בזיכרון) (?:על |בנושא )?(.+)$",
        r"מה יש לי (?:רשום )?(?:על |בנושא )(.+)$",
        r"מה הפתקים (?:שלי )?אומרים על (.+)$",
        r"יש לי פתקים (?:על |בנושא |לגבי )(.+)$",
        r"יש לי משהו (?:רשום )?(?:על |בנושא |לגבי )(.+)$",
        r"הראה (?:לי )?(?:את )?הפתקים (?:שלי )?(?:על |בנושא |לגבי )(.+)$",
        r"הצג (?:לי )?(?:את )?הפתקים (?:שלי )?(?:על |בנושא |לגבי )(.+)$",
    ]
    for p in he_pats:
        m = re.search(p, text)
        if m:
            return m.group(1).strip(" .?!,'\"")
    return None

def _obsidian_or_split(q):
    parts = re.split(r"\s+(?:or|או)\s+", q)
    parts = [p.strip() for p in parts if p.strip()]
    return parts or [q]

def search_obsidian(query, lang="en"):
    if not query or not query.strip():
        return list_all_notes(lang)
    q = query.strip().lower()
    terms = _obsidian_or_split(q)
    vault = VAULT_DIR
    try:
        if not vault.exists():
            return ("אין עדיין כספת אובסידיאן, אדוני." if lang == "he"
                    else "There's no Obsidian vault yet, sir.")
    except Exception:
        return ("לא הצלחתי לגשת לכספת, אדוני." if lang == "he"
                else "I couldn't reach the vault, sir.")
    matches = []
    total = 0
    CAP = 4000
    try:
        for f in sorted(vault.rglob("*.md")):
            try:
                lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
            except Exception:
                continue
            hits = [i for i, ln in enumerate(lines) if any(tt in ln.lower() for tt in terms)]
            if not hits:
                continue
            keep = set()
            for i in hits:
                for j in range(max(0, i - 2), min(len(lines), i + 3)):
                    keep.add(j)
            ctx = "\n".join(lines[j] for j in sorted(keep) if lines[j].strip())
            try:
                label = f.relative_to(vault)
            except Exception:
                label = f.name
            snippet = "[%s]\n%s" % (label, ctx)
            matches.append(snippet)
            total += len(snippet)
            if total >= CAP:
                break
    except Exception:
        return ("שגיאה בחיפוש בפתקים, אדוני." if lang == "he"
                else "Error searching your notes, sir.")
    if not matches:
        return (("לא מצאתי כלום על '%s' בפתקים שלך, אדוני." % query) if lang == "he"
                else ("I couldn't find anything about '%s' in your notes, sir." % query))
    facts = ("\n\n".join(matches))[:CAP]
    if not ANTHROPIC_API_KEY:
        head = ("מצאתי את זה בפתקים, אדוני:\n" if lang == "he"
                else "Found this in your notes, sir:\n")
        return clean_text(head + facts)
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        sys_p = (
            "You are Achilles, a calm British-butler AI. The user searched their "
            "personal Obsidian notes. Below are the matching excerpts (each tagged "
            "with its [filename]). Answer what THEIR NOTES say about '"
            + query + "' in 2 to 4 short sentences, in "
            + ("Hebrew" if lang == "he" else "English")
            + ". Address them as " + ("אדוני" if lang == "he" else "sir")
            + ". Base the answer ONLY on the excerpts. Plain text, no markdown, no URLs.")
        r = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=400,
            system=sys_p, messages=[{"role": "user", "content": facts}])
        parts = [b.text for b in r.content if getattr(b, "type", None) == "text"]
        reply = " ".join(p.strip() for p in parts if p.strip()).strip()
        return clean_text(reply) or clean_text(facts)
    except Exception:
        return clean_text(facts)

def list_all_notes(lang="en"):
    vault = VAULT_DIR
    try:
        if not vault.exists():
            return ("אין עדיין כספת אובסידיאן, אדוני." if lang == "he"
                    else "There's no Obsidian vault yet, sir.")
    except Exception:
        return ("לא הצלחתי לגשת לכספת, אדוני." if lang == "he"
                else "I couldn't reach the vault, sir.")
    try:
        files = sorted(vault.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        files = []
    if not files:
        return ("אין לך פתקים שמורים, אדוני." if lang == "he"
                else "You have no saved notes, sir.")
    LIMIT = 15
    shown = files[:LIMIT]
    lines = []
    for f in shown:
        try:
            label = f.relative_to(vault).as_posix()
        except Exception:
            label = f.name
        hint = ""
        try:
            for ln in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                s = ln.strip().lstrip("#").strip()
                if s:
                    hint = s[:60]
                    break
        except Exception:
            pass
        if hint:
            lines.append("%s — %s" % (label, hint))
        else:
            lines.append(str(label))
    extra = len(files) - len(shown)
    if lang == "he":
        head = "יש לך %d פתקים, אדוני. הנה האחרונים:\n" % len(files)
        tail = ("\nועוד %d." % extra) if extra > 0 else ""
    else:
        head = "You have %d notes, sir. The most recent:\n" % len(files)
        tail = ("\nAnd %d more." % extra) if extra > 0 else ""
    return clean_text(head + "\n".join(lines) + tail)

NEWS_INTERESTS = "artificial intelligence and technology, Israel, and major world news"

def _news_briefing_section(lang="en"):
    if not ANTHROPIC_API_KEY:
        return ""
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        interests = globals().get("NEWS_INTERESTS", "technology, Israel, world news")
        sys_p = (
            "You are a news desk. Use web_search to find 2 or 3 of the most "
            "important and RECENT headlines (prefer the last day or two) relevant "
            "to these interests: " + interests + ". Then output ONLY a compact "
            "plain-text list of those 2-3 headlines, one per line, each a short "
            "factual phrase. No URLs, no numbering, no commentary, no markdown. "
            "Write the headlines in " + ("Hebrew" if lang == "he" else "English") + ".")
        tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 2}]
        msgs = [{"role": "user", "content": "Today's headlines for my briefing, please."}]
        r = None
        for _ in range(4):
            r = client.messages.create(
                model="claude-sonnet-4-6", max_tokens=500,
                system=sys_p, messages=msgs, tools=tools)
            msgs.append({"role": "assistant", "content": r.content})
            if getattr(r, "stop_reason", None) == "tool_use":
                continue
            break
        parts = [b.text for b in r.content if getattr(b, "type", None) == "text"]
        news = "\n".join(p.strip() for p in parts if p.strip()).strip()
        news = re.sub(r"https?://\S+", "", news)
        return clean_text(news).strip()
    except Exception as e:
        try:
            print("[diag] news section skipped:", repr(e))
        except Exception:
            pass
        return ""

def think(user_message, memory, lang=""):
    if not ANTHROPIC_API_KEY:
        return "[Error: Missing API Key in .env]"
    with _quiz_lock:
        _quiz_active = _quiz_state["active"]
    if _quiz_active:
        _fb = evaluate_quiz_answer(
            user_message,
            lang="he" if lang == "he" or is_hebrew(user_message) else "en")
        if _fb is not None:
            return _fb
    parsed = _learning_intercept(user_message)
    if parsed is not None:
        topic, depth = parsed
        if topic == "__STATUS__":
            return learning_status()
        if topic.startswith("__RESUME__:"):
            return resume_learning(topic[len("__RESUME__:"):])
        if depth == "deep":
            return deep_learn_domain(topic)
        else:
            return learn_topic(topic, "")
    if _whats_new_intercept(user_message):
        return whats_new("he" if lang == "he" or is_hebrew(user_message) else "en")
    if _system_health_intercept(user_message):
        return system_health("he" if lang == "he" or is_hebrew(user_message) else "en")
    if _learned_this_week_intercept(user_message):
        return learned_this_week("he" if lang == "he" or is_hebrew(user_message) else "en")
    if _undo_intercept(user_message):
        return undo_last()
    if _budget_intercept(user_message):
        return budget_status("he" if lang == "he" or is_hebrew(user_message) else "en")
    if _backup_intercept(user_message):
        return backup_vault()
    _dec = _decision_log_parse(user_message)
    if _dec is not None:
        return log_decision(_dec)
    if _decision_review_intercept(user_message):
        return recent_decisions(lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    _nut = _nutrition_log_parse(user_message)
    if _nut is not None:
        return log_calories(_nut[1]) if _nut[0] == "calories" else log_protein(_nut[1])
    if _nutrition_status_intercept(user_message):
        return nutrition_status(lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    _quiz_topic = _quiz_start_parse(user_message)
    if _quiz_topic is not None:
        return start_quiz(_quiz_topic, lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    _inj = _injury_log_parse(user_message)
    if _inj is not None:
        return log_injury(_inj, lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    _rec = _injury_recovered_parse(user_message)
    if _rec is not None:
        return mark_recovered(_rec, lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    if _injury_status_intercept(user_message):
        return injury_status(lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    _wo = _workout_log_parse(user_message)
    if _wo is not None:
        return log_workout(_wo, lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    if _workout_status_intercept(user_message):
        return recent_workouts(lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    _ft = _fitness_test_parse(user_message)
    if _ft is not None:
        return log_fitness_test(_ft, lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    _tg = _set_target_parse(user_message)
    if _tg is not None:
        return set_fitness_target(_tg, lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    if _fitness_progress_intercept(user_message):
        return fitness_progress(lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    if _weekly_summary_intercept(user_message):
        return weekly_summary(lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    _wt = _weight_log_parse(user_message)
    if _wt is not None:
        return log_weight(_wt, lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    if _weight_check_intercept(user_message):
        return weight_check(lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    _obs_q = _obsidian_search_parse(user_message)
    if _obs_q is not None:
        return search_obsidian(_obs_q, lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    _low = user_message.lower()
    if re.search(r"(פתח|תפתח|open|show|launch|bring up|תעלה|תציג)[^.!?]{0,24}(black\s?hole|חור שחור|achilles|אכילס)", _low) \
       or re.search(r"(black\s?hole|חור שחור)[^.!?]{0,12}(screen|window|מסך|חלון)", _low):
        return open_achilles("core")
    if re.search(r"(פתח|תפתח|open|show|launch|תראה|תציג|תעלה)[^.!?]{0,24}(solar\s?system|מערכת השמש|הכוכבים|the planets)", _low):
        return open_achilles("solar")
    _t = re.search(r"(?:תוסיף משימה|תוסיף לרשימה|add (?:a )?task)\s+(.+)", user_message, re.IGNORECASE)
    if _t is not None:
        return todo_add_voice(_t.group(1), "he" if lang == "he" or is_hebrew(user_message) else "en")
    if re.search(r"(פתח|תפתח|open|show|תראה|תציג|תעלה)[^.!?]{0,24}(to\s?do|todo|task list|המשימות|רשימת משימות|רשימת המשימות)", _low):
        return open_achilles("todo")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    if lang == "he":
        _lang_note = "\nIMPORTANT: The user is speaking HEBREW. Reply ONLY in Hebrew. Never reply in any other language."
    else:
        _lang_note = "\nIMPORTANT: Reply ONLY in English. Never reply in German, French, or any language other than English, even if the user's words look like another language."
    _time_note = "\nCurrent local time (Israel): " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
    sys_prompt = [
        {"type": "text", "text": JARVIS_SYSTEM_PROMPT,
         "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": _lang_note + _time_note},
    ]
    sys_prompt_plain = JARVIS_SYSTEM_PROMPT + _lang_note + _time_note
    globals()["_last_timer_lang"] = "he" if lang == "he" else "en"
    tools = [
        {"type": "web_search_20250305", "name": "web_search", "max_uses": 3},
    ] + LOCAL_TOOLS
    # Hold the lock for the whole turn so concurrent callers (voice / Telegram /
    # the /ask HTTP thread) can never interleave appends into conversation_history.
    with _think_lock:
        _normalize_history()
        if not conversation_history:
            msg = f"[Memory from past conversations:]\n{memory}\n\n[Current message:]\n{user_message}"
        else:
            msg = user_message
        conversation_history.append({"role": "user", "content": msg})
        try:
            for _ in range(5):
                r = client.messages.create(
                    model="claude-sonnet-4-6", max_tokens=1024,
                    system=sys_prompt,
                    messages=conversation_history,
                    tools=tools,
                )
                conversation_history.append({"role": "assistant", "content": r.content})
                if r.stop_reason == "tool_use":
                    tool_results = []
                    for block in r.content:
                        if getattr(block, "type", None) == "tool_use" and block.name in (
                                "open_app", "save_note", "calendar_read", "calendar_add",
                                "calendar_delete", "calendar_update",
                                "gmail_read", "gmail_spam_review", "gmail_move_spam",
                                "find_places", "get_directions", "set_timer",
                                "spotify_play", "spotify_pause", "spotify_next",
                                "spotify_previous", "spotify_volume", "spotify_now_playing",
                                "learn_topic", "deep_learn_domain", "resume_learning",
                                "learning_status", "open_search_panel", "open_worldview",
                                "open_achilles", "open_roadmap"):
                            out = run_local_tool(block.name, block.input or {})
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": out,
                            })
                    if tool_results:
                        conversation_history.append({"role": "user", "content": tool_results})
                        continue
                    # tool_use with no matching tool_result would poison the next
                    # call; drop the orphaned assistant turn before bailing out.
                    if (conversation_history
                            and conversation_history[-1].get("role") == "assistant"):
                        conversation_history.pop()
                    break
                parts = [b.text for b in r.content if getattr(b, "type", None) == "text"]
                reply = " ".join(p.strip() for p in parts if p.strip()).strip()
                if not reply:
                    reply = "Done, sir."
                return clean_text(reply)
            return "I got a bit stuck on that, sir. Could you rephrase?"
        except Exception as e:
            try:
                _normalize_history()
                r = client.messages.create(
                    model="claude-sonnet-4-6", max_tokens=1024,
                    system=sys_prompt_plain, messages=conversation_history)
                reply = r.content[0].text
                conversation_history.append({"role": "assistant", "content": reply})
                return clean_text(reply)
            except Exception as e2:
                import traceback
                print("[diag] Brain error full traceback:", flush=True)
                traceback.print_exc()
                return f"[Error connecting to Brain: {e2}]"

_WMO_WEATHER = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy", 51: "light drizzle", 53: "drizzle",
    55: "heavy drizzle", 56: "freezing drizzle", 57: "freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain",
    67: "freezing rain", 71: "light snow", 73: "snow", 75: "heavy snow",
    77: "snow grains", 80: "rain showers", 81: "rain showers",
    82: "violent rain showers", 85: "snow showers", 86: "snow showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail",
}

def get_weather(when="today"):
    lat, lon = 32.1772, 34.9947
    url = ("https://api.open-meteo.com/v1/forecast"
           "?latitude=%s&longitude=%s"
           "&current=temperature_2m,weather_code"
           "&daily=temperature_2m_max,temperature_2m_min,weather_code"
           "&timezone=auto" % (lat, lon))
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            d = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return "weather unavailable (%s)" % e
    daily = d.get("daily", {})
    idx = 1 if when == "tomorrow" else 0
    try:
        hi = round(daily["temperature_2m_max"][idx])
        lo = round(daily["temperature_2m_min"][idx])
        desc = _WMO_WEATHER.get(daily["weather_code"][idx], "")
        if when == "tomorrow":
            return "%s, high %dC, low %dC" % (desc, hi, lo)
        cur = d.get("current", {}).get("temperature_2m")
        cur_s = ("currently %dC, " % round(cur)) if cur is not None else ""
        return "%s%s, high %dC, low %dC" % (cur_s, desc, hi, lo)
    except Exception:
        return "weather unavailable"

def _briefing_part_from_clock(now):
    h = now.hour
    if 5 <= h < 12:
        return "morning"
    if 12 <= h < 18:
        return "afternoon"
    return "evening"

_BRIEFING_MORNING = ["good morning", "morning jarvis", "בוקר טוב", "boker tov"]
_BRIEFING_AFTERNOON = ["good afternoon", "צהריים טובים", "tzohoraim tovim"]
_BRIEFING_EVENING = ["good evening", "ערב טוב", "erev tov"]

def detect_briefing(text):
    if not text:
        return None
    t = text.lower().strip()
    for ch in ",.!?-:;\"'":
        t = t.replace(ch, " ")
    t = " ".join(t.split())
    if len(t.split()) > 4:
        return None
    if any(w in t for w in _BRIEFING_EVENING):
        return "evening"
    if any(w in t for w in _BRIEFING_AFTERNOON):
        return "afternoon"
    if any(w in t for w in _BRIEFING_MORNING):
        return "morning"
    return None

def _training_briefing_section():
    try:
        p = Path(__file__).resolve().parent / "training_log.json"
        if not p.exists():
            return ""
        data = json.loads(p.read_text(encoding="utf-8"))
        lines = []
        w = data.get("last_weight_kg")
        wd = data.get("last_weight_date")
        tgt = data.get("weight_target_min_kg", 68)
        if w is not None:
            line = "Last weight: %g kg" % float(w)
            if wd:
                try:
                    d0 = datetime.date.fromisoformat(wd)
                    days = (datetime.date.today() - d0).days
                    if days == 0:
                        line += " (today)"
                    elif days == 1:
                        line += " (yesterday)"
                    else:
                        line += " (%d days ago)" % days
                except Exception:
                    pass
            try:
                gap = float(w) - float(tgt)
                if gap >= 0:
                    line += "; %+.1f kg above %g kg target" % (gap, tgt)
                else:
                    line += "; %+.1f kg BELOW %g kg target - red line crossed" % (gap, tgt)
            except Exception:
                pass
            lines.append(line)
        wt = data.get("last_workout_type")
        wtd = data.get("last_workout_date")
        if wt and wtd:
            try:
                d0 = datetime.date.fromisoformat(wtd)
                days = (datetime.date.today() - d0).days
                if days == 0:
                    when = "today"
                elif days == 1:
                    when = "yesterday"
                else:
                    when = "%d days ago" % days
                lines.append("Last workout: %s, %s" % (wt, when))
            except Exception:
                lines.append("Last workout: %s on %s" % (wt, wtd))
        elif wt:
            lines.append("Last workout: %s" % wt)
        wc = data.get("weekly_workouts")
        if wc is not None:
            lines.append("Workouts this week: %s" % wc)
        return "\n".join(lines)
    except Exception:
        return ""

def daily_briefing(part="auto", lang="en"):
    if not ANTHROPIC_API_KEY:
        return "[Error: Missing API Key in .env]"
    now = datetime.datetime.now()
    if part == "auto":
        part = _briefing_part_from_clock(now)
    if part == "evening":
        focus, day, greet = "tomorrow", now + datetime.timedelta(days=1), "Good evening"
    elif part == "afternoon":
        focus, day, greet = "today", now, "Good afternoon"
    else:
        focus, day, greet = "today", now, "Good morning"
    weather = get_weather("tomorrow" if focus == "tomorrow" else "today")
    local_tz = datetime.datetime.now().astimezone().tzinfo
    if focus == "tomorrow":
        tmin = day.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        tmin = now
    tmax = day.replace(hour=23, minute=59, second=59, microsecond=0)
    try:
        cal = calendar_read(tmin.replace(tzinfo=local_tz).isoformat(),
                            tmax.replace(tzinfo=local_tz).isoformat())
    except Exception as e:
        cal = "Calendar unavailable: %s" % e
    try:
        mail = gmail_read(max_results=8)
    except Exception as e:
        mail = "Email unavailable: %s" % e
    training = _training_briefing_section()
    news = _news_briefing_section(lang)
    facts = (
        "GREETING: %s\n"
        "DATE (%s): %s\n"
        "WEATHER (%s, Alfei Menashe): %s\n"
        "%s"
        "%s"
        "CALENDAR (%s):\n%s\n\n"
        "EMAIL:\n%s\n"
        % (greet, focus, day.strftime("%A, %d %B %Y"),
           focus, weather,
           ("TRAINING:\n" + training + "\n\n") if training else "",
           ("NEWS:\n" + news + "\n\n") if news else "",
           focus, cal, mail))
    sys_p = (
        "You are Achilles, a calm British-butler AI assistant giving your creator "
        "(address him as \"sir\" in English or \"אדוני\" in Hebrew) a short spoken "
        "%s briefing. Use the data below. Speak warmly in %s, in 2 to 5 short "
        "sentences. Open with the greeting, then the weather, the key calendar "
        "events for the %s, anything notable in the email, and if a TRAINING "
        "section is present, briefly note the training status - especially if "
        "below the 68 kg minimum or no training in several days. If a NEWS section "
        "is present, briefly mention one or two headlines. If any data is not "
        "connected/unavailable/empty, skip that part silently. Say dates "
        "naturally. Plain text only: no markdown, no bullets, no URLs."
        % (part, "Hebrew" if lang == "he" else "English", focus))
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        r = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=400,
            system=sys_p, messages=[{"role": "user", "content": facts}])
        parts = [b.text for b in r.content if getattr(b, "type", None) == "text"]
        reply = " ".join(p.strip() for p in parts if p.strip()).strip()
        return clean_text(reply) or (greet + ", sir.")
    except Exception as e:
        import traceback
        print("[diag] Briefing error full traceback:", flush=True)
        traceback.print_exc()
        return clean_text("%s, sir. The weather is %s." % (greet, weather))

_active_timers = []
_last_timer_lang = "en"

def _timer_fire(label, lang):
    if lang == "he":
        msg = ("אדוני, הטיימר ל%s הסתיים." % label) if label else "אדוני, הטיימר הסתיים."
    else:
        msg = ("Sir, your %s timer is up." % label) if label else "Sir, your timer is up."
    try:
        if APP is not None:
            APP.ui(lambda: APP._push("JARVIS", msg))
    except Exception:
        pass
    try:
        beep()
    except Exception:
        pass
    try:
        speak(msg)
    except Exception:
        pass

def set_timer(minutes, label=None):
    lang = globals().get("_last_timer_lang", "en")
    try:
        mins = float(minutes)
    except Exception:
        return "I need a number of minutes for the timer, sir."
    if mins <= 0:
        return "The timer needs to be longer than zero, sir."
    secs = mins * 60.0
    # Self-removing wrapper so fired timers don't leak in _active_timers forever
    # (only undo used to prune them; normally-elapsed timers stayed referenced).
    def _fire(_label=label, _lang=lang):
        try:
            _timer_fire(_label, _lang)
        finally:
            try:
                _active_timers.remove(t)
            except ValueError:
                pass
    t = threading.Timer(secs, _fire)
    t.daemon = True
    t.start()
    _active_timers.append(t)
    _record_action("set_timer", {"timer": t, "label": label})
    if mins >= 1:
        dur = "1 minute" if mins == 1 else ("%g minutes" % mins)
    else:
        dur = "%d seconds" % int(round(secs))
    if label:
        return "Timer set for %s (%s), sir." % (dur, label)
    return "Timer set for %s, sir." % dur

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"
SPOTIFY_SCOPES = ("user-read-playback-state user-modify-playback-state "
                  "user-read-currently-playing")
_SPOTIFY_TOKEN_FILE = Path("spotify_token.json")

def _spotify_oauth_flow():
    import http.server, urllib.parse, urllib.request, webbrowser, threading, base64
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        print("Spotify: SPOTIFY_CLIENT_ID/SECRET missing from .env")
        return None
    code_holder = {}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(q)
            if "code" in params:
                code_holder["code"] = params["code"][0]
                body = ("<html><body style='font-family:sans-serif;"
                        "background:#000;color:#fff;text-align:center;"
                        "padding-top:80px'><h1>JARVIS Spotify connected.</h1>"
                        "<p>You can close this tab.</p></body></html>").encode()
            else:
                err = params.get("error", ["unknown"])[0]
                code_holder["error"] = err
                body = (("<html><body><h1>Auth failed: %s</h1></body></html>") % err).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a):
            pass

    try:
        server = http.server.HTTPServer(("127.0.0.1", 8888), _Handler)
    except OSError as e:
        print("Spotify: port 8888 busy:", e)
        return None
    t = threading.Thread(target=server.handle_request, daemon=True)
    t.start()
    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "response_type": "code",
        "client_id": SPOTIFY_CLIENT_ID,
        "scope": SPOTIFY_SCOPES,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
    })
    print("Spotify: opening browser for one-time authorization...")
    webbrowser.open(auth_url)
    t.join(timeout=180)
    try:
        server.server_close()
    except Exception:
        pass
    code = code_holder.get("code")
    if not code:
        err = code_holder.get("error", "no code returned (timeout?)")
        print("Spotify auth failed:", err)
        return None
    auth_b64 = base64.b64encode(
        ("%s:%s" % (SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)).encode()).decode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": SPOTIFY_REDIRECT_URI,
        }).encode(),
        headers={"Authorization": "Basic " + auth_b64,
                 "Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            tokens = json.loads(r.read())
    except Exception as e:
        print("Spotify token exchange failed:", repr(e))
        return None
    tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)
    _SPOTIFY_TOKEN_FILE.write_text(json.dumps(tokens))
    print("Spotify: connected.")
    return tokens

def _spotify_refresh(refresh_token):
    import urllib.parse, urllib.request, base64
    auth_b64 = base64.b64encode(
        ("%s:%s" % (SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)).encode()).decode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }).encode(),
        headers={"Authorization": "Basic " + auth_b64,
                 "Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            tokens = json.loads(r.read())
    except Exception as e:
        print("Spotify refresh failed:", repr(e))
        return None
    tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)
    if "refresh_token" not in tokens:
        tokens["refresh_token"] = refresh_token
    _SPOTIFY_TOKEN_FILE.write_text(json.dumps(tokens))
    return tokens

def _spotify_token():
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        return None
    tokens = None
    if _SPOTIFY_TOKEN_FILE.exists():
        try:
            tokens = json.loads(_SPOTIFY_TOKEN_FILE.read_text())
        except Exception:
            tokens = None
    if tokens and time.time() >= tokens.get("expires_at", 0) - 30:
        tokens = _spotify_refresh(tokens.get("refresh_token", ""))
    if not tokens:
        tokens = _spotify_oauth_flow()
    return tokens.get("access_token") if tokens else None

def _spotify_request(method, path, params=None, body=None):
    import urllib.parse, urllib.request, urllib.error
    token = _spotify_token()
    if not token:
        return {"error": "Spotify not connected, sir."}
    url = "https://api.spotify.com/v1" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw else {"ok": True}
    except urllib.error.HTTPError as e:
        body_txt = ""
        try:
            body_txt = e.read().decode()
        except Exception:
            pass
        if e.code == 404:
            return {"error": "No active Spotify device, sir. Open Spotify on your phone or computer first."}
        if e.code == 403:
            return {"error": "Spotify Premium is required for that, sir."}
        return {"error": "HTTP %d: %s" % (e.code, body_txt[:200])}
    except Exception as e:
        return {"error": repr(e)}

def _spotify_ensure_active_device():
    r = _spotify_request("GET", "/me/player/devices")
    if "error" in r:
        return False, r["error"]
    devices = r.get("devices") or []
    if not devices:
        return False, "Spotify isn't open anywhere, sir. Open Spotify on a device first."
    if any(d.get("is_active") for d in devices):
        return True, None
    target = devices[0]
    transfer = _spotify_request("PUT", "/me/player",
                                body={"device_ids": [target["id"]], "play": False})
    if "error" in transfer:
        return False, ("Couldn't activate %s, sir: %s"
                       % (target.get("name", "device"), transfer["error"]))
    return True, None

def spotify_play(query=None):
    ok, err = _spotify_ensure_active_device()
    if not ok:
        return err
    if query:
        result = _spotify_request("GET", "/search", params={
            "q": query, "type": "track,artist,album,playlist", "limit": 3})
        if "error" in result:
            return "Couldn't search Spotify: %s" % result["error"]
        tracks = (result.get("tracks") or {}).get("items") or []
        playlists = (result.get("playlists") or {}).get("items") or []
        albums = (result.get("albums") or {}).get("items") or []
        artists = (result.get("artists") or {}).get("items") or []
        if tracks:
            t = tracks[0]
            r = _spotify_request("PUT", "/me/player/play", body={"uris": [t["uri"]]})
            if "error" in r:
                return "Couldn't play: %s" % r["error"]
            return "Playing %s by %s, sir." % (
                t.get("name", "Unknown"),
                (t.get("artists") or [{"name": "Unknown"}])[0].get("name", ""))
        if playlists:
            p = playlists[0]
            r = _spotify_request("PUT", "/me/player/play", body={"context_uri": p["uri"]})
            if "error" in r:
                return "Couldn't play: %s" % r["error"]
            return "Playing the playlist %s, sir." % p.get("name", "")
        if albums:
            a = albums[0]
            r = _spotify_request("PUT", "/me/player/play", body={"context_uri": a["uri"]})
            if "error" in r:
                return "Couldn't play: %s" % r["error"]
            return "Playing the album %s, sir." % a.get("name", "")
        if artists:
            ar = artists[0]
            r = _spotify_request("PUT", "/me/player/play", body={"context_uri": ar["uri"]})
            if "error" in r:
                return "Couldn't play: %s" % r["error"]
            return "Playing music by %s, sir." % ar.get("name", "")
        return "No results on Spotify for '%s', sir." % query
    r = _spotify_request("PUT", "/me/player/play")
    if "error" in r:
        return "Couldn't resume: %s" % r["error"]
    return "Resumed, sir."

def spotify_pause():
    ok, err = _spotify_ensure_active_device()
    if not ok:
        return err
    r = _spotify_request("PUT", "/me/player/pause")
    if "error" in r:
        return "Couldn't pause: %s" % r["error"]
    return "Paused, sir."

def spotify_next():
    ok, err = _spotify_ensure_active_device()
    if not ok:
        return err
    r = _spotify_request("POST", "/me/player/next")
    if "error" in r:
        return "Couldn't skip: %s" % r["error"]
    return "Next track, sir."

def spotify_previous():
    ok, err = _spotify_ensure_active_device()
    if not ok:
        return err
    r = _spotify_request("POST", "/me/player/previous")
    if "error" in r:
        return "Couldn't go back: %s" % r["error"]
    return "Previous track, sir."

def spotify_volume(level):
    try:
        v = int(level)
    except Exception:
        return "I need a volume number from 0 to 100, sir."
    v = max(0, min(100, v))
    ok, err = _spotify_ensure_active_device()
    if not ok:
        return err
    r = _spotify_request("PUT", "/me/player/volume", params={"volume_percent": v})
    if "error" in r:
        return "Couldn't set volume: %s" % r["error"]
    return "Volume set to %d%%, sir." % v

def spotify_now_playing():
    r = _spotify_request("GET", "/me/player/currently-playing")
    if "error" in r:
        return r["error"]
    if not r or not r.get("item"):
        return "Nothing playing, sir."
    item = r["item"]
    artists = ", ".join(a.get("name", "") for a in item.get("artists", []))
    return "%s by %s, sir." % (item.get("name", "Unknown"), artists)

def _el_pick_voice_id():
    global _el_voice_id_cache
    if _el_voice_id_cache:
        return _el_voice_id_cache
    if not ELEVENLABS_API_KEY:
        print("[diag] ElevenLabs: no API key in environment -> using edge-tts.", flush=True)
        return None
    try:
        req = urllib.request.Request(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": ELEVENLABS_API_KEY})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        voices = data.get("voices", [])
        by_name = {(v.get("name") or "").lower(): v.get("voice_id") for v in voices}
        for pref in EL_PREFERRED_VOICES:
            vid = by_name.get(pref.lower())
            if vid:
                _el_voice_id_cache = vid
                print(f"[diag] ElevenLabs voice selected: {pref} ({vid})", flush=True)
                return vid
        if voices:
            _el_voice_id_cache = voices[0].get("voice_id")
            print("[diag] ElevenLabs voice (first available):", voices[0].get("name"), flush=True)
            return _el_voice_id_cache
        print("[diag] ElevenLabs: account has no voices.", flush=True)
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")[:300]
        except Exception:
            detail = ""
        print("[diag] ElevenLabs voices HTTP error:", e.code, detail, flush=True)
    except Exception as e:
        print("[diag] ElevenLabs voice lookup failed:", repr(e), flush=True)
    return None

def speak_elevenlabs(text, fn):
    if not ELEVENLABS_API_KEY:
        return False
    vid = _el_pick_voice_id()
    if not vid:
        return False
    try:
        body = json.dumps({
            "text": text,
            "model_id": EL_MODEL,
            "voice_settings": {"stability": 0.55, "similarity_boost": 0.75,
                               "style": 0.0, "use_speaker_boost": True},
        }).encode("utf-8")
        url = ("https://api.elevenlabs.io/v1/text-to-speech/%s"
               "?output_format=mp3_44100_128" % vid)
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"xi-api-key": ELEVENLABS_API_KEY,
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            audio = resp.read()
        if not audio:
            return False
        with open(fn, "wb") as f:
            f.write(audio)
        return True
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")[:300]
        except Exception:
            detail = ""
        print("[diag] ElevenLabs TTS HTTP error:", e.code, detail, flush=True)
        return False
    except Exception as e:
        print("[diag] ElevenLabs TTS error:", repr(e), flush=True)
        return False

async def _speak(text, voice, fn="jarvis_reply.mp3"):
    await edge_tts.Communicate(text, voice, rate="-8%", pitch="-3Hz").save(fn)

def play_audio(path="jarvis_reply.mp3"):
    try:
        p = os.path.abspath(path)
        mci = ctypes.windll.winmm.mciSendStringW
        mci("close jarvisaudio", None, 0, 0)
        if mci('open "%s" type mpegvideo alias jarvisaudio' % p, None, 0, 0) == 0:
            mci("play jarvisaudio wait", None, 0, 0)
            mci("close jarvisaudio", None, 0, 0)
    except Exception as e:
        print("Audio playback error:", e)

def stop_audio():
    try:
        mci = ctypes.windll.winmm.mciSendStringW
        mci("stop jarvisaudio", None, 0, 0)
        mci("close jarvisaudio", None, 0, 0)
    except Exception:
        pass

def speak(text):
    fn = "jarvis_reply_%d.mp3" % (int(time.time() * 1000) % 1000000)
    try:
        produced = False
        mostly_he = is_mostly_hebrew(text)
        if not mostly_he:
            produced = speak_elevenlabs(text, fn)
        if not produced:
            voice = VOICE_HEBREW if mostly_he else VOICE_ENGLISH
            try:
                asyncio.run(_speak(text, voice, fn))
                produced = True
            except Exception as e:
                if not mostly_he:
                    try:
                        asyncio.run(_speak(text, VOICE_ENGLISH_FALLBACK, fn))
                        produced = True
                    except Exception as e2:
                        print("Voice error (fallback):", e2)
                else:
                    print("Voice error:", e)
        if produced:
            play_audio(fn)
    except Exception as e:
        print("Voice error:", e)
    finally:
        try:
            os.remove(fn)
        except Exception:
            pass

def save_log(u, j):
    now = datetime.datetime.now()
    lf = Path(SSD_OBSIDIAN_VAULT) / f"Log_{now.strftime('%Y-%m-%d')}.md"
    with open(lf, "a", encoding="utf-8") as f:
        f.write(f"\n### Chat - {now.strftime('%H:%M:%S')}\n**You:** {u}\n\n**JARVIS:** {j}\n\n---\n")

APP = None

def _image_block_from_path(path):
    try:
        mt = mimetypes.guess_type(path)[0] or "image/jpeg"
        if mt not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
            mt = "image/jpeg"
        with open(path, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode("ascii")
        return {"type": "image",
                "source": {"type": "base64", "media_type": mt, "data": data}}
    except Exception as e:
        print("Image read error:", repr(e))
        return None

def _link_depth_score(url):
    try:
        p = urllib.parse.urlparse(url or "")
        segs = [s for s in (p.path or "").split("/") if s]
        score = len(segs) * 2
        if p.query:
            score += 3
        low = (url or "").lower()
        for kw in ("modelid", "/item", "/p/", "product", "/dp/", "sku", ".aspx"):
            if kw in low:
                score += 4
        return score
    except Exception:
        return 0

def search_with_optional_image(user_text, image_path=None, lang="he"):
    if not ANTHROPIC_API_KEY:
        return ("[Error: Missing API Key in .env]", [])
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    sys_prompt = JARVIS_SYSTEM_PROMPT
    sys_prompt += (
        "\n\nYOU ARE NOW IN THE PRODUCT SEARCH WINDOW. Additional rules:\n"
        "- He is in ISRAEL and can only buy from stores that operate in Israel. "
        "Build the web_search query with explicit site filters, e.g. <product> "
        "site:zap.co.il OR site:ksp.co.il OR site:bug.co.il OR site:ivory.co.il "
        "OR site:idigital.co.il OR site:amazon.co.il. Also run a Hebrew query "
        "'<product> ישראל מחיר'. Prefer Zap.co.il. Prices in shekels only. NEVER "
        "return foreign stores unless the user explicitly names another country.\n"
        "- DEFAULT MARKET is Israel; only override when a country is named "
        "explicitly, then use that country's stores and currency.\n"
        "- If an image is attached, identify the product first, then search.\n"
        "- You CAN use find_places and get_directions here too.\n"
        "- Reply in %s.\n"
        "- CRITICAL FORMAT: AT MOST 2 short sentences. No lists/paragraphs/URLs "
        "in the reply text - the clickable result links are shown separately.\n\n"
        "DIRECT PRODUCT LINKS: after your short reply, output a machine-readable "
        "block listing the BEST DIRECT PRODUCT PAGES you actually found (not "
        "homepages). Only URLs that appeared in the web search results. Up to 6, "
        "best first. If none, leave it empty. Output EXACTLY:\n"
        "<<<LINKS>>>\n"
        "short title | https://full-url\n"
        "<<<ENDLINKS>>>"
        % ("Hebrew" if lang == "he" else "English"))
    sys_prompt += ("\nCurrent local time (Israel): "
                   + datetime.datetime.now().strftime("%Y-%m-%d %H:%M (%A)"))
    content = []
    if image_path:
        blk = _image_block_from_path(image_path)
        if blk:
            content.append(blk)
    content.append({"type": "text", "text": (user_text or "Find this product.")})
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 4}]
    for t in LOCAL_TOOLS:
        if t.get("name") in ("find_places", "get_directions"):
            tools.append(t)
    links = []
    spoken_parts = []
    try:
        msgs = [{"role": "user", "content": content}]
        for _ in range(5):
            r = client.messages.create(
                model="claude-sonnet-4-6", max_tokens=700,
                system=sys_prompt, messages=msgs, tools=tools)
            msgs.append({"role": "assistant", "content": r.content})
            for b in r.content:
                bt = getattr(b, "type", None)
                if bt == "text" and getattr(b, "text", "").strip():
                    spoken_parts.append(b.text.strip())
                elif bt == "web_search_tool_result":
                    results = getattr(b, "content", None) or []
                    for item in results:
                        url = getattr(item, "url", None)
                        title = getattr(item, "title", None) or url
                        if url:
                            links.append((title, url))
            if r.stop_reason == "tool_use":
                tool_results = []
                for block in r.content:
                    if getattr(block, "type", None) == "tool_use" and \
                            block.name in ("find_places", "get_directions"):
                        out = run_local_tool(block.name, block.input or {})
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": out,
                        })
                if tool_results:
                    msgs.append({"role": "user", "content": tool_results})
                continue
            break
        full_text = " ".join(spoken_parts)
        brain_links = []
        mblk = re.search(r"<<<\s*LINKS\s*>>>(.*?)<<<\s*ENDLINKS\s*>>>",
                         full_text, re.DOTALL | re.IGNORECASE)
        block_body = mblk.group(1) if mblk else ""
        if block_body:
            for line in block_body.splitlines():
                mu = re.search(r"(https?://\S+)", line)
                if not mu:
                    continue
                url = mu.group(1).rstrip(").,]»\"'")
                title = line[:mu.start()].strip().rstrip("|").strip() or url
                brain_links.append((title, url))
        spoken_raw = re.sub(r"<<<\s*LINKS\s*>>>.*?<<<\s*ENDLINKS\s*>>>", "",
                            full_text, flags=re.DOTALL | re.IGNORECASE)
        spoken_raw = re.sub(r"<<<\s*LINKS\s*>>>.*$", "", spoken_raw,
                            flags=re.DOTALL | re.IGNORECASE)
        spoken_raw = re.sub(r"https?://\S+", "", spoken_raw)
        spoken_raw = re.sub(r"\bwww\.\S+", "", spoken_raw)
        spoken = clean_text(spoken_raw).strip() or "Here is what I found, sir."
        if brain_links:
            chosen = brain_links
        else:
            chosen = sorted(links, key=lambda tu: _link_depth_score(tu[1]), reverse=True)
        seen, uniq = set(), []
        for t, u in chosen:
            if u not in seen:
                seen.add(u)
                uniq.append((t, u))
        return spoken, uniq[:8]
    except Exception as e:
        import traceback
        print("[diag] Search panel full traceback:", flush=True)
        traceback.print_exc()
        return (f"[Search error: {e}]", [])

RAMPS = {
    "loading":   ((70, 30, 15),   (150, 80, 40)),
    "idle":      ((120, 35, 10),  (255, 150, 60)),
    "listening": ((150, 45, 10),  (255, 180, 80)),
    "thinking":  ((140, 25, 10),  (255, 120, 40)),
    "speaking":  ((160, 55, 15),  (255, 200, 100)),
}
KEY = "#050507"
# v4.60: the face is the PIL black hole drawn INSIDE the floating orb window.
ACHILLES_FACE = "orb"

def _clamp(v):
    return 0 if v < 0 else (255 if v > 255 else int(v))

def _hexcol(r, g, b):
    return "#%02x%02x%02x" % (_clamp(r), _clamp(g), _clamp(b))

# ============================ TELEGRAM BRIDGE ============================
_TG_CHAT_FILE = str(Path(__file__).resolve().parent / "telegram_chat.json")
_tg_chat_id = None
_tg_pair_code = None
_tg_offset = 0

def _tg_api(method, params=None, timeout=60):
    if not TELEGRAM_BOT_TOKEN:
        return None
    url = "https://api.telegram.org/bot%s/%s" % (TELEGRAM_BOT_TOKEN, method)
    data = urllib.parse.urlencode(params).encode("utf-8") if params else None
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, data=data), timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None

def telegram_send(text, chat_id=None):
    cid = chat_id if chat_id is not None else _tg_chat_id
    if not TELEGRAM_BOT_TOKEN or cid is None or not text:
        return False
    t = text if len(text) <= 4000 else (text[:3990] + "...")
    res = _tg_api("sendMessage", {"chat_id": cid, "text": t})
    return bool(res and res.get("ok"))

def _tg_load_chat():
    global _tg_chat_id
    try:
        if os.path.exists(_TG_CHAT_FILE):
            with open(_TG_CHAT_FILE, "r", encoding="utf-8") as f:
                _tg_chat_id = json.load(f).get("chat_id")
    except Exception:
        _tg_chat_id = None

def _tg_save_chat(cid):
    global _tg_chat_id
    _tg_chat_id = cid
    try:
        with open(_TG_CHAT_FILE, "w", encoding="utf-8") as f:
            json.dump({"chat_id": cid}, f)
    except Exception:
        pass

class App:
    @property
    def state(self):
        return getattr(self, "_state_val", "loading")

    @state.setter
    def state(self, v):
        self._state_val = v
        try:
            _achilles_state["state"] = v
            _achilles_state["ts"] = time.time()
        except Exception:
            pass

    def __init__(self, root):
        global APP
        APP = self
        self.root = root
        self.state = "loading"
        self.wake_on = False
        self.busy = False
        self.stop = False
        self.model = None
        self.wake_model = None
        self.memory = ""
        self.outbox = []
        self._lock = threading.Lock()
        self._hold = ""
        self._hold_until = 0.0
        self.panel = None
        self.panel_busy = False
        self._last_user = ""
        self._last_reply = ""
        self._preroll = None
        self._bhL = None
        self._bh_ph = 0.0
        self._bh_star_a = 0.0
        if HAVE_PIL:
            threading.Thread(target=self._bh_build_async, daemon=True).start()

        sw = root.winfo_screenwidth()
        self.EW, self.EH = 400, 470
        self.ex = sw - self.EW - 30
        self.ey = 60

        self.mode = "hidden"
        self.req_mode = "hidden"
        self.typing = False
        self.req_typing = False

        root.title("ACHILLES")
        root.overrideredirect(True)
        try:
            _ico = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "achilles.ico")
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    u"horn.achilles.jarvis")
            except Exception:
                pass
            self._taskbar_anchor = tk.Toplevel(root)
            _tb = self._taskbar_anchor
            _tb.title("ACHILLES")
            _tb.geometry("1x1+-32000+-32000")
            _tb.attributes("-topmost", False)
            if os.path.isfile(_ico):
                try:
                    _tb.iconbitmap(default=_ico)
                except Exception:
                    try:
                        _tb.iconbitmap(_ico)
                    except Exception:
                        pass
                try:
                    root.iconbitmap(default=_ico)
                except Exception:
                    pass
            def _on_anchor_close():
                try:
                    self.stop = True
                except Exception:
                    pass
                try:
                    root.destroy()
                except Exception:
                    pass
            _tb.protocol("WM_DELETE_WINDOW", _on_anchor_close)
        except Exception as _e:
            print("[diag] taskbar anchor not created:", repr(_e))
        root.attributes("-topmost", True)
        try:
            root.attributes("-transparentcolor", KEY)
        except Exception:
            pass
        root.config(bg=KEY)
        root.geometry("%dx%d+%d+%d" % (self.EW, self.EH, self.ex, self.ey))
        root.withdraw()

        self.SS = 3
        self.use_pil = HAVE_PIL

        self.cv = tk.Canvas(root, bg=KEY, highlightthickness=0, bd=0)
        self.cv.pack(fill=tk.BOTH, expand=True)

        self.entry = tk.Entry(root, bg="#161b22", fg="#e6edf3",
                              insertbackground="#58a6ff", relief=tk.FLAT,
                              font=("Segoe UI", 11))
        self.entry.bind("<Return>", self._send_typed)

        self.N = 360
        self.pts = []
        ga = 2.399963
        for i in range(self.N):
            y = 1 - (i / (self.N - 1)) * 2
            rr = (1 - y * y) ** 0.5
            th = i * ga
            self.pts.append((np.cos(th) * rr, y, np.sin(th) * rr))

        self.img_id = self.cv.create_image(0, 0, anchor="nw")
        self._tkimg = None
        self.items = [self.cv.create_oval(0, 0, 0, 0, outline="", fill="")
                      for _ in range(self.N)]
        self.ripple_id = self.cv.create_oval(0, 0, 0, 0, outline="", width=2)
        self.ring_id = self.cv.create_oval(0, 0, 0, 0, outline="", width=2)
        self.status_id = self.cv.create_text(0, 0, text="", fill="#9aa7b4",
                                              font=("Segoe UI", 9))

        self.ang = 0.0
        self.zoom = 1.0
        self.sel = 0
        self.prev = "loading"
        self.ripple = 0.0
        self.ripple_on = False
        self._drag = (0, 0)
        self._moved = False

        self.menu = tk.Menu(root, tearoff=0)
        self.menu.add_command(label="Talk", command=lambda: self.talk(True))
        self.menu.add_command(label="Type", command=self._open_typing)
        self.menu.add_command(label="Search window", command=lambda: self.ui(self.open_panel))
        self.menu.add_command(label="Toggle Wake Word", command=self.toggle_wake)
        self.menu.add_separator()
        self.menu.add_command(label="Quit JARVIS", command=self.quit)

        self.cv.bind("<Button-3>", self._show_menu)
        self.cv.bind("<Double-Button-1>", lambda e: threading.Thread(
            target=open_portal, daemon=True).start())
        self.cv.bind("<Button-1>", self._drag_start)
        self.cv.bind("<B1-Motion>", self._drag_move)
        root.bind_all("<Escape>", lambda e: self._hide())
        root.bind_all("<F1>", lambda e: self._key_f1())
        root.bind_all("<F2>", lambda e: self._key_f2())
        root.bind_all("<F3>", lambda e: self._key_f3())
        root.bind_all("<F5>", lambda e: self._key_f5())

        threading.Thread(target=self._boot, daemon=True).start()
        threading.Thread(target=self._signal_watch, daemon=True).start()
        threading.Thread(target=self._telegram_loop, daemon=True).start()
        self.animate()

    def ui(self, fn):
        try:
            self.root.after(0, fn)
        except Exception:
            pass

    _UI = {
        "bg": "#0a0c10", "panel": "#11151b", "input": "#161b22",
        "hover": "#1f2733", "accent": "#ff8c42", "accent2": "#ffa55f",
        "ink": "#1a1205", "text": "#e6edf3", "muted": "#8b97a5",
        "link": "#7cc4ff", "divider": "#222a35",
    }

    def _hoverable(self, widget, normal, hover):
        widget.bind("<Enter>", lambda e: widget.config(bg=hover))
        widget.bind("<Leave>", lambda e: widget.config(bg=normal))

    def _round_rect(self, cv, x1, y1, x2, y2, r=14, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return cv.create_polygon(pts, smooth=True, **kw)

    def _make_orb_image(self, size=240):
        cx = cy = size / 2.0
        R = size * 0.30
        glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for rad, a in [(R * 2.7, 28), (R * 2.0, 44), (R * 1.5, 70), (R * 1.15, 110)]:
            gd.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=(255, 120, 40, a))
        glow = glow.filter(ImageFilter.GaussianBlur(size * 0.045))
        core = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        cd = ImageDraw.Draw(core)
        steps = 30
        for i in range(steps):
            t = i / (steps - 1)
            rr = R * (1 - t)
            col = (255, int(120 + 125 * t), int(40 + 155 * t), 255)
            cd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=col)
        core = core.filter(ImageFilter.GaussianBlur(size * 0.012))
        return Image.alpha_composite(glow, core)

    def _make_backdrop_image(self, w, h):
        top, bottom = (16, 16, 22), (6, 7, 10)
        grad = Image.new("RGB", (w, h))
        gd = ImageDraw.Draw(grad)
        for y in range(h):
            t = y / max(1, h - 1)
            gd.line([(0, y), (w, y)],
                    fill=(int(top[0] * (1 - t) + bottom[0] * t),
                          int(top[1] * (1 - t) + bottom[1] * t),
                          int(top[2] * (1 - t) + bottom[2] * t)))
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gld = ImageDraw.Draw(glow)
        gx, gy = w // 2, int(h * 0.15)
        for rad, a in [(360, 16), (260, 24), (170, 32), (90, 40)]:
            gld.ellipse([gx - rad, gy - rad, gx + rad, gy + rad], fill=(255, 110, 40, a))
        glow = glow.filter(ImageFilter.GaussianBlur(60))
        return Image.alpha_composite(grad.convert("RGBA"), glow).convert("RGB")

    def _cbutton(self, cv, x1, y1, x2, y2, label, cmd, primary=False):
        c = self._UI
        base = c["accent"] if primary else c["input"]
        hov = c["accent2"] if primary else c["hover"]
        fg = c["ink"] if primary else c["text"]
        outline = "" if primary else c["divider"]
        tag = "cbtn%d" % self._cbtn_n
        self._cbtn_n += 1
        rid = self._round_rect(cv, x1, y1, x2, y2, r=14,
                               fill=base, outline=outline, tags=(tag,))
        cv.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=label, fill=fg,
                       font=("Segoe UI", 11, "bold"), tags=(tag,))
        cv.tag_bind(tag, "<Enter>",
                    lambda e, i=rid: (cv.itemconfig(i, fill=hov), cv.config(cursor="hand2")))
        cv.tag_bind(tag, "<Leave>",
                    lambda e, i=rid: (cv.itemconfig(i, fill=base), cv.config(cursor="")))
        cv.tag_bind(tag, "<Button-1>", lambda e: cmd())

    def _render_orb_frame(self, size, ang):
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        R = size * 0.30
        focal = R * 2.6
        cx = cy = size / 2.0
        disc = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        dd = ImageDraw.Draw(disc)
        dr_r = R * 1.55
        steps = 22
        for k in range(steps):
            t = k / (steps - 1.0)
            rr = dr_r * (1.0 - t)
            dd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                       fill=(int(40 + 90 * t), int(15 + 35 * t), int(8 + 12 * t), 255))
        try:
            disc = disc.filter(ImageFilter.GaussianBlur(size * 0.02))
        except Exception:
            pass
        img.alpha_composite(disc)
        dr = ImageDraw.Draw(img)
        sa, ca = np.sin(ang), np.cos(ang)
        lo, hi = RAMPS["idle"]
        pts = self.pts[::2]
        order = sorted(((-p[0] * sa + p[2] * ca), idx) for idx, p in enumerate(pts))
        for z, i in order:
            px0, py0, pz0 = pts[i]
            x = px0 * ca + pz0 * sa
            sc = focal / (focal + z * R)
            X = cx + x * R * sc
            Y = cy + py0 * R * sc
            depth = (z + 1) / 2.0
            rad = 1.1 + 2.0 * depth
            r = lo[0] + (hi[0] - lo[0]) * depth
            g = lo[1] + (hi[1] - lo[1]) * depth
            b = lo[2] + (hi[2] - lo[2]) * depth
            a = int(70 + 170 * depth)
            gr = rad * 2.4
            dr.ellipse([X - gr, Y - gr, X + gr, Y + gr],
                       fill=(_clamp(r), _clamp(g), _clamp(b), int(a * 0.28)))
            dr.ellipse([X - rad, Y - rad, X + rad, Y + rad],
                       fill=(_clamp(r), _clamp(g), _clamp(b), _clamp(a)))
        try:
            img = img.filter(ImageFilter.GaussianBlur(0.5))
        except Exception:
            pass
        return img

    def _panel_close(self):
        self._panel_speaking = False
        try:
            stop_audio()
        except Exception:
            pass
        try:
            if self.panel is not None:
                self.panel.destroy()
        except Exception:
            pass

    def _panel_show_typing(self):
        try:
            self.panel.focus_force()
            self._pulse_cv.itemconfig(self._entry_win, state="normal")
            self.panel_entry.focus_set()
        except Exception:
            pass

    def _panel_stop_speaking(self):
        self._panel_speaking = False
        stop_audio()

    def _panel_is_open(self):
        try:
            return (self.panel is not None
                    and tk.Toplevel.winfo_exists(self.panel)
                    and bool(self.panel.winfo_ismapped()))
        except Exception:
            return False

    def _key_f1(self):
        self._panel_show_typing() if self._panel_is_open() else self._open_typing()

    def _key_f2(self):
        self._panel_speak() if self._panel_is_open() else self._save_last_exchange()

    def _key_f3(self):
        self._panel_pick_image() if self._panel_is_open() else self._repeat_last()

    def _key_f5(self):
        if self._panel_is_open():
            self._panel_stop_speaking()
        else:
            stop_audio()

    def _panel_pulse_tick(self):
        if not (self.panel and tk.Toplevel.winfo_exists(self.panel)):
            return
        try:
            cv = self._pulse_cv
            if getattr(self, "_hud_time", None) is not None:
                now = datetime.datetime.now()
                cv.itemconfig(self._hud_time, text=now.strftime("%H:%M:%S"))
                cv.itemconfig(self._hud_date, text=now.strftime("%A, %d %B %Y"))
            if getattr(self, "_orb_frames", None):
                self._orb_idx = (self._orb_idx + 1) % len(self._orb_frames)
                cv.itemconfig(self._orb_item, image=self._orb_frames[self._orb_idx])
            if getattr(self, "_panel_speaking", False):
                cv.itemconfig(self._pulse_item, state="normal")
                cv.itemconfig(self._pulse_glow, state="normal")
                x0, x1, y = self._pulse_x0, self._pulse_x1, self._pulse_y
                ph = self._pulse_phase
                n = 70
                pts = []
                for i in range(n + 1):
                    t = i / n
                    env = np.sin(np.pi * t)
                    yv = y + 16.0 * env * (0.7 * np.sin(8 * t * np.pi + ph)
                                           + 0.3 * np.sin(15 * t * np.pi - ph * 1.7))
                    pts += [x0 + (x1 - x0) * t, yv]
                cv.coords(self._pulse_item, *pts)
                cv.coords(self._pulse_glow, *pts)
                self._pulse_phase += 0.5
            else:
                cv.itemconfig(self._pulse_item, state="hidden")
                cv.itemconfig(self._pulse_glow, state="hidden")
        except Exception:
            pass
        self.panel.after(60, self._panel_pulse_tick)

    def open_panel(self):
        if self.panel is not None and tk.Toplevel.winfo_exists(self.panel):
            self.panel.deiconify()
            self.panel.lift()
            return
        c = self._UI
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        W, H = sw, sh
        w = tk.Toplevel(self.root)
        self.panel = w
        w.configure(bg=c["bg"])
        w.overrideredirect(True)
        w.geometry("%dx%d+0+0" % (W, H))
        w.attributes("-topmost", True)
        try:
            w.focus_force()
        except Exception:
            pass
        w.bind("<Escape>", lambda e: self._panel_close())
        cv = tk.Canvas(w, width=W, height=H, bg=c["bg"], highlightthickness=0, bd=0)
        cv.pack(fill=tk.BOTH, expand=True)
        self._pulse_cv = cv
        self._cbtn_n = 0
        self._panel_link_n = 0
        self._panel_speaking = False
        cxm = W // 2
        orb_cy = int(H * 0.21)
        osize = max(180, min(int(min(W, H) * 0.26), 360))
        VER = "v4.16"
        hx = 44
        self._hud_time = cv.create_text(hx, 46, anchor="nw", text="00:00:00",
                                        fill=c["accent"], font=("Consolas", 30, "bold"))
        self._hud_date = cv.create_text(hx, 92, anchor="nw", text="",
                                        fill=c["muted"], font=("Consolas", 13))
        cv.create_text(hx, 130, anchor="nw", text="JARVIS  %s" % VER,
                       fill=c["text"], font=("Consolas", 12, "bold"))
        cv.create_text(hx, 152, anchor="nw", text="STATUS  ·  ONLINE",
                       fill=c["accent2"], font=("Consolas", 11))
        cv.create_text(hx, 188, anchor="nw", text="PROJECTS", fill=c["muted"],
                       font=("Consolas", 11, "bold"))
        cv.create_text(hx, 210, anchor="nw", text="› JARVIS  (this assistant)",
                       fill=c["text"], font=("Consolas", 11))
        self._orb_frames = []
        self._orb_idx = 0
        if self.use_pil:
            NF = 24
            for k in range(NF):
                pil = self._render_orb_frame(osize, (k / NF) * 2 * np.pi)
                self._orb_frames.append(ImageTk.PhotoImage(pil))
            self._orb_item = cv.create_image(cxm, orb_cy, image=self._orb_frames[0])
        else:
            self._orb_item = cv.create_oval(cxm - osize // 4, orb_cy - osize // 4,
                                            cxm + osize // 4, orb_cy + osize // 4,
                                            fill=c["accent"], outline="")
        title_y = orb_cy + osize // 2 + 18
        cv.create_text(cxm, title_y, text="ACHILLES", fill=c["accent"],
                       font=("Segoe UI", 30, "bold"))
        cv.create_text(cxm, title_y + 30, text="P R O D U C T   S E A R C H",
                       fill=c["muted"], font=("Segoe UI", 11, "bold"))
        self._pulse_y = title_y + 64
        self._pulse_x0 = int(W * 0.30)
        self._pulse_x1 = int(W * 0.70)
        self._pulse_glow = cv.create_line(
            self._pulse_x0, self._pulse_y, self._pulse_x1, self._pulse_y,
            fill="#7a3d14", width=6, capstyle="round", joinstyle="round",
            smooth=True, state="hidden")
        self._pulse_item = cv.create_line(
            self._pulse_x0, self._pulse_y, self._pulse_x1, self._pulse_y,
            fill=c["accent"], width=2, capstyle="round", joinstyle="round",
            smooth=True, state="hidden")
        self._pulse_phase = 0.0
        TX1, TX2 = int(W * 0.16), int(W * 0.84)
        TY1, TY2 = int(H * 0.42), int(H * 0.84)
        self.panel_out = tk.Text(cv, bg=c["bg"], fg=c["text"],
                                 insertbackground=c["text"], font=("Segoe UI", 13),
                                 wrap="word", relief=tk.FLAT, bd=0,
                                 highlightthickness=0, padx=10, pady=8)
        cv.create_window(TX1, TY1, anchor="nw", window=self.panel_out,
                         width=TX2 - TX1, height=TY2 - TY1)
        self.panel_out.bind("<MouseWheel>",
                            lambda e: self.panel_out.yview_scroll(int(-e.delta / 120), "units"))
        self.panel_out.configure(state="disabled")
        o = self.panel_out
        o.tag_config("you",    foreground=c["link"],   font=("Segoe UI", 13, "bold"))
        o.tag_config("jarvis", foreground=c["accent"], font=("Segoe UI", 13, "bold"))
        o.tag_config("sys",    foreground=c["muted"],  font=("Segoe UI", 11, "italic"))
        o.tag_config("body",   foreground=c["text"], spacing1=2, spacing3=12,
                     lmargin1=4, lmargin2=4)
        self.panel_entry = tk.Entry(cv, bg=c["input"], fg=c["text"],
                                    insertbackground=c["accent"], relief=tk.FLAT,
                                    bd=0, highlightthickness=1,
                                    highlightbackground=c["divider"],
                                    highlightcolor=c["accent"], font=("Segoe UI", 13))
        self._entry_win = cv.create_window(cxm, int(H * 0.875), anchor="center",
                                           window=self.panel_entry,
                                           width=int(W * 0.5), height=38,
                                           state="hidden")
        self.panel_entry.bind("<Return>", lambda e: self._panel_ask_typed())
        cv.create_text(cxm, int(H * 0.93),
                       text="F1  Type        F2  Speak        F3  Image        "
                            "F5  Stop        Esc  Close",
                       fill=c["muted"], font=("Segoe UI", 12))
        self._panel_write("JARVIS", "Ready, sir. Press F1 to write, F2 to speak, "
                          "or F3 to send a product image. F5 stops me speaking. I "
                          "search Israeli stores and reply in English unless you "
                          "write in Hebrew.")
        self._panel_pulse_tick()

    def _panel_write(self, who, text):
        if self.panel is None or not tk.Toplevel.winfo_exists(self.panel):
            return
        self.panel_out.configure(state="normal")
        tag = "you" if who == "You" else ("sys" if who == "System" else "jarvis")
        self.panel_out.insert("end", f"{who}  ", tag)
        self.panel_out.insert("end", text + "\n\n", "body")
        self.panel_out.see("end")
        self.panel_out.configure(state="disabled")

    def _panel_add_link(self, title, url):
        if self.panel is None or not tk.Toplevel.winfo_exists(self.panel):
            return
        c = self._UI
        self.panel_out.configure(state="normal")
        tagname = "link%d" % self._panel_link_n
        self._panel_link_n += 1
        self.panel_out.tag_config("bullet", foreground=c["accent"],
                                  font=("Segoe UI", 12, "bold"))
        self.panel_out.insert("end", "   ›  ", "bullet")
        self.panel_out.insert("end", (title or url) + "\n", (tagname,))
        self.panel_out.tag_config(tagname, foreground=c["link"], underline=True, spacing3=6)
        self.panel_out.tag_bind(tagname, "<Button-1>", lambda e, u=url: webbrowser.open(u))
        self.panel_out.tag_bind(tagname, "<Enter>", lambda e: self.panel_out.config(cursor="hand2"))
        self.panel_out.tag_bind(tagname, "<Leave>", lambda e: self.panel_out.config(cursor=""))
        self.panel_out.see("end")
        self.panel_out.configure(state="disabled")

    def _panel_run(self, user_text, image_path=None):
        if self.panel_busy:
            return
        self.panel_busy = True
        try:
            lang = "he" if is_hebrew(user_text or "") else "en"
            bpart = None if image_path else detect_briefing(user_text)
            if bpart:
                self.ui(lambda: self._panel_write("System", "Briefing..."))
                brief = daily_briefing(bpart, lang)
                self.ui(lambda b=brief: self._panel_write("JARVIS", b))
                self._panel_speaking = True
                try:
                    speak(brief)
                finally:
                    self._panel_speaking = False
                return
            self.ui(lambda: self._panel_write("System", "Searching..."))
            spoken, links = search_with_optional_image(user_text, image_path, lang)
            def render():
                self._panel_write("JARVIS", spoken)
                if links:
                    self._panel_write("System", "Links (click to open):")
                    for t, u in links:
                        self._panel_add_link(t, u)
                else:
                    self._panel_write("System", "No links found.")
            self.ui(render)
            self._panel_speaking = True
            try:
                speak(spoken)
            except Exception:
                pass
            finally:
                self._panel_speaking = False
        finally:
            self.panel_busy = False

    def _panel_ask_typed(self):
        if self.panel is None or self.panel_busy:
            return
        txt = self.panel_entry.get().strip()
        if not txt:
            return
        self.panel_entry.delete(0, tk.END)
        try:
            self._pulse_cv.itemconfig(self._entry_win, state="hidden")
        except Exception:
            pass
        self._panel_write("You", txt)
        threading.Thread(target=self._panel_run, args=(txt,), daemon=True).start()

    def _panel_speak(self):
        if self.panel is None or self.panel_busy or self.model is None:
            return
        def worker():
            self.ui(lambda: self._panel_write("System", "Listening... speak now."))
            af = record_until_silence()
            text, _lang = transcribe(self.model, af)
            text = (text or "").strip()
            if len(text) < 2:
                self.ui(lambda: self._panel_write("System", "I didn't catch that, sir."))
                return
            self.ui(lambda: self._panel_write("You", text))
            self._panel_run(text)
        threading.Thread(target=worker, daemon=True).start()

    def _panel_pick_image(self):
        if self.panel is None or self.panel_busy:
            return
        path = filedialog.askopenfilename(
            parent=self.panel, title="Choose a product image",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.gif *.webp"),
                       ("All files", "*.*")])
        if not path:
            return
        self._panel_write("You", "[image] " + os.path.basename(path))
        prompt = self.panel_entry.get().strip() or "Identify this product and find where to buy it."
        self.panel_entry.delete(0, tk.END)
        threading.Thread(target=self._panel_run, args=(prompt, path), daemon=True).start()

    def _req(self, m):
        self.req_mode = m

    def _face_req(self):
        if ACHILLES_FACE != "blackhole":
            self._req("expanded")
            # Apply on the main thread right now so the visual feedback (the orb)
            # pops the instant the wake fires, not only on the next animate tick.
            try:
                self.ui(self._apply_mode)
            except Exception:
                pass

    def _hide(self):
        self.req_typing = False
        self.req_mode = "hidden"

    def _apply_mode(self):
        if self.req_mode != self.mode:
            self.mode = self.req_mode
            if self.mode == "expanded":
                self.root.deiconify()
                self.root.lift()
                self.root.attributes("-topmost", True)
            else:
                self.root.withdraw()
        if self.req_typing != self.typing:
            self.typing = self.req_typing
            if self.typing and self.mode == "expanded":
                self.entry.place(relx=0.5, rely=1.0, y=-12, anchor="s", relwidth=0.82)
                self.entry.focus_set()
            else:
                self.entry.place_forget()

    def _show_menu(self, e):
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()

    def _drag_start(self, e):
        self._drag = (e.x, e.y)
        self._moved = False

    def _drag_move(self, e):
        self._moved = True
        x = self.root.winfo_x() + e.x - self._drag[0]
        y = self.root.winfo_y() + e.y - self._drag[1]
        self.root.geometry("+%d+%d" % (x, y))
        self.ex, self.ey = x, y

    def _open_typing(self):
        self._req("expanded")
        self.req_typing = True

    def _save_last_exchange(self):
        if not self._last_user and not self._last_reply:
            self._req("expanded")
            self._push("System", "Nothing to save yet, sir.")
            return
        note = f"You: {self._last_user}\n  JARVIS: {self._last_reply}"
        status = save_note(note)
        self._req("expanded")
        self._push("System", status)

    def _repeat_last(self):
        if not self._last_reply:
            self._req("expanded")
            self._push("System", "I haven't said anything yet, sir.")
            return
        self._req("expanded")
        self._push("System", "Repeating last reply.")
        threading.Thread(target=lambda: speak(self._last_reply), daemon=True).start()

    def talk(self, collapse_after):
        if not self.busy and self.model is not None:
            self._face_req()
            threading.Thread(target=self._turn, args=(False, collapse_after),
                             daemon=True).start()

    def _send_typed(self, _e=None):
        if self.busy or self.model is None:
            return
        txt = self.entry.get().strip()
        if not txt:
            return
        self.entry.delete(0, tk.END)
        threading.Thread(target=self._typed_turn, args=(txt,), daemon=True).start()

    def toggle_wake(self):
        self.wake_on = not self.wake_on

    def quit(self):
        self.stop = True
        try:
            if os.path.exists(SHOW_SIGNAL):
                os.remove(SHOW_SIGNAL)
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            os._exit(0)

    def _push(self, who, text):
        with self._lock:
            self.outbox.append({"who": who, "text": text})

    def status_text(self):
        s = self.state
        if s == "loading":
            return "Loading models..."
        if s == "listening":
            return "Listening...  (say 'write' to type)"
        if s == "thinking":
            return "Thinking..."
        if s == "speaking":
            return "Speaking..."
        if self.typing:
            return "Type and press Enter"
        return "Listening for 'Hey JARVIS'" if self.wake_on else "Wake word OFF"

    def _signal_watch(self):
        while not self.stop:
            try:
                if os.path.exists(SHOW_SIGNAL):
                    os.remove(SHOW_SIGNAL)
                    if not self.busy:
                        self.talk(collapse_after=True)
            except Exception:
                pass
            time.sleep(0.4)

    def _boot(self):
        ensure_directories()
        self.state = "loading"
        self._face_req()
        self.wake_model = WhisperModel(WAKE_MODEL_SIZE, device="cpu", compute_type="int8")
        self.model = WhisperModel("small", device="cpu", compute_type="int8")
        self.memory = load_long_term_memory()
        if not ANTHROPIC_API_KEY:
            self.state = "idle"
            self._push("System", "No API key found in .env")
            return
        self.state = "idle"
        self.wake_on = True
        self._push("System", "Achilles online, sir.")
        try:
            speak("Achilles online, sir.")
        except Exception:
            pass
        if ACHILLES_FACE == "blackhole":
            def _open_face():
                try:
                    time.sleep(1.0)
                    print("[face]", open_achilles("core", face=True), flush=True)
                except Exception as e:
                    print("[diag] face window failed:", repr(e), flush=True)
            threading.Thread(target=_open_face, daemon=True).start()
        time.sleep(1.6)
        try:
            self._maybe_auto_briefing()
        except Exception as e:
            print("[diag] auto-briefing failed:", repr(e), flush=True)
        try:
            self._maybe_auto_backup()
        except Exception as e:
            print("[diag] auto-backup failed:", repr(e), flush=True)
        self._hide()
        threading.Thread(target=self._wake_loop, daemon=True).start()
        if HAVE_KEYBOARD:
            try:
                keyboard.add_hotkey("f1", lambda: self.ui(self._key_f1))
                keyboard.add_hotkey("f2", lambda: self.ui(self._key_f2))
                keyboard.add_hotkey("f3", lambda: self.ui(self._key_f3))
                keyboard.add_hotkey("f5", lambda: self.ui(self._key_f5))
            except Exception as e:
                print("Hotkey registration failed:", e)

    def _maybe_auto_briefing(self):
        marker = Path(".jarvis_last_briefing")
        today = datetime.date.today().isoformat()
        try:
            if marker.exists() and marker.read_text(encoding="utf-8").strip() == today:
                return
        except Exception:
            pass
        try:
            marker.write_text(today, encoding="utf-8")
        except Exception:
            pass
        part = _briefing_part_from_clock(datetime.datetime.now())
        self._face_req()
        self.state = "thinking"
        brief = daily_briefing(part, "en")
        self._push("JARVIS", brief)
        self._last_reply = brief
        self.state = "speaking"
        try:
            speak(brief)
        except Exception:
            pass
        time.sleep(min(14.0, max(3.0, len(brief.split()) * 0.45)))

    def _maybe_auto_backup(self):
        marker = Path(".jarvis_last_backup")
        today = datetime.date.today().isoformat()
        try:
            if marker.exists() and marker.read_text(encoding="utf-8").strip() == today:
                return
        except Exception:
            pass
        try:
            marker.write_text(today, encoding="utf-8")
        except Exception:
            pass
        threading.Thread(target=backup_vault, daemon=True).start()

    def _turn(self, announce, collapse_after):
        try:
            try:
                with open("wake_diag.log", "a", encoding="utf-8") as _wf:
                    _wf.write("[turn] entered announce=%s\n" % (announce,))
            except Exception:
                pass
            self.busy = True
            if announce:
                beep()
            keep_going = self._one_exchange(first=True)
            while keep_going and not self.stop:
                keep_going = self._one_exchange(first=False)
        except Exception as e:
            try:
                with open("wake_diag.log", "a", encoding="utf-8") as _wf:
                    _wf.write("[turn-error] %r\n" % (e,))
            except Exception:
                pass
            self._push("System", "Error: " + str(e))
        finally:
            self.busy = False
            self.state = "idle"
            if collapse_after and not self.typing:
                time.sleep(1.0)
                self._hide()

    def _one_exchange(self, first):
        self.state = "listening"
        if first:
            pr = getattr(self, "_preroll", None)
            self._preroll = None
            af = record_until_silence(preroll=pr)
        else:
            af = record_followup(start_timeout=5.0)
            if af is None:
                return False
        self.state = "thinking"
        user_text, lang = transcribe(self.model, af)
        try:
            with open("wake_diag.log", "a", encoding="utf-8") as _wf:
                _wf.write("[cmd first=%s] af=%r text=%r lang=%r\n" % (first, af, user_text, lang))
        except Exception:
            pass
        if first and user_text:
            user_text = strip_wake_prefix(user_text)
        cleaned = (user_text or "").strip()
        if len(cleaned) < 3 or not re.search(r'[A-Za-z֐-׿]', cleaned):
            if first:
                ack = "כן, אדוני?" if lang == "he" else "Yes, sir?"
                self._push("JARVIS", ack)
                self.state = "speaking"
                speak(ack)
                return True
            return False
        if detect_write(user_text) and len(user_text.split()) <= 3:
            self._req("expanded")
            self.req_typing = True
            self._push("System", "Typing enabled. Go ahead, sir.")
            return False
        bpart = detect_briefing(user_text)
        if bpart:
            self._push("You", user_text)
            self.state = "thinking"
            blang = "he" if (lang == "he" or is_hebrew(user_text)) else "en"
            brief = daily_briefing(bpart, blang)
            self._push("JARVIS", brief)
            save_log(user_text, brief)
            self._last_user = user_text
            self._last_reply = brief
            self.state = "speaking"
            speak(brief)
            time.sleep(min(14.0, max(3.0, len(brief.split()) * 0.45)))
            return True
        if detect_goodbye(user_text):
            bye = pick_farewell(lang == "he" or is_hebrew(user_text))
            self._push("You", user_text)
            self._push("JARVIS", bye)
            save_log(user_text, bye)
            self._last_user = user_text
            self._last_reply = bye
            self.state = "speaking"
            speak(bye)
            time.sleep(min(8.0, max(2.0, len(bye.split()) * 0.45)))
            return False
        self._push("You", user_text)
        reply = think(user_text, self.memory, lang)
        end_now = bool(re.search(r'<\s*END\s*>', reply, re.IGNORECASE))
        if end_now:
            reply = re.sub(r'<\s*END\s*>', '', reply, flags=re.IGNORECASE).strip()
            if not reply:
                reply = pick_farewell(lang == "he")
        self._push("JARVIS", reply)
        save_log(user_text, reply)
        self._last_user = user_text
        self._last_reply = reply
        self.state = "speaking"
        speak(reply)
        time.sleep(min(12.0, max(2.0, len(reply.split()) * 0.45)))
        return not end_now

    def _typed_turn(self, text):
        try:
            self.busy = True
            self._push("You", text)
            self.state = "thinking"
            lang = "he" if is_hebrew(text) else "en"
            bpart = detect_briefing(text)
            if bpart:
                brief = daily_briefing(bpart, lang)
                self._push("JARVIS", brief)
                save_log(text, brief)
                self._last_user = text
                self._last_reply = brief
                self.state = "speaking"
                speak(brief)
                time.sleep(min(14.0, max(3.0, len(brief.split()) * 0.45)))
                return
            reply = think(text, self.memory, lang)
            self._push("JARVIS", reply)
            save_log(text, reply)
            self._last_user = text
            self._last_reply = reply
            self.state = "speaking"
            speak(reply)
            time.sleep(min(12.0, max(2.5, len(reply.split()) * 0.45)))
        except Exception as e:
            self._push("System", "Error: " + str(e))
        finally:
            self.busy = False
            self.state = "idle"

    def _telegram_turn(self, text):
        lang = "he" if is_hebrew(text) else "en"
        bpart = detect_briefing(text)
        if bpart:
            return daily_briefing(bpart, lang)
        return think(text, self.memory, lang)

    def _telegram_loop(self):
        global _tg_offset, _tg_pair_code
        if not TELEGRAM_BOT_TOKEN:
            return
        import random
        _tg_load_chat()
        time.sleep(3)
        if _tg_chat_id is None:
            _tg_pair_code = "%06d" % random.randint(0, 999999)
            try:
                with open(str(Path(__file__).resolve().parent
                              / "telegram_pairing.txt"), "w", encoding="utf-8") as _pf:
                    _pf.write("JARVIS Telegram pairing code: " + _tg_pair_code
                              + "  (send this code to your bot to link it)")
            except Exception:
                pass
            try:
                self._push("JARVIS", "טלגרם: שלח לבוט את הקוד " + _tg_pair_code
                           + " כדי לחבר.")
            except Exception:
                pass
            print("[telegram] pairing code: " + _tg_pair_code, flush=True)
        else:
            print("[telegram] paired with chat %s - listening." % _tg_chat_id, flush=True)
        r0 = _tg_api("getUpdates", {"timeout": 0, "offset": -1}, timeout=10)
        if r0 and r0.get("ok") and r0.get("result"):
            _tg_offset = r0["result"][-1]["update_id"] + 1
        while not self.stop:
            r = _tg_api("getUpdates", {"timeout": 50, "offset": _tg_offset}, timeout=60)
            if not r or not r.get("ok"):
                time.sleep(3)
                continue
            for upd in r.get("result", []):
                _tg_offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("edited_message")
                if not msg or "text" not in msg:
                    continue
                cid = msg["chat"]["id"]
                text = msg["text"].strip()
                if not text:
                    continue
                if _tg_chat_id is None:
                    if _tg_pair_code and text == _tg_pair_code:
                        _tg_save_chat(cid)
                        try:
                            os.remove(str(Path(__file__).resolve().parent
                                          / "telegram_pairing.txt"))
                        except Exception:
                            pass
                        telegram_send("מחובר. JARVIS צמוד אליך עכשיו, אדוני. שלח לי כל דבר.", cid)
                        try:
                            self._push("JARVIS", "Telegram paired.")
                        except Exception:
                            pass
                    else:
                        telegram_send("שלח את קוד הצימוד שמופיע על JARVIS כדי לחבר.", cid)
                    continue
                if cid != _tg_chat_id:
                    telegram_send("לא מורשה.", cid)
                    continue
                waited = 0.0
                while self.busy and waited < 60:
                    time.sleep(0.5); waited += 0.5
                self.busy = True
                try:
                    _tg_api("sendChatAction", {"chat_id": cid, "action": "typing"}, timeout=10)
                    reply = self._telegram_turn(text)
                except Exception as e:
                    reply = "Error: " + str(e)
                finally:
                    self.busy = False
                telegram_send(reply or "(no reply)", cid)
                try:
                    self._push("Telegram", text)
                    self._push("JARVIS", reply)
                except Exception:
                    pass

    def _wake_loop(self):
        ring_len = int(SAMPLE_RATE * WAKE_WINDOW)
        block = int(SAMPLE_RATE * 0.1)
        while not self.stop:
            if not self.wake_on or self.busy or self.wake_model is None:
                time.sleep(0.2)
                continue
            ring = {"buf": np.zeros(ring_len, dtype=np.float32)}
            lock = threading.Lock()

            def cb(indata, frames, t_info, status, _ring=ring, _lock=lock):
                x = indata[:, 0]
                n = len(x)
                with _lock:
                    b = _ring["buf"]
                    b = np.roll(b, -n)
                    b[-n:] = x
                    _ring["buf"] = b

            triggered = False
            try:
                with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32',
                                    blocksize=block, callback=cb):
                    time.sleep(WAKE_STEP)
                    while not self.stop and self.wake_on and not self.busy:
                        with lock:
                            buf = ring["buf"].copy()
                        if float(np.max(np.abs(buf))) >= WAKE_GATE:
                            sf.write("wake_window.wav", buf, SAMPLE_RATE)
                            try:
                                text = transcribe_wake(self.wake_model, "wake_window.wav")
                            except Exception:
                                text = ""
                            # Fire whenever a wake word is clearly present. The
                            # old "<= 4 words" cap silently rejected valid wakes
                            # when the tiny model expanded the clip into a short
                            # phrase (e.g. "hey jarvis are you there"); the
                            # generous cap below still rejects long hallucinated
                            # runs of speech that merely happen to contain a name.
                            _hit = (bool(text) and detect_wake(text)
                                    and len(text.split()) <= 8)
                            if text:
                                try:
                                    with open("wake_diag.log", "a", encoding="utf-8") as _wf:
                                        _wf.write("[heard] %r match=%s\n" % (text, _hit))
                                except Exception:
                                    pass
                            if _hit:
                                triggered = True
                                with lock:
                                    tail = ring["buf"][-int(SAMPLE_RATE * PREROLL_SEC):].copy()
                                self._preroll = tail
                                break
                        time.sleep(WAKE_STEP)
            except Exception as e:
                print("[diag] wake-loop mic reopen failed, retrying:", repr(e), flush=True)
                # Surface it: a console-less GUI hides print(), so without this
                # the wake path can be dead while looking like "not hearing me".
                try:
                    self._push("System", "Microphone unavailable - retrying. "
                               "Close other apps using the mic, sir.")
                except Exception:
                    pass
                time.sleep(0.6)
            if triggered:
                try:
                    with open("wake_diag.log", "a", encoding="utf-8") as _wf:
                        _wf.write("[trigger] firing _turn\n")
                except Exception:
                    pass
                self._push("System", "Wake word detected.")
                self._face_req()
                self._turn(True, collapse_after=True)
                time.sleep(0.6)

    def _bh_build_async(self):
        try:
            self._bh_make_layers(520)
            print("[face] black-hole layers ready", flush=True)
        except Exception as e:
            print("[diag] black-hole prerender failed, keeping orb:", repr(e), flush=True)

    def _bh_make_layers(self, S):
        NF = 24
        ax = np.linspace(-1.0, 1.0, S, dtype=np.float32)
        x, y = np.meshgrid(ax, ax)
        yd = y / 0.26
        r = np.sqrt(x * x + yd * yd)
        th = np.arctan2(yd, x)
        rc = np.sqrt(x * x + y * y)
        RH, D1, D2 = 0.28, 0.34, 0.93
        hot = np.clip(1.0 - (r - D1) / (D2 - D1), 0.0, 1.0)
        ring = (np.clip((r - D1) / 0.06, 0.0, 1.0)
                * np.clip((D2 - r) / 0.18, 0.0, 1.0))
        dop = np.clip(1.0 + 0.75 * np.cos(th), 0.45, 1.8) ** 1.3
        front_m = np.clip(y / 0.05, 0.0, 1.0)
        back_m = 1.0 - front_m

        def to_img(cr, cg, cb, a, mask=None):
            if mask is not None:
                a = a * mask
            arr = (np.dstack([np.clip(cr, 0, 1), np.clip(cg, 0, 1),
                              np.clip(cb, 0, 1), np.clip(a, 0, 1)]) * 255).astype(np.uint8)
            return Image.fromarray(arr, "RGBA")

        fronts, backs = [], []
        for k in range(NF):
            ph = (k / float(NF)) * 2.0 * np.pi
            ta = th - ph
            sw = (0.62 + 0.30 * np.sin(2.0 * ta + r * 3.0)
                  + 0.16 * np.sin(5.0 * ta + r * 9.0)
                  + 0.07 * np.sin(11.0 * ta - r * 16.0)
                  + 0.04 * np.sin(23.0 * ta + r * 31.0))
            em = ring * (0.30 + 1.35 * hot ** 1.6) * np.clip(sw, 0.05, 2.0) * dop
            em = np.clip(em, 0.0, 1.6)
            cr = (0.55 + 0.50 * hot) * em
            cg = (0.20 + 0.62 * hot) * em
            cb = (0.06 + 0.50 * hot) * em
            a = em * 1.4

            def with_glow(im):
                try:
                    g = im.filter(ImageFilter.GaussianBlur(8))
                    g.alpha_composite(im)
                    return g
                except Exception:
                    return im
            fronts.append(with_glow(to_img(cr, cg, cb, a, front_m)))
            backs.append(with_glow(to_img(cr * 0.85, cg * 0.85, cb * 0.85, a, back_m)))

        halo = np.clip(1.0 - np.abs(rc - RH * 1.14) / 0.045, 0.0, 1.0) ** 1.5
        upper = np.clip((-y + 0.05) / 0.45, 0.0, 1.0)
        lower = np.clip((y - 0.10) / 0.50, 0.0, 1.0)
        hdop = np.clip(1.0 - 0.55 * np.cos(np.arctan2(y, x)), 0.45, 1.6)
        hem = halo * (0.10 + 1.05 * upper + 0.50 * lower) * hdop
        arc = to_img(0.98 * hem, 0.66 * hem, 0.36 * hem, hem)

        pr = np.clip(1.0 - np.abs(rc - RH * 1.02) / 0.020, 0.0, 1.0) ** 1.1
        rdop = np.clip(1.0 + 0.30 * x / np.maximum(rc, 1e-4), 0.65, 1.35)
        pr = pr * rdop
        ring_img = to_img(1.0 * pr, 0.82 * pr, 0.55 * pr, pr)

        zer = np.zeros_like(rc)
        sh_a = np.clip((RH - rc) / 0.012 + 1.0, 0.0, 1.0)
        shadow = to_img(zer, zer, zer, sh_a)

        edge = np.clip((0.985 - rc) / 0.012, 0.0, 1.0)
        stars = to_img(np.full_like(rc, 0.004), np.full_like(rc, 0.004),
                       np.full_like(rc, 0.008), edge)

        self._bhL = {"S": S, "NF": NF, "stars": stars, "front": fronts,
                     "back": backs, "arc": arc, "ring": ring_img, "shadow": shadow}

    def _render_bh(self, Wc, Hc, st, now):
        L = getattr(self, "_bhL", None)
        if L is None:
            return self._render_pil(Wc, Hc, st, now)
        S = L["S"]
        if st == "listening":
            spd, boost = 2.2, 1.35
        elif st == "thinking":
            spd, boost = 3.0, 0.55
        elif st == "speaking":
            spd, boost = 1.6, 1.25 + 0.30 * abs(np.sin(now / 160.0))
        else:
            spd, boost = 1.0, (0.55 if st == "loading" else 1.0)
        self._bh_ph = (self._bh_ph + 0.045 * spd) % L["NF"]
        i = int(self._bh_ph)
        j = (i + 1) % L["NF"]
        f = self._bh_ph - i
        front = Image.blend(L["front"][i], L["front"][j], f)
        back = Image.blend(L["back"][i], L["back"][j], f)
        if abs(boost - 1.0) > 0.03:
            front = ImageEnhance.Brightness(front).enhance(boost)
            back = ImageEnhance.Brightness(back).enhance(boost)
        img = L["stars"].copy()
        img.alpha_composite(back)
        img.alpha_composite(L["arc"])
        img.alpha_composite(L["shadow"])
        img.alpha_composite(L["ring"])
        img.alpha_composite(front)
        dr = ImageDraw.Draw(img)
        if st == "thinking":
            self._bh_star_a += 0.045
            px = S / 2.0 + np.cos(self._bh_star_a) * S * 0.30
            py = S / 2.0 + np.sin(self._bh_star_a) * S * 0.10 - S * 0.05
            gg = 0.7 + 0.3 * np.sin(now / 110.0)
            for rad, alp in ((9.0, 60), (5.0, 130), (2.4, 255)):
                dr.ellipse([px - rad, py - rad, px + rad, py + rad],
                           fill=(int(160 + 60 * gg), int(200 + 40 * gg), 255, int(alp * gg)))
            z = 1.45
            cw = S / z
            cxz = min(max(px, cw / 2.0), S - cw / 2.0)
            cyz = min(max(py, cw / 2.0), S - cw / 2.0)
            img = img.crop((int(cxz - cw / 2), int(cyz - cw / 2),
                            int(cxz + cw / 2), int(cyz + cw / 2)))
            img = img.resize((S, S), Image.LANCZOS)
            dr = ImageDraw.Draw(img)
        if self.ripple_on:
            self.ripple += 0.02
            if self.ripple >= 1.0:
                self.ripple_on = False
            else:
                rr = self.ripple * S * 0.62
                aa = int(max(0, (1 - self.ripple) * 180))
                dr.ellipse([S / 2 - rr, S / 2 - rr, S / 2 + rr, S / 2 + rr],
                           outline=(255, 150, 70, aa), width=2)
        D = max(2, int(min(Wc, Hc) * 0.97))
        img = img.resize((D, D), Image.LANCZOS)
        out = Image.new("RGBA", (Wc, Hc), (0, 0, 0, 0))
        out.alpha_composite(img, (int(Wc / 2 - D / 2), int(Hc / 2 - D / 2 - 12)))
        return ImageTk.PhotoImage(out)

    def _render_pil(self, Wc, Hc, st, now):
        SS = self.SS
        W, H = Wc * SS, Hc * SS
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        R = min(W, H) * 0.30
        focal = R * 2.6
        cx, cy = W / 2.0, H / 2.0 - 14 * SS
        if st != "thinking":
            disc_r = R * 1.55
            disc = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            dd = ImageDraw.Draw(disc)
            steps = 26
            for k in range(steps):
                t = k / (steps - 1.0)
                rr = disc_r * (1.0 - t)
                cc = (int(40 + 90 * t), int(15 + 35 * t), int(8 + 12 * t), 255)
                dd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=cc)
            try:
                disc = disc.filter(ImageFilter.GaussianBlur(SS * 1.2))
            except Exception:
                pass
            img.alpha_composite(disc)
            dr = ImageDraw.Draw(img)
        spin = 0.0015 if st == "thinking" else (0.006 if st == "listening" else 0.0035)
        self.ang += spin
        pulse = 1.0
        if st == "listening":
            pulse = 1 + 0.06 * np.sin(now / 130.0)
        elif st == "idle":
            pulse = 1 + 0.02 * np.sin(now / 700.0)
        tzoom = 2.3 if st == "thinking" else 1.0
        self.zoom += (tzoom - self.zoom) * 0.10
        zc = min(self.zoom, 1.5)
        sa, ca = np.sin(self.ang), np.cos(self.ang)
        ox = oy = 0.0
        if st == "thinking":
            spx, spy, spz = self.pts[self.sel]
            sx0 = spx * ca + spz * sa
            sz0 = -spx * sa + spz * ca
            sc0 = focal / (focal + sz0 * R)
            ox = sx0 * R * sc0
            oy = spy * R * sc0
        lo, hi = RAMPS.get(st, RAMPS["idle"])
        order = []
        for i in range(self.N):
            px0, py0, pz0 = self.pts[i]
            z = -px0 * sa + pz0 * ca
            order.append((z, i))
        order.sort()
        selX = selY = None
        selR = 2.0
        for z, i in order:
            px0, py0, pz0 = self.pts[i]
            x = px0 * ca + pz0 * sa
            y = py0
            sc = focal / (focal + z * R) * pulse
            X = cx + (x * R * sc - ox) * self.zoom
            Y = cy + (y * R * sc - oy) * self.zoom
            depth = (z + 1) / 2.0
            rad = (1.3 + 2.3 * depth) * zc * SS
            r = lo[0] + (hi[0] - lo[0]) * depth
            g = lo[1] + (hi[1] - lo[1]) * depth
            b = lo[2] + (hi[2] - lo[2]) * depth
            a = int(70 + 170 * depth)
            if st == "thinking" and i == self.sel:
                r, g, b, a = 235, 248, 255, 255
                rad *= 2.4
                selX, selY, selR = X, Y, rad
            elif st == "thinking":
                a = int(a * 0.4)
            gr = rad * 2.4
            dr.ellipse([X - gr, Y - gr, X + gr, Y + gr],
                       fill=(_clamp(r), _clamp(g), _clamp(b), int(a * 0.28)))
            dr.ellipse([X - rad, Y - rad, X + rad, Y + rad],
                       fill=(_clamp(r), _clamp(g), _clamp(b), _clamp(a)))
        if st == "thinking" and selX is not None:
            gg = 0.5 + 0.4 * np.sin(now / 110.0)
            rr = selR + (10 + 3 * np.sin(now / 110.0)) * SS
            dr.ellipse([selX - rr, selY - rr, selX + rr, selY + rr],
                       outline=(255, _clamp(170 * gg + 40), _clamp(40 * gg + 10), 220),
                       width=max(1, SS))
        if self.ripple_on:
            self.ripple += 0.02
            if self.ripple >= 1.0:
                self.ripple_on = False
            else:
                rr = self.ripple * R * 2.0
                aa = int(max(0, (1 - self.ripple) * 180))
                dr.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                           outline=(255, 140, 50, aa), width=max(1, int(2 * SS)))
        if SS != 1:
            img = img.resize((Wc, Hc), Image.LANCZOS)
        try:
            img = img.filter(ImageFilter.GaussianBlur(0.4))
        except Exception:
            pass
        return ImageTk.PhotoImage(img)

    def animate(self):
        # CRITICAL: this method MUST always reschedule itself, or the entire
        # display loop dies and the orb can never appear again on the next wake
        # (req_mode would be set to "expanded" but nothing ever applies it).
        # So the whole body is guarded and the after() reschedule is in finally.
        if self.stop:
            return
        delay = 33
        try:
            self._apply_mode()
            with self._lock:
                msgs = self.outbox
                self.outbox = []
            for m in msgs:
                txt = m["text"]
                if len(txt) > 66:
                    txt = txt[:63] + "..."
                self._hold = txt
                self._hold_until = time.time() + 4.0
            st = self.state
            if st != self.prev:
                if st == "thinking":
                    self.sel = int(np.random.randint(0, self.N))
                if st == "speaking":
                    self.ripple = 0.0
                    self.ripple_on = True
                self.prev = st
            if self.mode != "expanded":
                delay = 80
            else:
                Wc = max(self.cv.winfo_width(), 1)
                Hc = max(self.cv.winfo_height(), 1)
                now = time.time() * 1000.0
                if self.use_pil and Wc > 2 and Hc > 2:
                    try:
                        self._tkimg = self._render_bh(Wc, Hc, st, now)
                        self.cv.itemconfig(self.img_id, image=self._tkimg)
                        self.cv.coords(self.img_id, 0, 0)
                    except Exception as e:
                        self.use_pil = False
                        print("PIL render failed, fallback:", e)
                else:
                    self._render_canvas(Wc, Hc, st, now)
                self.cv.coords(self.status_id, Wc / 2.0, Hc - 40)
                self.cv.tag_raise(self.status_id)
                if self._hold_until > time.time():
                    self.cv.itemconfig(self.status_id, text=self._hold)
                else:
                    self.cv.itemconfig(self.status_id, text=self.status_text())
        except Exception as _e:
            print("[diag] animate frame error (continuing):", repr(_e), flush=True)
        finally:
            if not self.stop:
                try:
                    self.root.after(delay, self.animate)
                except Exception:
                    pass

    def _render_canvas(self, Wc, Hc, st, now):
        R = min(Wc, Hc) * 0.30
        focal = R * 2.6
        cx, cy = Wc / 2.0, Hc / 2.0 - 14
        spin = 0.0015 if st == "thinking" else (0.006 if st == "listening" else 0.0035)
        self.ang += spin
        pulse = 1.0
        if st == "listening":
            pulse = 1 + 0.06 * np.sin(now / 130.0)
        elif st == "idle":
            pulse = 1 + 0.02 * np.sin(now / 700.0)
        tzoom = 2.3 if st == "thinking" else 1.0
        self.zoom += (tzoom - self.zoom) * 0.10
        zc = min(self.zoom, 1.5)
        sa, ca = np.sin(self.ang), np.cos(self.ang)
        ox = oy = 0.0
        if st == "thinking":
            spx, spy, spz = self.pts[self.sel]
            sx0 = spx * ca + spz * sa
            sz0 = -spx * sa + spz * ca
            sc0 = focal / (focal + sz0 * R)
            ox = sx0 * R * sc0
            oy = spy * R * sc0
        lo, hi = RAMPS.get(st, RAMPS["idle"])
        selX, selY, selR = cx, cy, 2.0
        for i in range(self.N):
            px0, py0, pz0 = self.pts[i]
            x = px0 * ca + pz0 * sa
            z = -px0 * sa + pz0 * ca
            y = py0
            sc = focal / (focal + z * R) * pulse
            X = cx + (x * R * sc - ox) * self.zoom
            Y = cy + (y * R * sc - oy) * self.zoom
            depth = (z + 1) / 2.0
            rad = (1.3 + 2.2 * depth) * zc
            r = lo[0] + (hi[0] - lo[0]) * depth
            g = lo[1] + (hi[1] - lo[1]) * depth
            b = lo[2] + (hi[2] - lo[2]) * depth
            if st == "thinking" and i == self.sel:
                r, g, b = 235, 248, 255
                rad *= 2.4
                selX, selY, selR = X, Y, rad
            elif st == "thinking":
                r, g, b = r * 0.4, g * 0.4, b * 0.4
            self.cv.coords(self.items[i], X - rad, Y - rad, X + rad, Y + rad)
            self.cv.itemconfig(self.items[i], fill=_hexcol(r, g, b), outline="")
        if st == "thinking":
            gg = 0.5 + 0.4 * np.sin(now / 110.0)
            rr = selR + 9 + 3 * np.sin(now / 110.0)
            self.cv.coords(self.ring_id, selX - rr, selY - rr, selX + rr, selY + rr)
            self.cv.itemconfig(self.ring_id,
                               outline=_hexcol(230 * gg + 25, 245 * gg + 10, 255 * gg))
        else:
            self.cv.itemconfig(self.ring_id, outline="")
        if self.ripple_on:
            self.ripple += 0.02
            rr = self.ripple * R * 2.0
            if self.ripple >= 1.0:
                self.ripple_on = False
                self.cv.itemconfig(self.ripple_id, outline="")
            else:
                self.cv.coords(self.ripple_id, cx - rr, cy - rr, cx + rr, cy + rr)
                self.cv.itemconfig(self.ripple_id, outline="#46e0d6")
        else:
            self.cv.itemconfig(self.ripple_id, outline="")

def main():
    root = tk.Tk()
    App(root)
    try:
        import threading as _thr
        from pathlib import Path as _P
        def _wv_autostart():
            try:
                _fd = _P(__file__).resolve().parent
                _ensure_worldview_server(_fd, port=7777)
            except Exception as _e:
                print("[diag] worldview autostart failed:", repr(_e))
        _thr.Thread(target=_wv_autostart, daemon=True).start()
    except Exception as _e:
        print("[diag] worldview autostart not scheduled:", repr(_e))
    root.mainloop()

if __name__ == "__main__":
    main()
