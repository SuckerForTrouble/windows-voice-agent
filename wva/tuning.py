"""Teaching the agent your voice without Claude: an AI of your choice does the reading.

1. "export my voice history" (or the tray) writes tune-me.txt to your Desktop: a prompt,
   every command, and what you said that didn't work (with what you said right after
   that did work, which is usually what you meant).
2. Paste the whole file into Gemini / ChatGPT / any AI.
3. Copy its answer and say "import the AI answer" (or use the tray). Only lines of two
   simple shapes are taken, and every one is checked against the real commands first:

     heard: stream io -> stremio            a word the recogniser gets wrong, fixed everywhere
     say: chuck the volume up -> volume up  a whole phrase, mapped to one that works

They land in tuning.txt (%LOCALAPPDATA%\\WindowsVoiceAgent), which you can also edit
by hand ("open my tuning file" in the tray). No regexes, no code: a bad AI answer
can't break anything."""
import re
from collections import Counter
from datetime import datetime

from . import engine, history, paths, ui
from .engine import CTX

LINE = re.compile(r"^\s*[-*•]?\s*(heard|say)\s*:\s*(.+?)\s*(?:->|→|=>)\s*(.+?)\s*$", re.I)
COMMON = set("a an the to and or of in on it is i you me my this that for with be at by up down go".split())

PROMPT = """\
=== INSTRUCTIONS FOR THE AI — read all of this, then answer ===
I use a voice-command program on Windows. A speech recogniser turns what I say into
text, then the program matches that text against a fixed list of commands. Below are
(1) the commands it understands, with example phrasings, (2) my existing fixes, and
(3) what I said recently that it did NOT understand, plus things I said right after a
failure that DID work (usually what I meant).

Your job: write fixes so that next time my failed sentences work. Reply with ONLY lines
in exactly these two shapes, between the BEGIN/END markers, nothing else:

BEGIN TUNING
heard: <words the recogniser got wrong> -> <the correct words>
say: <a whole sentence I said> -> <an example phrasing from the command list that does what I meant>
END TUNING

Rules:
- "heard:" is for a misheard name or word that would be wrong everywhere
  (e.g. "heard: stream io -> stremio", "heard: spot if i -> spotify"). Never use it for
  ordinary English words like "the", "play", "open".
- "say:" maps one of MY failed sentences (lower case, as written below) to a phrasing
  copied from the command list. Only use commands that exist in the list.
- Skip anything that looks like normal chatting, dictation or a mistake, and anything
  you're unsure about. Fewer good lines beat many guesses.
- Don't repeat fixes that are already in "MY CURRENT FIXES".
- At most 60 lines.
"""


def _load_lines():
    try:
        return paths.TUNING.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []


def parse(text):
    """[(kind, left, right)] from any text (an AI reply, the tuning file)."""
    out = []
    for line in text.splitlines():
        m = LINE.match(line)
        if m:
            kind, left, right = m.group(1).lower(), m.group(2).strip().strip("\"'").lower(), m.group(3).strip().strip("\"'").lower()
            if left and right and left != right:
                out.append((kind, left, right))
    return out


def apply():
    """Load tuning.txt into the engine (at start-up and after an import)."""
    words, says = [], {}
    for kind, left, right in parse("\n".join(_load_lines())):
        if kind == "heard":
            words.append((re.compile(r"\b" + re.escape(left) + r"\b"), right))
    engine.TUNE_WORDS[:] = words
    engine.TUNE_SAY.clear()  # so natural() below doesn't map through the old phrases
    for kind, left, right in parse("\n".join(_load_lines())):  # after the word fixes, which change the text
        if kind == "say":
            says[engine.natural(engine.clean(left))] = engine.natural(engine.clean(right))
    engine.TUNE_SAY.clear()
    engine.TUNE_SAY.update(says)
    return len(words), len(says)


def _routes(phrase):
    was = CTX.dry
    CTX.dry = True
    try:
        steps, _ = engine.plan(phrase, woke=True)
        return bool(steps)
    finally:
        CTX.dry = was


def check(kind, left, right):
    """None if the line is fine, else why it was refused."""
    if len(left) > 80 or len(right) > 80:
        return "too long"
    if kind == "heard":
        if left in COMMON or len(left) < 3:
            return "too common a word to replace everywhere"
        if not re.fullmatch(r"[\w' .-]+", left + right):
            return "odd characters"
        return None
    if not _routes(right):
        return f"'{right}' isn't a command"
    return None


