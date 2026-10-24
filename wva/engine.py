"""Transcript -> commands. Ported from a Linux voice agent (v3, 2026-10-22).

How a transcript becomes commands:
  1. clean      lower-case, fix things the recogniser mishears (ALIASES + the user's tuning file)
  2. wake word  "computer …" (also heard as "commuter", "compute her", …)
  3. natural    strip politeness and filler: "can you please …", "I want to …",
                "um …", "… for me", "… thanks" — so normally spoken requests match
  4. chains     "open youtube and search for cats", "… then …", "…, …": every part
                must be a command, otherwise the whole thing is one command or nothing
  5. rules      each rule lists several ways to say the same thing; the WHOLE part
                must match, so a sentence that merely contains a command word is
                never hijacked

Bare vs wake word: with the agent key everything counts as addressed to the
computer. Through the dictation key only "computer …" runs commands.
Nothing here touches Windows: the rules (rules.py) bring the actions.
"""
import re
from collections import namedtuple


class Ctx:
    dry = False          # print what would happen, do nothing
    raw = ""             # the transcript as spoken, for typing with its own capitalisation
    last_target = None   # what the previous step of a chain opened ("stremio", "spotify", …)
    log = print          # where dry-run lines go
    front = ""           # dry runs: pretend this window title is in front ("instagram", "youtube")


CTX = Ctx()

Rule = namedtuple("Rule", "group say desc pats fn wake guard free after late")
RULES = []


def rule(group, say_, desc, pats, fn, wake=False, guard=None, free=False, after=0.35, late=False):
    """wake=True: needs the agent key or "computer". "strict": even inside a chain.
    free: the rule swallows free text (search, type…), so a chain may split it.
    after: seconds to wait before the next step of a chain. late: tried after all others."""
    if isinstance(pats, str):
        pats = [pats]
    RULES.append(Rule(group, say_, desc, [re.compile(p) for p in pats], fn, wake, guard, free, after, late))


WAKE = r"(?:(?:hey|hi|ok|okay|yo)\s+)?(?:computer|computers|computa|komputer|compute her|commuter|come pewter|compooter)\b"

# Things the recogniser mishears. (regex, replacement) on the lower-cased transcript,
# for ROUTING ONLY: dictated text is typed exactly as heard.
ALIASES = [
    (r"\bfull screen\b", "fullscreen"),
    (r"\bscreen ?shot\b|\bscreen shut\b", "screenshot"),
    (r"\bmike\b|\bmic phone\b", "mic"),
    (r"\byou tube\b|\byoutube's\b|\byou too\b", "youtube"),
    (r"\bgit hub\b|\bget hub\b|\bgithub's\b", "github"),
    (r"\bg mail\b|\bgee mail\b|\bjimmail\b", "gmail"),
    (r"\bred it\b|\bread it\b(?= dot| com)", "reddit"),
    (r"\bwhat's app\b|\bwhats app\b|\bwhat sap\b", "whatsapp"),
    (r"\bchat (?:gpt|gbt|g p t|gp t)\b", "chatgpt"),
    (r"\bstack over flow\b", "stackoverflow"),
    (r"\b(new|close|next|previous|reopen) (?:tap|tabs|tub|top)\b", r"\1 tab"),
    (r"\b(?:paws|pours|pose|pass|posts?) (?:the )?(music|song|video|spotify)\b", r"pause \1"),
    (r"\bvolume app\b|\bvolume op\b", "volume up"),
    (r"\bvolume (?:dawn|done|town|don)\b", "volume down"),
    (r"\bbright ness\b|\bbrightest\b", "brightness"),
    (r"\bblue tooth\b", "bluetooth"),
    (r"\bwi fi\b|\bwhy fi\b|\bwifey\b|\bwi-fi\b", "wifi"),
    (r"\bnext (?:sung|sang|son)\b", "next song"),
    (r"\bscroll dawn\b|\bscroll done\b", "scroll down"),
    (r"\bzoom and\b", "zoom in"),
    (r"\bnew ?window\b", "new window"),
    (r"\bin cognito\b|\bincognito\b", "private"),
    (r"\bspot if i\b|\bspotty fi\b|\bspot a fi\b|\bspotifi\b|\bspotify's\b", "spotify"),
    (r"\bdiscords?\b|\bthis cord\b|\bdis cord\b", "discord"),
    (r"\bplay ?list\b", "playlist"),
    (r"\bstream ?io\b|\bstream mio\b|\bstrem ?io\b|\bstreamy ?o\b|\bstremio's\b|\bstream yo\b", "stremio"),
    (r"\binsta gram\b|\binstagram's\b|\binsta\b", "instagram"),
    (r"\b(?:reals|rails|riels)\b", "reels"),
    (r"\b(?:the fan|defend|deafened|death in|deaf in)\b(?= (?:me|myself|discord|on discord)\b|$)", "deafen"),
    (r"\bun ?deafen\b|\bundefend\b", "undeafen"),
    (r"\bwhats\b", "what's"), (r"\btodays\b", "today's"), (r"\bhows\b", "how's"),
    (r"\b(\w+)-(hours?|minutes?|seconds?|mins?|secs?)\b", r"\1 \2"),
    (r"\bmins?\b", "minutes"), (r"\bsecs?\b", "seconds"), (r"\bhrs?\b", "hours"),
    (r"\bnevermind\b", "never mind"),
    (r"^closed (window|tab|it|this)\b", r"close \1"), (r"\bclose and close\b", "close"),
    (r"\bshut ?down\b", "shutdown"),
    (r"\bshuffled?\b(?= (?:the|my|this|music|songs|playlist|it|queue|on|off))|\bshovel\b(?= (?:the|my|music|songs))", "shuffle"),
    (r"\bv ?s code\b|\bvisual studio code\b", "vs code"),
    (r"\bo b s\b", "obs"),
    (r"\bn ?video\b", "nvidia"),
]
ALIASES = [(re.compile(p), r) for p, r in ALIASES]

