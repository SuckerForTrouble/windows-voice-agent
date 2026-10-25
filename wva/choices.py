"""A short numbered list on the pill ("Which one?") and "the second one" to answer it:
files that fit about as well, your sound outputs."""
import re
import time

from . import ui
from .engine import CTX, num

SECONDS = 25   # how long "the second one" works after a list
PENDING = {"items": [], "act": None, "until": 0.0}
_ORDS = ("first", "second", "third", "fourth", "fifth")


def offer(title, items, act, footer="Say “the first one”, “the second one”…"):
    """items: (name, detail, value), at most five; act(value) runs on the one picked."""
    items = list(items)[:5]
    PENDING.update(items=items, act=act, until=time.time() + SECONDS)
    ui.choose(title, [(n, d) for n, d, _ in items], footer, SECONDS)


def waiting():
    return bool(PENDING["items"]) and time.time() < PENDING["until"]


def pick(which):
    """'the second one' / 'number 3' / 'the last one'."""
    items = PENDING["items"]
    which = re.sub(r"(\d)(?:st|nd|rd|th)$", r"\1", which)
    n = len(items) if which in ("last", "bottom") else 1 if which == "top" else num(which)
    if CTX.dry:
        return CTX.log(f"  item {n} of the list")
    if not n or not 1 <= n <= len(items):
        return ui.notify(f"Say “the first one” to “the {_ORDS[len(items) - 1]} one”")
    act, value = PENDING["act"], items[n - 1][2]
    PENDING.update(items=[], act=None, until=0.0)
    act(value)
