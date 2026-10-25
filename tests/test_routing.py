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
    state_only = {"stop scrolling", "the second one"}  # need a doom scroll running / a list on the pill
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
    assert stt._tidy("Open Spotify and Search for Interstellar. Open Spotify and Search for Interstellar. Open") == \
        "Open Spotify and Search for Interstellar."  # the tiny model in CI, 2026-10-25
    assert stt._tidy("Close the tab. Close Discord.") == "Close the tab. Close Discord."  # two different things stay
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


def test_file_names():
    """Misspelt, shortened and sound-alike file names: what friends will say (2026-10-25)."""
    import time

    from wva import files as fl
    now = time.time()
    names = ["Documents/budget_2026_final.xlsx", "Documents/resume.pdf", "Documents/School/assgnmt_chem.docx",
             "Documents/School/Physics Assignment 4.docx", "Documents/School/Physics Assignment 3.docx",
             "Downloads/setup.exe", "Pictures/IMG_2041.jpg", "Documents/MyResumeOld.docx", "Documents/homework.docx",
             "Documents/Bio notes.txt", "Desktop/Minecraft Mods.zip", "Documents/project-management-plan.pdf",
             "Documents/photos list.txt"]
    found = [(f"C:/Users/x/{n}", now - i * 86400 * 5, False) for i, n in enumerate(names)]
    for query, want in [("budjet", "budget_2026_final.xlsx"), ("rezume", "resume.pdf"),
                        ("chemistry assignment", "assgnmt_chem.docx"), ("fizzics assignment 4", "Physics Assignment 4.docx"),
                        ("physics assignment three", "Physics Assignment 3.docx"), ("home work", "homework.docx"),
                        ("biology notes", "Bio notes.txt"), ("resume pdf", "resume.pdf"), ("my old resume", "MyResumeOld.docx"),
                        ("project management", "project-management-plan.pdf"), ("fotos list", "photos list.txt")]:
        r = fl.rank(query, found=found)
        got = r[0][2].split("/")[-1] if r else None
        assert got == want and fl.decide(r) == "open", f"{query!r}: want {want}, got {got} ({fl.decide(r)})"
    r = fl.rank("fizzics assignment", found=found)  # two fit as well: it asks
    assert fl.decide(r) == "pick" and {p.split("/")[-1] for _, _, p in r[:2]} == {"Physics Assignment 4.docx", "Physics Assignment 3.docx"}
    assert fl.decide(fl.rank("zzz qqq", found=found)) == "none"
    two = found + [("C:/Users/x/Documents/budget_2025.xlsx", now - 86400 * 30, False)]
    assert fl.decide(fl.rank("budget", found=two)) == "pick"
    fl.remember("the budget", "C:/Users/x/Documents/budget_2025.xlsx")  # picked from the list once
    try:
        r = fl.rank("budget", found=two)
        assert fl.decide(r) == "open" and r[0][2].endswith("budget_2025.xlsx")
    finally:
        fl.PICKS.unlink()


def test_pick_from_list():
    import time

    from wva import choices
    assert [r.say for r, _, _ in route("the second one")] != ["the second one"], "no list, no pick"
    choices.PENDING.update(items=[("a", "", 1), ("b", "", 2), ("c", "", 3)], act=print, until=time.time() + 20)
    try:
        for text in ("the second one", "number two", "open the 3rd one", "the last one", "two", "first", "pick number 3"):
            got = [r.say for r, _, _ in route(text)]
            assert got == ["the second one"], f"{text!r} -> {got}"
    finally:
        choices.PENDING.update(items=[], act=None, until=0.0)


def test_shortcut_target():
    """A Windows shortcut's target, from a .lnk built the way MS-SHLLINK lays it out
    (CI also reads one that Windows itself made)."""
    import struct
    import tempfile

    from wva import files as fl

    def lnk(target, unicode):
        vol = struct.pack("<4I", 17, 3, 0x1234, 16) + b"\0"
        head = 0x24 if unicode else 0x1C
        ansi = target.encode("cp1252") + b"\0"
        body = vol + ansi + b"\0"  # the local base path, then an empty common path suffix
        offs = [head + len(vol), head + len(vol) + len(ansi)]
        if unicode:
            wide = target.encode("utf-16-le") + b"\0\0"
            offs += [head + len(body), head + len(body) + len(wide)]
            body += wide + b"\0\0"
        info = struct.pack("<7I", head + len(body), head, 1, head, offs[0], 0, offs[1])
        if unicode:
            info += struct.pack("<2I", offs[2], offs[3])
        flags = 0x2 | 0x80 | 0x1
        idlist = struct.pack("<H", 4) + b"\x02\0\0\0"
        return struct.pack("<I16sI", 0x4C, b"\x01\x14\x02" + b"\0" * 13, flags) + b"\0" * 52 + idlist + info + body
    with tempfile.TemporaryDirectory() as d:
        for unicode in (False, True):
            p = os.path.join(d, f"t{unicode}.lnk")
            with open(p, "wb") as f:
                f.write(lnk(r"C:\Users\x\Documents\budget 2026.xlsx", unicode))
            assert fl.lnk_target(p) == r"C:\Users\x\Documents\budget 2026.xlsx", (unicode, fl.lnk_target(p))
        with open(os.path.join(d, "junk.lnk"), "wb") as f:
            f.write(b"not a shortcut")
        assert fl.lnk_target(os.path.join(d, "junk.lnk")) is None


def test_sound_devices():
    """Spoken names against real-looking Windows device names; Bluetooth battery lines."""
    from wva import audio, system
    devs = [("a", "Speakers (Realtek(R) Audio)", True), ("b", "Headphones (2- HyperX Cloud II Wireless)", False),
            ("c", "LG ULTRAGEAR (NVIDIA High Definition Audio)", False), ("d", "Headset Earphone (Galaxy Buds2)", False)]
    for said, want in [("headphones", "b"), ("my hyperx", "b"), ("the speakers", "a"), ("the tv", "c"), ("monitor", "c"),
                       ("galaxy buds", "d"), ("my earbuds", "d"), ("laptop", "a"), ("toaster", None)]:
        got = audio.best(said, devs)
        assert (got[0] if got else None) == want, f"{said!r}: want {want}, got {got}"
    assert audio.device_like("my headphones") and audio.device_like("the tv")
    assert not audio.device_like("the second monitor") and not audio.device_like("chrome")
    lines = "Galaxy Buds2 Hands-Free AG\t80\nGalaxy Buds2 Avrcp Transport\t85\nXbox Wireless Controller\t40\nnoise\t\n"
    assert system.bt_batteries(lines) == {"Galaxy Buds2": 80, "Xbox Wireless Controller": 40}


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
