"""How actions talk back. The app plugs in the OSD, tray balloons and the voice;
in a dry run (and the tests) everything is printed instead."""
import re

from .engine import CTX

handlers = {"notify": None, "speak": None, "osd_text": None, "choose": None}


def notify(msg):
    """Something worth seeing (an error, a result): the OSD pill, else a tray balloon."""
    if CTX.dry:
        CTX.log(f"  notify: {msg}")
        return
    h = handlers["notify"]
    if h:
        h(msg)


def choose(title, items, footer, seconds):
    """A short numbered list on the pill ("Which one?"); items are (name, where) pairs."""
    line = "  ".join(f"{i}. {name}" for i, (name, _) in enumerate(items, 1))
    if CTX.dry:
        CTX.log(f"  {title} {line}")
        return
    h = handlers["choose"]
    if h:
        h(title, items, footer, seconds)
    else:
        notify(f"{title} {line}")


def speak(text):
    text = re.sub(r"\s*·\s*|\n+", ", ", text)
    text = text.replace("%", " percent").replace("°C", " degrees").replace("→", "to")
    if CTX.dry:
        CTX.log(f"  speak: {text}")
        return
    h = handlers["speak"]
    if h:
        h(text)


def tell(msg, spoken=None):
    """An answer: on screen and, unless voice replies are off, out loud."""
    notify(msg)
    speak(spoken or msg)
