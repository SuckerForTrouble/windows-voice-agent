"""Learning from your retries, and "did you mean?".

Say something it doesn't get, then within 10 seconds say something that works, and the two
are a pair ("open spot a fly" then "open spotify"). The second time the same pair happens,
or the first time when the two sound alike, or when you picked it from "Did you mean?", it
becomes a fix in tuning.txt (the same file the AI trick writes, checked the same way) and the
pill says "Learned: … means …". "Forget that" right after undoes it. "No, that's wrong" right
after a command marks it as misunderstood, so what you say next is learned the same way.

Only what you said yourself, on purpose: push-to-talk, or always listening after the call word
(phrases without it never get this far, see listen.py). Never what was heard in Discord's sound,
never dictation."""
import difflib
import json
import time
from collections import Counter

from . import paths, tuning, ui
from .engine import CTX, clean, natural, plan

WINDOW = 10   # seconds from a miss to the retry that worked
FORGET = 120  # "forget that" undoes a fix learned this recently
SURE, MAYBE = 0.88, 0.75  # "did you mean": run it / offer it
_last = {"failed": "", "failed_t": 0.0, "failed_ran": False, "ran": "", "ran_t": 0.0, "line": "", "line_t": 0.0}
_phrases = {"t": 0.0, "list": []}
_vocab = set()


def vocab():
    """Words the commands and known names use: never replaced everywhere by a learnt word fix
    ("heard: steam -> stremio" would break Steam), only a whole phrase is mapped for them."""
    if not _vocab:
        from . import apps
        from .examples import CASES
        for text in [c[0] for c in CASES] + list(apps.APPS) + list(apps.SITES) + list(apps.APP_PROCS) + list(apps.SPOKEN):
            _vocab.update(_said(text).split())
    return _vocab


def _file():
    return paths.DATA / "learning.json"


def _load():
    try:
        return json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"pairs": {}}


def _save(data):
    paths.ensure()
    _file().write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _said(text):
    return natural(clean(text or "")).strip()


def _sim(a, b):
    """0..1 for two words, by sound and spelling; a different first letter only when it sounds the same."""
    from .files import sound, word_match
    if a == b:
        return 1.0
    v = word_match(a, b)
    return v if a[:1] == b[:1] or sound(a) == sound(b) else min(v, 0.6)


def alike(a, b):
    """Do two phrases sound alike, word for word ("open spot a fly" / "open spotify")?"""
    wa, wb = a.split(), b.split()
    if not wa or not wb:
        return False
    ab = sum(max(_sim(x, y) for y in wb) for x in wa) / len(wa)
    ba = sum(max(_sim(x, y) for x in wa) for y in wb) / len(wb)
    joined = _sim(a.replace(" ", ""), b.replace(" ", ""))
    return min(ab, ba) >= 0.75 or joined >= 0.85


def line_for(failed, worked):
    """The tuning line for a pair: a word fix when one word differs and sounds alike (it then
    works in every command), else the whole phrase."""
    wa, wb = failed.split(), worked.split()
    i = 0
    while i < min(len(wa), len(wb)) and wa[i] == wb[i]:
        i += 1
    j = 0
    while j < min(len(wa), len(wb)) - i and wa[-1 - j] == wb[-1 - j]:
        j += 1
    left, right = " ".join(wa[i:len(wa) - j]), " ".join(wb[i:len(wb) - j])
    known = vocab()
    if left and right and len(left.split()) <= 3 and len(right.split()) <= 2 and alike(left, right) and \
            left not in known and not all(w in known for w in left.split()) and tuning.check("heard", left, right) is None:
        return f"heard: {left} -> {right}"
    return f"say: {failed} -> {worked}"


# ----------------------------------------------------------------- what you said, and when
def note(text, routed, via="agent"):
    """After every command you said: remember a miss; a hit within WINDOW of one is a retry."""
    if via == "discord":
        return
    said, now = _said(text), time.time()
    if not said:
        return
    if not routed:
        _last.update(failed=said, failed_t=now, failed_ran=False)
        return
    if _last["failed"] and now - _last["failed_t"] <= WINDOW and said != _last["failed"]:
        pair(_last["failed"], said, _last["failed_ran"])
    _last.update(failed="", failed_ran=False, ran=said, ran_t=now)


def pair(failed, worked, failed_ran=False):
    """A miss and the retry that worked: learnt now when they sound alike, else the second
    time. failed_ran: the first one did run something ("no, that's wrong"): always the second
    time, so one slip can't remap a command that works."""
    data = _load()
    key = f"{failed} => {worked}"
    n = data["pairs"][key] = data["pairs"].get(key, 0) + 1
    _save(data)
    if n >= 2 or (alike(failed, worked) and not failed_ran):
        return learn(failed, worked)
    return False


