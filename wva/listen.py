"""Always listening (opt-in, tray → Always listening): no key needed, say the call word
first ("Angel, open Spotify"; several call words work, comma-separated).

The mic stays open. A light voice detector (loudness against the room's own noise
level) cuts out each spoken phrase; only phrases go to the speech model. A phrase
that doesn't start with the call word (or have a sentence that does, see hear()) is
thrown away: it is never shown, logged or written to the history. The call word
alone ("Angel…") waits a few seconds for the command, like a smart speaker. Never
with a cloud model: that would send everything said near the mic to the cloud.

The Linux voice agent's listener is the model here (same detector, same quiet-mic
floor, same louder()); it answers the call word at once, so this one should too."""
import array
import difflib
import math
import queue
import re
import threading
import time
from collections import deque

from .engine import WAKE

RATE = 16000
FRAME = 480             # 30 ms
FILLER = {"hey", "hi", "ok", "okay", "yo", "so", "um", "uh", "hmm", "oh"}
# Words that come up in normal talk too often to be a call word.
TOO_COMMON = {"hey", "ok", "okay", "yes", "no", "play", "open", "stop", "start", "go", "the", "hello", "hi",
              "please", "thanks", "close", "next", "volume", "music", "phone", "game", "bro", "yaar"}


def level(frame):
    """Loudness (RMS) of 16-bit samples, every 3rd sample: cheap enough for 33 frames a second."""
    a = array.array("h", frame)[::3]
    return math.sqrt(sum(x * x for x in a) / len(a)) if a else 0.0


class Segmenter:
    """Feed it 30 ms frames; it returns each spoken phrase (bytes) once the speaker pauses.
    Speech = louder than 3x the room's noise (learnt while nobody talks) and a floor: 400 for
    a mic with real room noise, down to 40 for a quiet or gated one (a laptop's array mic, a
    headset with noise removal: silence near zero, a voice of only ~150). A fixed 400 missed
    those voices outright: the Linux agent hit it first (2026-11-01) and this is its fix."""

    def __init__(self, start_ms=120, end_ms=700, preroll_ms=300, min_ms=450, max_s=12, keep_ms=300):
        ms = 1000 * FRAME / RATE
        self.start_n, self.end_n = round(start_ms / ms), round(end_ms / ms)
        self.min_n, self.max_n = round(min_ms / ms), round(max_s * 1000 / ms)
        self.keep_n = round(keep_ms / ms)  # silence kept after the last word (its tail), the rest isn't sent
        self.pre = deque(maxlen=round(preroll_ms / ms))
        self.noise = 300.0
        self.active = False
        self.buf = []
        self.run = 0          # speech frames in a row (before) / silent frames in a row (during)
        self.streak = 0       # loud frames in a row

    def floor(self):
        return max(self.noise * 3.0, min(400.0, max(40.0, self.noise * 6.0)))

    def drop(self):
        """Forget a phrase in progress (push-to-talk took over); keeps the learnt noise level."""
        self.active, self.buf, self.run, self.streak = False, [], 0, 0
        self.pre.clear()

    def feed(self, frame):
        rms = level(frame)
        speech = rms > self.floor()
        if not self.active:
            if not speech:  # learn the room: down fast (a gated mic is silent at once), up slowly
                k = 0.15 if rms < self.noise else 0.03
                self.noise = (1 - k) * self.noise + k * min(rms, 4000.0)
            self.pre.append(frame)
            self.run = self.run + 1 if speech else 0
            if self.run >= self.start_n:  # someone started talking: keep the bit just before too
                self.active, self.buf, self.run, self.streak = True, list(self.pre), 0, self.run
            return None
        self.buf.append(frame)
        # A key or mouse click is loud for one or two frames; a spoken sound lasts 90 ms and more.
        # Clicks don't keep a phrase going, so typing while you talk doesn't hold the command back.
        self.streak = self.streak + 1 if speech else 0
        self.run = 0 if self.streak >= 3 else self.run + 1
        if self.run >= self.end_n or len(self.buf) >= self.max_n:
            n = len(self.buf) - self.run
            phrase = b"".join(self.buf[:len(self.buf) - max(0, self.run - self.keep_n)])
            self.active, self.buf, self.run, self.streak = False, [], 0, 0
            self.pre.clear()
            return phrase if n >= self.min_n else None
        return None


def louder(pcm, target=16000, most=30.0):
    """A quiet phrase raised to a normal level (peak ~16000) for the model; loud ones unchanged."""
    a = array.array("h", pcm)
    peak = max((abs(v) for v in a), default=0)
    if not peak or peak >= target / 2:
        return pcm
    g = min(most, target / peak)
    return array.array("h", (max(-32767, min(32767, int(v * g))) for v in a)).tobytes()