def import_text(text):
    """Add the good lines of an AI reply to tuning.txt. Returns (added, refused[(line, why)])."""
    have = {(k, l) for k, l, _ in parse("\n".join(_load_lines()))}
    block = re.search(r"BEGIN TUNING(.*?)END TUNING", text, re.S | re.I)
    added, refused = [], []
    for kind, left, right in parse(block.group(1) if block else text):
        if (kind, left) in have:
            continue
        why = check(kind, left, right)
        if why:
            refused.append((f"{kind}: {left} -> {right}", why))
            continue
        added.append(f"{kind}: {left} -> {right}")
        have.add((kind, left))
    if added:
        lines = _load_lines()
        if not lines:
            lines = ["# Your fixes. 'heard: wrong -> right' fixes a word everywhere,",
                     "# 'say: what you said -> a command that works' maps a whole phrase.",
                     "# Delete a line to undo it. Lines starting with # are ignored.", ""]
        lines += [f"# imported {datetime.now():%Y-%m-%d %H:%M}"] + added
        paths.ensure()
        paths.TUNING.write_text("\n".join(lines) + "\n", encoding="utf-8")
        apply()
    return added, refused


def import_from_clipboard():
    if CTX.dry:
        return CTX.log("  import tuning lines from the clipboard")
    from . import win
    added, refused = import_text(win.clipboard_text())
    if not added and not refused:
        ui.notify("No tuning lines on the clipboard. Copy the AI's whole answer first.")
        return
    ui.tell(f"Learned {len(added)} fixes" + (f", skipped {len(refused)}" if refused else ""))


# ----------------------------------------------------------------- export
def _commands_text():
    from . import guide
    out = []
    for group in guide.groups():
        out.append(f"\n## {group['name']}")
        for r in group["rules"]:
            ex = "; ".join(f'"{e}"' for e in r["examples"][:3])
            out.append(f"- {r['say']}" + (f" — {r['desc']}" if r["desc"] else "") + (f" — e.g. {ex}" if ex else ""))
    return "\n".join(out)


def build_export(days=30):
    rows = history.rows(days)
    misses = Counter(e.get("clean", "").rstrip(".?!") for e in rows if e.get("result") == "unmatched" and e.get("clean"))
    pairs = Counter()
    for prev, nxt in zip(rows, rows[1:]):
        if prev.get("result") == "unmatched" and nxt.get("result") == "ran":
            try:
                gap = (datetime.fromisoformat(nxt["t"]) - datetime.fromisoformat(prev["t"])).total_seconds()
            except (ValueError, KeyError):
                continue
            if gap <= 30:
                pairs[(prev.get("clean", "").rstrip(".?!"), nxt.get("clean", "").rstrip(".?!"))] += 1
    used = Counter(st for e in rows if e.get("result") == "ran" for st in e.get("steps") or [])
    parts = [PROMPT, "=== THE COMMANDS ===", _commands_text(), "", "=== MY CURRENT FIXES ==="]
    current = [f"{k}: {l} -> {r}" for k, l, r in parse("\n".join(_load_lines()))]
    parts.append("\n".join(current) or "(none yet)")
    parts += ["", f"=== NOT UNDERSTOOD (last {days} days, how often × what the recogniser heard) ==="]
    parts.append("\n".join(f"{n}× {t}" for t, n in misses.most_common(150)) or "(nothing — everything worked)")
    parts += ["", "=== FAILED, THEN SAID THIS WITHIN 30 s AND IT WORKED (failed  =>  worked) ==="]
    parts.append("\n".join(f"{n}× {a}  =>  {b}" for (a, b), n in pairs.most_common(80)) or "(none)")
    parts += ["", "=== WORKED (most used commands, for reference) ==="]
    parts.append("\n".join(f"{n}× {s}" for s, n in used.most_common(40)) or "(none yet)")
    parts += ["", "=== END OF FILE — now write your answer between BEGIN TUNING and END TUNING ==="]
    return "\n".join(parts) + "\n", len(misses)


def export_for_ai():
    text, n = build_export()
    if CTX.dry:
        return CTX.log(f"  write tune-me.txt ({n} misses)")
    out = paths.user_folder("desktop") / "tune-me.txt"
    try:
        out.write_text(text, encoding="utf-8")
    except OSError:
        out = paths.DATA / "tune-me.txt"
        out.write_text(text, encoding="utf-8")
    import os
    os.startfile(str(out))
    ui.tell(f"tune-me.txt is on your Desktop ({n} things to fix). Paste all of it into Gemini or ChatGPT, "
            "copy the answer, then say 'import the AI answer'.",
            "Saved tune me dot text on your desktop. Paste it into an AI, copy its answer, then say import the AI answer.")
