"""Routing tests: every example phrase lands on its command, and every command
runs cleanly in a dry run. Runs anywhere (Linux too): nothing touches Windows.

    python tests/test_routing.py        (or: python -m pytest tests)
"""
import collections
import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("WVA_DATA", os.path.join(os.path.dirname(__file__), ".data"))

from wva import engine, rules  # noqa: E402,F401  (rules registers the commands)
from wva.examples import CASES  # noqa: E402

SRC = os.path.join(os.path.dirname(__file__), "..", "wva")


def route(text, front=""):
    engine.CTX.dry, engine.CTX.raw, engine.CTX.front, engine.CTX.last_target = True, text, front, None
    steps, _ = engine.plan(text, woke=True)
    return steps


def test_no_duplicate_functions():
    # A second def of the same name silently replaces the first (it powered Bluetooth
    # off instead of playing a song on the Linux agent once).
    for f in os.listdir(SRC):
        if f.endswith(".py"):
            names = re.findall(r"^def (\w+)", open(os.path.join(SRC, f), encoding="utf-8").read(), re.M)
            dups = [n for n, c in collections.Counter(names).items() if c > 1]
            assert not dups, f"{f}: duplicate functions {dups}"


def test_examples_route():
    bad = []
    for case in CASES:
        text, want, front = (*case, "")[:3]
        got = [r.say for r, _, _ in route(text, front)]
        if got != want:
            bad.append(f"{text!r} (front={front!r}): want {want}, got {got}")
    assert not bad, "\n".join(bad)


def test_examples_run_dry():
    """Each command's action runs in a dry run without blowing up."""
    out = io.StringIO()
    engine.CTX.log = lambda m: out.write(m + "\n")
    bad = []
    try:
        for case in CASES:
            text, _, front = (*case, "")[:3]
            for r, groups, _ in route(text, front):
                try:
                    r.fn(*groups)
                except Exception as e:  # noqa: BLE001
                    bad.append(f"{text!r} -> {r.say}: {type(e).__name__}: {e}")
    finally:
        engine.CTX.log = print
    assert not bad, "\n".join(bad)


def test_every_rule_has_an_example():
    covered = {s for case in CASES for s in case[1]}
    state_only = {"stop scrolling"}  # needs a doom scroll running
    missing = [r.say for r in engine.RULES if r.say not in covered and r.desc and r.say not in state_only]
    assert not missing, f"rules without an example: {missing}"


def test_tuning_lines():
    from wva import tuning
    assert tuning.check("heard", "the", "a")  # too common
    assert tuning.check("say", "chuck the volume up", "volume up") is None
    assert tuning.check("say", "do my homework", "make me a sandwich")  # not a command
    engine.TUNE_SAY["chuck the volume up"] = "volume up"
    try:
        assert [r.say for r, _, _ in route("chuck the volume up")] == ["volume up | down"]
    finally:
        engine.TUNE_SAY.clear()


def test_mishearings():
    """What the recognisers (Parakeet especially, which takes no prompt) actually wrote."""
    for text, want in [("Plus Discord from the tray.", ["quit <app> completely"]),
                       ("Clothes chrome", ["close <app>"]),
                       ("What's using my REM?", ["what is using RAM"]),
                       ("REM", ["ram"]),
                       ("Watch Breaking Bad Season 2 Episode 3 on Stremeo.", ["watch <movie | show> on Stremio"]),
                       ("open stremyo", ["open <app | game | site | folder | settings page>"]),
                       ("plus one for that idea", [])]:
        got = [r.say for r, _, _ in route(text)]
        assert got == want, f"{text!r}: want {want}, got {got}"


def test_guide_starters_route():
    """The 'Try these first' phrases at the top of the voice guide."""
    from wva.guide import STARTERS
    bad = [t for _, t in STARTERS if not route(t)]
    assert not bad, f"starter phrases that don't route: {bad}"


def _frames(pcm):
    from wva.listen import FRAME
    return [pcm[i:i + FRAME * 2] for i in range(0, len(pcm) - FRAME * 2 + 1, FRAME * 2)]


def _room(seconds, amp=120, seed=1):
    import array
    import random
    r = random.Random(seed)
    return array.array("h", (int(r.gauss(0, amp)) for _ in range(int(16000 * seconds)))).tobytes()