class Inbox:
    """Phrases waiting for the speech model. When they pile up (a slow model, a long
    command) the oldest go, never the newest: what you just said is what matters.
    (Before 0.1.13 the newest was the one dropped, call word and all.)"""

    def __init__(self, size=3):
        self.items = deque(maxlen=size)
        self.wake = threading.Event()
        self.dropped = 0

    def put(self, item):
        if len(self.items) == self.items.maxlen:
            self.dropped += 1
        self.items.append(item)
        self.wake.set()

    def get(self, timeout=None):
        """The oldest waiting phrase, or None after timeout."""
        end = None if timeout is None else time.time() + timeout
        while True:
            try:
                return self.items.popleft()
            except IndexError:
                pass
            left = None if end is None else end - time.time()
            if left is not None and left <= 0:
                return None
            self.wake.clear()
            if self.items:
                continue
            self.wake.wait(left)


# What the recognisers write for a call word, beyond near spellings (those always count)
HEARD_AS = {
    "angel": {"angle", "angela", "angelo", "angels", "angel's", "angle's", "anjel", "anjal", "angil", "angell", "engel",
              "ainjel", "aangel", "anjelo", "angie", "angelina", "angeli", "anchal", "and gel", "an gel",
              "and jel", "an jel", "ann gel", "in gel", "ain gel"},
}


def call_words(setting):
    """'angel, jarvis' -> ['angel', 'jarvis'] (the setting can hold several, comma-separated)."""
    out = []
    for w in (setting or "").split(","):
        w = " ".join(re.findall(r"[a-z']+", w.lower()))
        if w and w not in out:
            out.append(w)
    return out or ["angel"]


def call_word_ok(word):
    """None if it can be the call word (or every one of several, comma-separated), else why not."""
    for w in [" ".join(re.findall(r"[a-z']+", p.lower())) for p in (word or "").split(",")] or [""]:
        if not w or len(w.split()) > 3:
            return "one to three words each, letters only (several: separate them with commas)"
        if len(w.replace(" ", "")) < 4:
            return f"“{w}” is too short: it would go off all the time"
        if w in TOO_COMMON:
            return f"“{w}” is too common a word: it would go off in normal talk"
    return None


def _strip_one(text, word):
    if word == "computer":  # the built-in one knows its mishearings ("commuter", "compute her"…)
        m = re.match(r"\W*(?:(?:hey|hi|ok|okay|yo|so)\W+)*" + WAKE + r"\W*", text, re.I)
        return text[m.end():].strip() if m else None
    want = word.split()
    k = len(want)
    toks = [(m.group(0).lower(), m.end()) for m in re.finditer(r"[A-Za-z0-9']+", text)]
    heard = HEARD_AS.get(word, set())

    def fits(n):  # the next n words say the call word
        said = " ".join(t for t, _ in toks[i:i + n])
        return said == word or said in heard or (
            n == k and difflib.SequenceMatcher(None, said, word).ratio() >= 0.75) or (
            n == k + 1 and "".join(t for t, _ in toks[i:i + n]) == word.replace(" ", ""))  # "an gel"
    i, skipped = 0, 0
    while i < len(toks) and skipped < 4:
        t = toks[i][0]
        if fits(k) or fits(k + 1):
            break
        # fillers, and stutters: the start of the call word said first ("a-angel", "an angel", "ang angel")
        if (t in FILLER and t not in want) or (want[0].startswith(t) and t != want[0]):
            i, skipped = i + 1, skipped + 1
            continue
        return None
    for n in (k, k + 1, k + 2):
        if i + n <= len(toks) and fits(n):
            end = i + n
            while end + k <= len(toks) and " ".join(t for t, _ in toks[end:end + k]) == word:
                end += k  # "angel angel, open spotify"
            return text[toks[end - 1][1]:].lstrip(" ,.;:!?-").strip()
    return None


def strip_call(text, word):
    """The command after the call word ('Jarvis, open Spotify' -> 'open Spotify'), '' for
    the call word alone, None if the phrase doesn't start with one. word can hold several,
    comma-separated ('angel, jarvis'). Near misses count ('Jarvus', 'Angela'), fillers and
    stutters before it are skipped ('hey jarvis…', 'a-angel…'); the command keeps its capitals."""
    for w in call_words(word or "angel"):
        rest = _strip_one(text, w)
        if rest is not None:
            return rest
    return None


