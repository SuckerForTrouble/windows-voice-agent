"""Always listening (opt-in, tray → Optional features): no key needed, say the call word
first ("Jarvis, open Spotify").

The mic stays open. A light voice detector (loudness against the room's own noise
level) cuts out each spoken phrase; only phrases go to the speech model. A phrase
that doesn't start with the call word is thrown away: it is never shown, logged or
written to the history. The call word alone ("Jarvis…") waits a few seconds for
the command, like a smart speaker. Never with a cloud model: that would send
everything said near the mic to the cloud."""
import array
import difflib
import math
import queue
import re
import threading
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
    Speech = louder than 3x the room's noise (learnt while nobody talks) and at least 400."""

    def __init__(self, start_ms=120, end_ms=700, preroll_ms=300, min_ms=450, max_s=12):
        ms = 1000 * FRAME / RATE
        self.start_n, self.end_n = round(start_ms / ms), round(end_ms / ms)
        self.min_n, self.max_n = round(min_ms / ms), round(max_s * 1000 / ms)
        self.pre = deque(maxlen=round(preroll_ms / ms))
        self.noise = 300.0
        self.active = False
        self.buf = []
        self.run = 0          # speech frames in a row (before) / silent frames in a row (during)

    def drop(self):
        """Forget a phrase in progress (push-to-talk took over); keeps the learnt noise level."""
        self.active, self.buf, self.run = False, [], 0
        self.pre.clear()

    def feed(self, frame):
        rms = level(frame)
        speech = rms > max(self.noise * 3.0, 400.0)
        if not self.active:
            if not speech:
                self.noise = 0.97 * self.noise + 0.03 * min(rms, 4000.0)
            self.pre.append(frame)
            self.run = self.run + 1 if speech else 0
            if self.run >= self.start_n:  # someone started talking: keep the bit just before too
                self.active, self.buf, self.run = True, list(self.pre), 0
            return None
        self.buf.append(frame)
        self.run = 0 if speech else self.run + 1
        if self.run >= self.end_n or len(self.buf) >= self.max_n:
            phrase, n = b"".join(self.buf), len(self.buf) - self.run
            self.active, self.buf, self.run = False, [], 0
            self.pre.clear()
            return phrase if n >= self.min_n else None
        return None


def call_word_ok(word):
    """None if it can be the call word, else why not."""
    w = " ".join(re.findall(r"[a-z']+", word.lower()))
    if not w or len(w.split()) > 3:
        return "one to three words, letters only"
    if len(w.replace(" ", "")) < 4:
        return "too short: it would go off all the time"
    if w in TOO_COMMON:
        return "too common a word: it would go off in normal talk"
    return None


def strip_call(text, word):
    """The command after the call word ('Jarvis, open Spotify' -> 'open Spotify'), '' for
    the call word alone, None if the phrase doesn't start with it. Near misses count
    ('Jarvus'), fillers before it are skipped ('hey jarvis…'); the command keeps its capitals."""
    word = (word or "computer").strip().lower()
    if word == "computer":  # the built-in one knows its mishearings ("commuter", "compute her"…)
        m = re.match(r"\W*(?:(?:hey|hi|ok|okay|yo|so)\W+)*" + WAKE + r"\W*", text, re.I)
        return text[m.end():].strip() if m else None
    want = " ".join(re.findall(r"[a-z']+", word))
    k = len(want.split())
    toks = [(m.group(0).lower(), m.end()) for m in re.finditer(r"[A-Za-z0-9']+", text)]
    i = 0
    while i < len(toks) and toks[i][0] in FILLER and toks[i][0] not in want.split():
        i += 1
    if len(toks) < i + k:
        return None
    said = " ".join(t for t, _ in toks[i:i + k])
    if said != want and difflib.SequenceMatcher(None, said, want).ratio() < 0.75:
        return None
    return text[toks[i + k - 1][1]:].lstrip(" ,.;:!?-").strip()


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