def test_always_listening_detector():
    """The voice detector on a real recording (tests/data/open_spotify.wav) in room noise."""
    import array
    import math
    import wave

    from wva.listen import Segmenter
    with wave.open(os.path.join(os.path.dirname(__file__), "data", "open_spotify.wav")) as w:
        speech = w.readframes(w.getnframes())

    def phrases(pcm):
        seg = Segmenter()
        return [p for p in (seg.feed(f) for f in _frames(pcm)) if p]

    assert phrases(_room(5)) == [], "room noise alone"
    hum = array.array("h", (int(900 * math.sin(i / 16000 * 2 * math.pi * 50)) for i in range(16000 * 6))).tobytes()
    assert phrases(_room(1) + hum) == [], "a steady hum (fan, AC) learnt as the room's noise"
    one = phrases(_room(1.5) + speech + _room(1.5, seed=2))
    assert len(one) == 1, f"one sentence -> {len(one)} phrases"
    got, want = len(one[0]) / 32000, len(speech) / 32000
    assert want - 0.3 < got < want + 1.2, f"phrase is {got:.2f}s, the sentence {want:.2f}s"
    two = phrases(_room(1) + speech + _room(1.2, seed=3) + speech + _room(1.5, seed=4))
    assert len(two) == 2, f"two sentences with a pause -> {len(two)} phrases"


def test_call_word():
    from wva.listen import call_word_ok, strip_call
    cases = [("Jarvis, open Spotify.", "jarvis", "open Spotify."), ("Hey Jarvis open spotify", "jarvis", "open spotify"),
             ("Jarvus, volume up", "jarvis", "volume up"), ("open spotify", "jarvis", None),
             ("I told Jarvis to stop", "jarvis", None), ("Jarvis.", "jarvis", ""), ("Jarvis", "jarvis", ""),
             ("Computer, volume up", "computer", "volume up"), ("Commuter volume up", "computer", "volume up"),
             ("Okay computer, next song", "computer", "next song"), ("the computer is slow", "computer", None),
             ("Hey Friday, what time is it", "hey friday", ", what time is it".lstrip(" ,")),
             ("Billa, close discord", "billa", "close discord")]
    for text, word, want in cases:
        got = strip_call(text, word)
        assert got == want, f"{text!r} with {word!r}: want {want!r}, got {got!r}"
    assert call_word_ok("Jarvis") is None and call_word_ok("hey friday") is None
    assert call_word_ok("play") and call_word_ok("bob") and call_word_ok("one two three four")


def test_whisper_tidy():
    """What the trimmed window made Best write (2026-10-25), and what must stay as it is."""
    from wva import config, stt
    config.load()
    assert stt._tidy("Next song. Next song.") == "Next song."
    assert stt._tidy("What's using my RAM? What's using my RAM?") == "What's using my RAM?"
    assert stt._tidy("Open YouTube, open YouTube, Open YouTube,") == "Open YouTube"
    assert stt._tidy("Open YouTube and search for lofi beats.") == "Open YouTube and search for lofi beats."
    assert stt._tidy("New tab, type hello, press enter") == "New tab, type hello, press enter"
    assert stt._tidy("Thank you.") == ""
    assert stt.audio_ctx(2.5) == 512 and stt.audio_ctx(20) == 1050 and stt.audio_ctx(29) == 0
    assert stt.paths.SAMPLE.exists(), "the setup check's sample sentence"


def test_chain_shortcut():
    """'open X and search Y' goes straight to X's search; other chains are left alone."""
    from wva.actions import streamline
    assert [r.say for r, _, _ in streamline(route("open youtube and search for lofi beats"))] == ["search <text>"]
    assert engine.CTX.last_target == "youtube"
    assert [r.say for r, _, _ in streamline(route("open stremio and search interstellar"))] == ["search <text>"]
    assert len(streamline(route("New tab, type hello world, press enter"))) == 3
    assert len(streamline(route("open notepad and type hello"))) == 2


def test_stremio_parse():
    from wva.extras import parse_show
    assert parse_show("breaking bad season 2 episode 3") == ("breaking bad", 2, 3)
    assert parse_show("season 4 of the office") == ("the office", 4, None)
    assert parse_show("the movie interstellar") == ("interstellar", None, None)


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"ok    {name}")
            except AssertionError as e:
                failed += 1
                print(f"FAIL  {name}\n{e}\n")
    sys.exit(1 if failed else 0)