def _sounds_like(said, word):
    """'anjali' / 'ainjel' for 'angel': the same sound code (files.sound), first letter alike."""
    from .files import sound
    a, b = said.replace(" ", ""), word.replace(" ", "")
    return len(a) >= 3 and a[:1] in b[:1] + ("e" if b[:1] == "a" else "a" if b[:1] == "e" else "") and sound(a) == sound(b)


def _near_start(text, word):
    """The command after a call word that only sounds like it ('Anjali, open Spotify'), or None."""
    toks = [(m.group(0).lower(), m.end()) for m in re.finditer(r"[A-Za-z0-9']+", text)]
    k = len(word.split())
    for i in range(min(3, len(toks))):
        for n in (k, k + 1):
            if i + n <= len(toks) and _sounds_like(" ".join(t for t, _ in toks[i:i + n]), word):
                return text[toks[i + n - 1][1]:].lstrip(" ,.;:!?-").strip()
        if toks[i][0] not in FILLER:
            return None
    return None


SENTENCE = re.compile(r"(?<=[.?!])\s+")


def _inner(rest, word):
    """'pause the music. Angel, take a screenshot.' -> 'pause the music. take a screenshot.'
    (two commands said in one breath, the call word before each)."""
    parts = SENTENCE.split(rest)
    out = [parts[0]] + [(r if (r := strip_call(p, word)) else p) for p in parts[1:]]
    return " ".join(p for p in out if p)


def hear(text, word):
    """What the open mic heard: None (not for us: dropped unseen), or (command, sure).
    sure: it starts with the call word (strip_call); ('', True) is the call word alone.
    Not sure, so only a phrase that is a command gets through (the app checks that):
    a call word that only sounds like it ('Anjali, …'), or a later sentence that starts
    with the call word ('Okay, wait. Angel, open Spotify.': you were still talking
    when you called it, so the two ran together into one phrase)."""
    if not text or not text.strip():
        return None
    words = call_words(word or "angel")
    for w in words:
        rest = strip_call(text, w)
        if rest is not None:
            return _inner(rest, w), True
    for w in words:
        rest = _near_start(text, w)
        if rest:
            return _inner(rest, w), False
    for p in SENTENCE.split(text.strip())[1:]:
        for w in words:
            rest = strip_call(p, w)
            if rest is None:
                rest = _near_start(p, w)
            if rest:
                tail = text.strip()[text.strip().index(p) + len(p):]
                return _inner((rest + " " + tail).strip(), w), False
    return None


def why_not(text, word):
    """For the log when a phrase is let go: how close its first words came to the call word,
    as a number (never the words): 'nearest 0.62'. Tells a misheard call word from talk."""
    toks = re.findall(r"[a-z']+", (text or "").lower())[:4]
    best = 0.0
    for w in call_words(word or "angel"):
        k = len(w.split())
        for i in range(len(toks)):
            for n in (k, k + 1):
                said = " ".join(toks[i:i + n])
                best = max(best, difflib.SequenceMatcher(None, said, w).ratio(), difflib.SequenceMatcher(None, said.replace(" ", ""), w.replace(" ", "")).ratio())
    return round(best, 2)


class Listener:
    """The open mic: frames -> Segmenter -> on_phrase(pcm). paused() is checked on every
    frame (true while push-to-talk is recording, so the two don't both hear you)."""

    def __init__(self, on_phrase, paused=lambda: False):
        self.on_phrase, self.paused = on_phrase, paused
        self.stream = None
        self.frames = queue.Queue(maxsize=400)  # ~12 s; dropped beyond that, never piled up
        self.running = False

    def start(self, mic=""):
        import sounddevice as sd
        dev = None
        if mic:
            for i, d in enumerate(sd.query_devices()):
                if d["max_input_channels"] > 0 and mic.lower() in d["name"].lower():
                    dev = i
                    break

        def cb(data, n, t, status):
            try:
                self.frames.put_nowait(bytes(data))
            except queue.Full:
                pass
        self.stream = sd.RawInputStream(samplerate=RATE, channels=1, dtype="int16", device=dev, callback=cb,
                                        blocksize=FRAME)
        self.stream.start()
        self.running = True
        threading.Thread(target=self._loop, daemon=True, name="listen").start()

    def _loop(self):
        seg = Segmenter()
        while self.running:
            try:
                frame = self.frames.get(timeout=0.5)
            except queue.Empty:
                continue
            if self.paused():
                seg.drop()
                continue
            phrase = seg.feed(frame)
            if phrase:
                self.on_phrase(phrase)

    def stop(self):
        self.running = False
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
