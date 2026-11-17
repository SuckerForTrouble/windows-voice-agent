"""Small everyday things: sums, a coin, dice, a stopwatch, is the internet up, translate,
what a word means, the second screen, the keyboard language, restarting an app."""
import ast
import math
import operator
import random
import re
import subprocess
import sys
import threading
import time
from urllib.parse import quote

from . import apps, ui
from .actions import CTX, keys, log
from .engine import num

WINDOWS = sys.platform == "win32"


# ----------------------------------------------------------------- sums
_WORDS = [  # spoken maths -> symbols, longest first
    (r"\bto the power of\b|\bpower\b|\braised to\b", "**"), (r"\bmultiplied by\b|\btimes\b|\binto\b|\bx\b", "*"),
    (r"\bdivided by\b|\bover\b|\bby\b", "/"), (r"\bplus\b|\badd\b", "+"), (r"\bminus\b|\bless\b|\btake away\b", "-"),
    (r"\bmod\b|\bmodulo\b", "%"), (r"\bsquared\b", "**2"), (r"\bcubed\b", "**3"),
    (r"\bpoint\b", "."), (r"[×✕]", "*"), (r"÷", "/"),
]
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.Mod: operator.mod, ast.USub: operator.neg, ast.UAdd: operator.pos}


def _numbers(text):
    """Number words to digits: 'twenty five' -> '25' (digits stay)."""
    out, run = [], []

    def flush():
        if run:
            v = num(" ".join(run))
            out.append(str(v) if v is not None else " ".join(run))
            run.clear()
    for w in text.split():
        if re.fullmatch(r"[a-z]+", w) and w not in ("a", "an", "to", "too", "for", "won", "ate", "tree") and \
                num(w) is not None or (run and w == "and"):
            run.append(w)
        else:
            flush()
            out.append(w)
    flush()
    return " ".join(out)


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        a, b = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and (abs(b) > 100 or abs(a) > 1e6):
            raise ValueError("too big")
        return _OPS[type(node.op)](a, b)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("not a sum")


def sum_of(text):
    """'25 times 4' / 'fifteen percent of 200' / 'square root of 81' / '2 to the power of 10'
    -> (the sum written out, the answer), or None when it isn't one."""
    t = _numbers(text.lower().replace(",", "").strip().rstrip("?"))
    t = re.sub(r"\b(?:equals?|is|are|make|makes|gives)$", "", t).strip()
    root = re.fullmatch(r"(?:the )?square root of ([\d.]+)", t)
    if root:
        v = float(root.group(1))
        return f"√{root.group(1)}", math.sqrt(v)
    t = re.sub(r"([\d.]+) ?(?:percent|%) of ([\d.]+)", r"(\1/100*\2)", t)
    for pat, sym in _WORDS:
        t = re.sub(pat, f" {sym} ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if not re.fullmatch(r"[\d.+\-*/%() ]+", t) or not re.search(r"\d", t) or not re.search(r"[+\-*/%]", t):
        return None
    try:
        v = _eval(ast.parse(t, mode="eval").body)
    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError, TypeError):
        return None
    return t.replace("**", "^").replace("*", "×").replace("/", "÷"), v


def _fmt(v):
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e15:
        v = int(v)
    if isinstance(v, float):
        return f"{v:,.4f}".rstrip("0").rstrip(".")
    return f"{v:,}"


def calculate(text):
    got = sum_of(text)
    if not got:
        return ui.notify("That's not a sum I can do")
    shown, v = got
    ui.tell(f"{shown} = {_fmt(v)}", f"It's {_fmt(v).replace(',', '')}")


# ----------------------------------------------------------------- chance
def coin():
    side = random.choice(["Heads", "Tails"])
    ui.tell(f"🪙 {side}", side)


def dice(count=None):
    n = num(count) if count else 1
    n = max(1, min(6, n or 1))
    rolls = [random.randint(1, 6) for _ in range(n)]
    shown = " + ".join(map(str, rolls)) + (f" = {sum(rolls)}" if n > 1 else "")
    ui.tell(f"🎲 {shown}", f"You rolled {sum(rolls)}" if n > 1 else f"You rolled a {rolls[0]}")


def random_number(low=None, high=None):
    a, b = (num(low), num(high)) if low and high else (1, 100)
    if a is None or b is None:
        a, b = 1, 100
    a, b = min(a, b), max(a, b)
    v = random.randint(a, b)
    ui.tell(f"{v}  (between {a} and {b})", str(v))


def numbers_ok(low, high):
    return num(low) is not None and num(high) is not None


# ----------------------------------------------------------------- stopwatch
_watch = {"start": 0.0, "stopped": None}


