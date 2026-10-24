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