def learn(failed, worked):
    """Write the fix to tuning.txt (refused if it doesn't check out) and say so."""
    line = line_for(_said(failed), _said(worked))
    added, refused = tuning.import_text(line, note="learned from a retry")
    if not added:
        if CTX.dry:
            CTX.log(f"  not learned: {line} ({refused[0][1] if refused else 'already there'})")
        return False
    _last.update(line=added[0], line_t=time.time())
    kind, left, right = tuning.parse(added[0])[0]
    ui.notify(f"Learned: “{left}” means “{right}”. Say “forget that” to undo")
    return True


def picked(said, phrase, run):
    """'Did you mean?' → 'the first one': run it, and remember that's what was meant (a pick
    is you saying so, so it's learnt the first time)."""
    _last.update(failed="")
    run(phrase)
    return learn(said, phrase)


def just_ran():
    """A command ran in the last WINDOW seconds (guard for "no, that's wrong")."""
    return CTX.dry or time.time() - _last["ran_t"] <= WINDOW


def wrong():
    """'No, that's wrong': the last command was a mistake; what you say next is the retry."""
    if CTX.dry:
        return CTX.log("  the last command was misheard: the next one is learned from")
    if _last["ran"]:
        _last.update(failed=_last["ran"], failed_t=time.time(), failed_ran=True, ran="")
    ui.notify("Sorry! Say it again: I'll learn from it")


def recent():
    """A fix was learnt in the last FORGET seconds (guard for "forget that")."""
    return bool(_last["line"]) and time.time() - _last["line_t"] <= FORGET


def forget():
    """'Forget that': take the fix just learnt out of tuning.txt."""
    if CTX.dry:
        return CTX.log("  remove the fix it just learned")
    line = _last["line"]
    lines = tuning._load_lines()
    if line not in lines:
        return ui.notify("Nothing to forget")
    i = lines.index(line)
    del lines[i]
    if i > 0 and lines[i - 1].startswith("# learned"):
        del lines[i - 1]
    paths.TUNING.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tuning.apply()
    _last.update(line="", line_t=0.0)
    ui.notify("Forgot it")


# ----------------------------------------------------------------- did you mean?
def _known():
    """Phrases that work: the examples, the guide's starters, and your own most used commands."""
    if time.time() - _phrases["t"] < 120 and _phrases["list"]:
        return _phrases["list"]
    from . import history
    from .examples import CASES
    from .guide import STARTERS
    mine = Counter(e.get("heard", "") for e in history.rows(30) if e.get("result") == "ran" and e.get("via") != "discord")
    out = [c[0] for c in CASES if c[1] and len(c) < 3] + [s for _, s in STARTERS] + [t for t, _ in mine.most_common(60) if t]
    _phrases.update(t=time.time(), list=list(dict.fromkeys(p.rstrip(".?!") for p in out)))
    return _phrases["list"]


def _score(a, b):
    wa, wb = a.split(), b.split()
    if not wa or not wb:
        return 0.0
    words = (sum(max(_sim(x, y) for y in wb) for x in wa) / len(wa) + sum(max(_sim(x, y) for x in wa) for y in wb) / len(wb)) / 2
    return max(words, difflib.SequenceMatcher(None, a, b).ratio())


def did_you_mean(text, known=None):
    """For a phrase that matched nothing: (sure, options). sure: a phrase so close it can just
    run (never a "strict" command like shutdown, and never one that types or searches free
    text); options: up to three (phrase, what it does) to offer instead. Each option is a
    different command."""
    said = _said(text)
    if len(said) < 3:
        return None, []
    scored = sorted(((_score(said, _said(p)), p) for p in (known if known is not None else _known())), reverse=True)
    was = CTX.dry
    CTX.dry = True  # route the candidates without anything happening
    picks, seen = [], set()
    try:
        for s, p in scored[:12]:
            if s < MAYBE:
                break
            steps, _ = plan(p, woke=True)
            what = tuple(r.say for r, _, _ in steps)
            if not steps or what in seen or any(r.free for r, _, _ in steps):
                continue
            seen.add(what)
            picks.append((s, p, steps))
    finally:
        CTX.dry = was
    if not picks:
        return None, []
    show = lambda p: _said(p)[:1].upper() + _said(p)[1:]  # noqa: E731  ("Paws the music" is an example of a mishearing)
    s, p, steps = picks[0]
    runner_up = picks[1][0] if len(picks) > 1 else 0.0
    if s >= SURE and s - runner_up >= 0.05 and not any(r.wake == "strict" for r, _, _ in steps):
        return show(p), []
    return None, [(show(p), " + ".join(r.say for r, _, _ in st)) for _, p, st in picks[:3]]


def _clear():
    """For the tests: forget the last few commands."""
    _last.update(failed="", failed_t=0.0, failed_ran=False, ran="", ran_t=0.0, line="", line_t=0.0)
    _phrases.update(t=0.0, list=[])