def _elapsed():
    end = _watch["stopped"] or time.time()
    s = end - _watch["start"]
    m, s = divmod(int(s), 60)
    h, m = divmod(m, 60)
    return (f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"), (f"{h} hours {m} minutes" if h else
                                                              f"{m} minutes {s} seconds" if m else f"{s} seconds")


def stopwatch(what):
    """start / stop / status: one stopwatch, kept until the app closes."""
    if CTX.dry:
        return log(f"stopwatch {what}")
    if what == "start" or not _watch["start"]:
        _watch.update(start=time.time(), stopped=None)
        return ui.tell("⏱ Stopwatch started", "Started")
    if what == "stop":
        _watch["stopped"] = _watch["stopped"] or time.time()
        shown, said = _elapsed()
        return ui.tell(f"⏱ Stopped at {shown}", said)
    shown, said = _elapsed()
    ui.tell(f"⏱ {shown}" + (" (stopped)" if _watch["stopped"] else ""), said)


# ----------------------------------------------------------------- the internet
def internet():
    """Is it up, and the ping: three pings to Cloudflare's 1.1.1.1."""
    if CTX.dry:
        return log("ping 1.1.1.1")

    def go():
        argv = ["ping", "-n" if WINDOWS else "-c", "3", "1.1.1.1"]
        try:
            out = subprocess.run(argv, capture_output=True, text=True, timeout=12,
                                 creationflags=0x08000000 if WINDOWS else 0).stdout
        except (OSError, subprocess.TimeoutExpired):
            out = ""
        times = [float(x) for x in re.findall(r"time[=<]\s*([\d.]+)\s*ms", out)]
        if not times:
            return ui.tell("No internet: 1.1.1.1 didn't answer", "No internet")
        avg = sum(times) / len(times)
        verdict = "great" if avg < 40 else "fine" if avg < 90 else "slow"
        ui.tell(f"Online · ping {avg:.0f} ms ({verdict})", f"You're online, ping {avg:.0f} milliseconds")
    threading.Thread(target=go, daemon=True).start()


def speed_test():
    _url("https://fast.com")


# ----------------------------------------------------------------- words
LANGS = {"hindi": "hi", "english": "en", "punjabi": "pa", "urdu": "ur", "bengali": "bn", "bangla": "bn", "tamil": "ta",
         "telugu": "te", "marathi": "mr", "gujarati": "gu", "kannada": "kn", "malayalam": "ml", "spanish": "es",
         "french": "fr", "german": "de", "italian": "it", "portuguese": "pt", "russian": "ru", "japanese": "ja",
         "korean": "ko", "chinese": "zh-CN", "mandarin": "zh-CN", "arabic": "ar", "turkish": "tr", "dutch": "nl",
         "nepali": "ne", "indonesian": "id", "thai": "th", "vietnamese": "vi", "polish": "pl", "greek": "el"}


def _url(url):
    if CTX.dry:
        return log(f"open {url}" + (f" in {CTX.browser}" if CTX.browser else ""))
    apps.launch("url", url)


def translate(text, lang):
    _url(f"https://translate.google.com/?sl=auto&tl={LANGS[lang.lower()]}&text={quote(text)}&op=translate")


def lang_ok(text, lang):
    return lang.lower() in LANGS and bool(text.strip())


def define(word):
    from .actions import web
    web(f"define {word}", "google")


# ----------------------------------------------------------------- the PC
DISPLAY = {"extend": "/extend", "duplicate": "/clone", "mirror": "/clone", "clone": "/clone", "copy": "/clone",
           "second": "/external", "external": "/external", "other": "/external", "monitor": "/external",
           "tv": "/external", "pc": "/internal", "laptop": "/internal", "first": "/internal", "main": "/internal",
           "computer": "/internal", "this": "/internal"}


def display(mode):
    """Windows' Win+P choices: extend, duplicate, second screen only, PC screen only."""
    arg = DISPLAY[mode]
    if CTX.dry:
        return log(f"DisplaySwitch.exe {arg}")
    import os
    exe = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "DisplaySwitch.exe")
    try:
        subprocess.Popen([exe, arg], creationflags=0x08000000)
    except OSError:
        keys("win+p")


def keyboard_language():
    keys("win+space")


def restart_app(name):
    """Quit it completely, wait for it to go, open it again (a stuck Discord, a Spotify that lost sound)."""
    from . import actions as a
    if CTX.dry:
        log(f"quit {name}")
        return log(f"open {name}")
    a.quit_app(name)
    for _ in range(40):
        time.sleep(0.25)
        if not a.find_target(name):
            break
    time.sleep(0.8)
    a.open_app(name)