# The user's own fixes, from tuning.txt (see tuning.py): filled in at start-up.
TUNE_WORDS = []   # [(compiled regex, replacement)]
TUNE_SAY = {}     # natural phrase -> phrase that routes

# Politeness and filler around a request, stripped until nothing changes.
LEAD = [
    r"(?:hey|hi|ok|okay|so|um+|uh+|uhm|erm|yeah|yes|alright|all right|well|and|also|then|oh)\s+",
    r"(?:can|could|would|will|can't|won't) you\s+(?:please\s+)?(?:kindly\s+)?",
    r"(?:please|kindly|pls|plz)\s+",
    r"(?:i want (?:you )?to|i wanna|i'd like (?:you )?to|i would like (?:you )?to|i need (?:you )?to|"
    r"i want|i need|i'd like|let's|lets|let me|go ahead and|just|quickly|quick|try to|help me)\s+",
]
TRAIL = r"\s+(?:please|for me|now|right now|thanks|thank you|real quick|quickly|asap|okay|ok|already|man|bro|buddy|mate|yaar)$"

# Chain separators, tried only after the whole utterance failed to be one command
# (so "search rock and roll" stays one search).
CHAIN = r"\s*[,;.!?]\s*|\s+(?:and then|and after that|after that|then|and also|and|also|plus|followed by)\s+"

# ----------------------------------------------------------------- numbers
_ONES = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_ONES.update({"to": 2, "too": 2, "for": 4, "fore": 4, "won": 1, "ate": 8, "tree": 3, "a": 1, "an": 1,
              "single": 1, "couple": 2, "few": 3, "half": 0})
_TENS = {w: i * 10 for i, w in enumerate(
    "x x twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "x"}
_ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
        "eighth": 8, "ninth": 9, "tenth": 10, "last": 9}


def num(s):
    """'3' / 'three' / 'twenty five' / 'one hundred and fifty' / 'third' / '40%' -> int, else None."""
    s = s.strip().lower().replace("-", " ").replace("%", "").replace(" percent", "")
    s = re.sub(r"\b(?:number|no)\b", "", s).strip()
    if s.isdigit():
        return int(s)
    if s in _ORD:
        return _ORD[s]
    total = 0
    seen = False
    for w in s.split():
        if w == "and":
            continue
        if w in _ONES:
            total += _ONES[w]
        elif w in _TENS:
            total += _TENS[w]
        elif w == "hundred":
            total = max(total, 1) * 100
        elif w.isdigit():
            total += int(w)
        else:
            return None
        seen = True
    return total if seen else None


_UNITS = {"hour": 3600, "minute": 60, "second": 1}


def parse_duration(text):
    """'1 hour and 30 minutes' / 'an hour and a half' / '90 seconds' / 'half an hour' -> seconds, else None."""
    t = (text or "").lower().strip()
    t = re.sub(r"\bhalf an? (hour|minute)\b", r"0.5 \1", t)
    t = re.sub(r"\ban? (hour|minute|second)\b", r"1 \1", t)
    t = re.sub(r"\b(\S+(?: \S+)?) (hours?|minutes?) and a half\b", lambda m: f"{m.group(1)} and a half {m.group(2)}", t)
    total, rest = 0.0, t
    for m in re.finditer(r"([\w.]+(?: [\w]+)?(?: and a half)?) (hours?|minutes?|seconds?)\b", t):
        words = m.group(1).replace(" and a half", "")
        words = re.sub(r"^(?:and|for|of) ", "", words)
        if set(words.split()) & {"to", "too", "for", "fore", "won", "ate", "tree", "single", "couple", "few"}:
            return None  # num() reads "to" as 2: "add 1 hour to 1 hour timer" became a 3-hour timer
        try:
            v = float(words)
        except ValueError:
            v = num(words)
        if v is None:
            return None
        if "and a half" in m.group(1):
            v += 0.5
        total += v * _UNITS[m.group(2).rstrip("s")]
        rest = rest.replace(m.group(0), " ", 1)
    if total <= 0 or re.sub(r"\b(?:and|for|of)\b|[\s,]", "", rest):
        return None  # anything left over means it wasn't only a duration
    return int(total)


def fmt_dur(secs):
    secs = int(round(secs))
    h, m, s = secs // 3600, secs % 3600 // 60, secs % 60
    parts = [f"{v} {u}{'s' if v != 1 else ''}" for v, u in ((h, "hour"), (m, "minute"), (s, "second")) if v]
    return " ".join(parts) or "0 seconds"


# ----------------------------------------------------------------- routing

def clean(text):
    """Lower-case, unify quotes, fix mishearings. Punctuation is kept (chains split on it)."""
    t = text.lower().replace("’", "'").replace("‘", "'")
    for sym, word in (("\t", " tab "), ("#", " hash "), ("/", " slash "), ("*", " star "),
                      ("@", " at "), ("&", " and "), ("=", " equals "), ("|", " pipe "), ("~", " tilde ")):
        t = t.replace(sym, word)
    t = re.sub(r"(\d)\s*%", r"\1 percent", t)
    t = re.sub(r"[^\w\s',.;!?+-]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    for pat, rep in ALIASES:
        t = pat.sub(rep, t)
    for pat, rep in TUNE_WORDS:
        t = pat.sub(rep, t)
    return re.sub(r"\s+", " ", t).strip()


def natural(part):
    """One command's text: no punctuation, no politeness, no filler."""
    t = re.sub(r"[,.;!?]", " ", part)
    t = re.sub(r"(?<!\w)-|-(?!\w)", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    prev = None
    while prev != t:
        prev = t
        for p in LEAD:
            t = re.sub("^" + p, "", t)
        t = re.sub(TRAIL, "", t)
        t = t.strip()
    return TUNE_SAY.get(t, t)


def match(t):
    """First rule whose pattern fully matches t (guard permitting): (rule, groups) or None.
    Catch-all (late) rules come after all the others, in their own order."""
    for r in [r for r in RULES if not r.late] + [r for r in RULES if r.late]:
        for p in r.pats:
            mm = p.fullmatch(t)
            if not mm:
                continue
            groups = tuple(g for g in mm.groups() if g is not None) if r.fn.__code__.co_argcount != len(mm.groups()) else mm.groups()
            try:
                if r.guard is None or r.guard(*groups):
                    return r, groups
            except (TypeError, ValueError):
                continue
    return None


def plan(text, woke=False):
    """Transcript -> (steps, woke). steps = [(rule, groups, text)] or [] for dictation.
    woke=True: the agent key was used, as good as saying the wake word."""
    t = clean(text)
    m = re.match(WAKE + r"[\s,.!?]*(.*)", t)
    if m:
        woke, t = True, m.group(1)
    whole = match(natural(t))
    parts = [p for p in re.split(CHAIN, t) if p and p.strip(" ,.;!?")]
    chain = []
    if len(parts) > 1:
        for p in parts:
            mm = match(natural(p))
            if not mm:
                chain = []
                break
            chain.append((mm[0], mm[1], natural(p)))
    if chain:
        bare = any(not r.wake for r, _, _ in chain)
        strict = any(r.wake == "strict" for r, _, _ in chain)
        allowed = woke or (bare and not strict)
        if allowed and (whole is None or whole[0].free or (whole[0].wake and not woke)):
            return chain, woke
    if whole and (woke or not whole[0].wake):
        return [(whole[0], whole[1], natural(t))], woke
    return [], woke
