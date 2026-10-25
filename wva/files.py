"""Files by voice: 'find the file budget', 'open my last download', 'show my last screenshot'.

Looks through your own folders (Desktop, Documents, Downloads, Pictures, Videos, Music,
OneDrive), the files you opened lately (Windows' Recent list, any drive) and, when Windows
Search is running, its index, with a time limit so it answers in a second or two. For a
search across everything Windows has indexed: 'search my files for …' opens Explorer's own search.

Names are matched word by word and forgive misspellings: "budjet" finds budget.xlsx,
"fizzics" finds Physics.docx (they sound the same), "chemistry assignment" finds
assgnmt_chem.docx (shortened words). When two files fit about as well, the pill lists
three and you say "the second one"; it remembers that pick for next time."""
import difflib
import functools
import json
import os
import re
import struct
import subprocess
import threading
import time
from pathlib import Path

from . import paths, ui
from .engine import CTX

SKIP = {"appdata", "node_modules", ".git", "$recycle.bin", "__pycache__", ".cache", "venv", ".venv", "cache"}
PARTIAL = (".crdownload", ".part", ".tmp", ".download", ".partial")
VIDEO = (".mp4", ".mkv", ".webm", ".mov", ".avi")
PICKS = paths.DATA / "file-picks.json"   # what you said -> the file you picked from a list

# Words people say around a name that aren't part of it
FILLER = {"the", "my", "a", "an", "file", "files", "document", "called", "named", "folder", "please", "that",
          "this", "thing", "of", "for", "from", "with", "in", "on", "about", "and"}
# "the budget excel" / "my resume pdf": a spoken kind matches the extension
KINDS = {"excel": ("xlsx", "xls", "xlsm", "csv"), "spreadsheet": ("xlsx", "xls", "csv", "ods"), "sheet": ("xlsx", "xls", "csv"),
         "word": ("docx", "doc", "rtf", "odt"), "pdf": ("pdf",), "powerpoint": ("pptx", "ppt"), "slides": ("pptx", "ppt", "pdf"),
         "presentation": ("pptx", "ppt"), "photo": ("jpg", "jpeg", "png", "heic", "webp"),
         "picture": ("jpg", "jpeg", "png", "heic", "webp", "bmp"), "image": ("jpg", "jpeg", "png", "webp", "gif", "bmp"),
         "video": ("mp4", "mkv", "mov", "avi", "webm"), "song": ("mp3", "m4a", "flac", "wav", "ogg"),
         "music": ("mp3", "m4a", "flac", "wav", "ogg"), "text": ("txt", "md"), "notes": ("txt", "md"),
         "zip": ("zip", "rar", "7z"), "exe": ("exe", "msi"), "installer": ("exe", "msi")}
NUMBER_WORDS = {w: str(i) for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen twenty".split())}


def roots():
    out = [paths.user_folder(n) for n in ("desktop", "documents", "downloads", "pictures", "videos", "music")]
    od = os.environ.get("OneDrive")
    if od:
        out.append(Path(od))
    seen, uniq = set(), []
    for r in out:
        if r.exists() and str(r).lower() not in seen:
            seen.add(str(r).lower())
            uniq.append(r)
    return uniq


def walk(dirs=False, limit=80000, seconds=2.5, max_depth=7):
    """(path, mtime) of files (or folders) under your folders, newest scans first."""
    deadline, n = time.time() + seconds, 0
    stack = [(r, 0) for r in roots()]
    while stack and n < limit and time.time() < deadline:
        d, depth = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    n += 1
                    name = e.name.lower()
                    if name.startswith(".") or name in SKIP:
                        continue
                    try:
                        if e.is_dir(follow_symlinks=False):
                            if depth < max_depth:
                                stack.append((e.path, depth + 1))
                            if dirs:
                                yield e.path, e.stat().st_mtime
                        elif not dirs:
                            yield e.path, e.stat().st_mtime
                    except OSError:
                        continue
        except OSError:
            continue


# ----------------------------------------------------------------- matching
_CAMEL, _CAPS, _WORD = re.compile(r"([a-z])([A-Z])"), re.compile(r"([A-Z]+)([A-Z][a-z])"), re.compile(r"[a-z]+|\d+")


def words(text):
    """'assgnmt_chem-v2', 'MyResume', 'Physics Assignment four' -> lower-case words, numbers as digits."""
    text = _CAPS.sub(r"\1 \2", _CAMEL.sub(r"\1 \2", text))
    return [NUMBER_WORDS.get(w, w) for w in _WORD.findall(text.lower())]


@functools.lru_cache(maxsize=4096)
def sound(w):
    """A rough sound-alike key (Metaphone-style): physics = fizzics = fisiks, resume = rezume."""
    for a, b in (("ph", "f"), ("ck", "k"), ("sch", "sk"), ("sh", "x"), ("ch", "x"), ("th", "0"), ("gh", ""),
                 ("kn", "n"), ("wr", "r"), ("wh", "w"), ("qu", "kw"), ("dg", "j"), ("x", "ks")):
        w = w.replace(a, b)
    w = re.sub(r"c(?=[eiy])", "s", w)
    w = re.sub(r"g(?=[eiy])", "j", w)
    w = w.replace("c", "k").replace("q", "k").replace("z", "s").replace("dj", "j")
    head = "a" if w[:1] in "aeiouy" else w[:1]
    return re.sub(r"(.)\1+", r"\1", head + re.sub(r"[aeiouyhw]", "", w[1:]))


def _subseq(short, long):
    it = iter(long)
    return all(ch in it for ch in short)


@functools.lru_cache(maxsize=200000)
def word_match(said, name):
    """0..1: how well a spoken word fits one word of a file name."""
    if said == name:
        return 1.0
    if said.isdigit() or name.isdigit():
        return 0.0
    short, long = sorted((said, name), key=len)
    best = 0.0
    if len(short) >= 3 and long.startswith(short):
        best = 0.85                     # chem = chemistry, docs = documents
    elif len(short) >= 3 and short[0] == long[0] and _subseq(short, long) and len(short) >= 0.4 * len(long):
        best = 0.8                      # assgnmt = assignment, mgmt = management
    if len(short) >= 3 and len(sound(said)) >= 2 and sound(said) == sound(name):
        best = max(best, 0.8)           # fizzics = physics
    if best < 0.85 and 2 * len(short) >= 0.75 * (len(short) + len(long)):
        sm = difflib.SequenceMatcher(None, said, name)
        if sm.real_quick_ratio() >= 0.75 and sm.quick_ratio() >= 0.75 and sm.ratio() >= 0.75:
            best = max(best, sm.ratio())  # budjet = budget, rezume = resume
    return best


def match(path, said):
    """(coverage 0..1, score) of a file name for the spoken words. Coverage: how much of what
    was said is in the name; the score adds how alike the whole names are and prefers
    names without extra words."""
    p = Path(path)
    stem, ext = (p.name, "") if not p.suffix or len(p.suffix) > 6 else (p.stem, p.suffix[1:].lower())
    name = words(stem)
    if not name or not said:
        return 0.0, 0.0
    toks = name + [a + b for a, b in zip(name, name[1:])]  # "home_work" for "homework"
    best = []
    for w in said:
        m = max(word_match(w, t) for t in toks)
        if ext and ext in KINDS.get(w, ()):
            m = 1.0
        best.append(m)
    for i in range(len(said) - 1):  # "home work" for "homework"
        j = max(word_match(said[i] + said[i + 1], t) for t in toks)
        if j > best[i] and j > best[i + 1]:
            best[i] = best[i + 1] = j
    cover = sum(best) / len(best)
    if cover == 0:
        return 0.0, 0.0
    used = sum(1 for t in name if any(word_match(w, t) for w in said))
    whole = difflib.SequenceMatcher(None, " ".join(said), " ".join(name)).ratio()
    return cover, cover * 2 + whole * 0.3 - max(0, len(name) - used) * 0.03


def spoken(query):
    ws = words(query)
    kept = [w for w in ws if w not in FILLER]
    return kept or ws


def key(query):
    return " ".join(spoken(query))


# ----------------------------------------------------------------- where to look
def recent_dir():
    return Path(os.environ.get("APPDATA") or Path.home() / "AppData/Roaming") / "Microsoft" / "Windows" / "Recent"


def lnk_target(path):
    """The local path a Windows shortcut (.lnk) points to, read from its LinkInfo (MS-SHLLINK), or None."""
    try:
        with open(path, "rb") as f:
            data = f.read(65536)
        if len(data) < 76 or struct.unpack_from("<I", data, 0)[0] != 0x4C:
            return None
        flags = struct.unpack_from("<I", data, 20)[0]
        pos = 76
        if flags & 0x1:  # HasLinkTargetIDList
            pos += 2 + struct.unpack_from("<H", data, pos)[0]
        if not flags & 0x2:  # no LinkInfo
            return None
        info = pos
        _size, head, iflags, _vol, base, _net, suffix = struct.unpack_from("<7I", data, info)
        if not iflags & 0x1:  # not a local path (a network share)
            return None

        def text(off, wide):
            start = end = info + off
            if wide:
                while end + 1 < len(data) and data[end:end + 2] != b"\0\0":
                    end += 2
                return data[start:end].decode("utf-16-le")
            end = data.index(b"\0", start)
            return data[start:end].decode("mbcs" if paths.WINDOWS else "cp1252", "replace")
        if head >= 0x24:
            ubase, usuffix = struct.unpack_from("<2I", data, info + 28)
            out = text(ubase, True) + (text(usuffix, True) if usuffix else "")
        else:
            out = text(base, False) + (text(suffix, False) if suffix else "")
        return out or None
    except (OSError, ValueError, struct.error, UnicodeDecodeError):
        return None


def recent(limit=400):
    """Targets of the files and folders you opened lately: {path: mtime of the shortcut}."""
    out = {}
    try:
        lnks = sorted((e for e in os.scandir(recent_dir()) if e.name.lower().endswith(".lnk")),
                      key=lambda e: e.stat().st_mtime, reverse=True)[:limit]
    except OSError:
        return out
    for e in lnks:
        t = lnk_target(e.path)
        if t:
            out.setdefault(t, e.stat().st_mtime)
    return out


def indexed(said, limit=300, seconds=2.0):
    """Paths from Windows Search's index whose name starts like a spoken word (any indexed drive).
    Empty when the index isn't there; the folder walk still runs."""
    if not paths.WINDOWS:
        return []
    starts = sorted({re.sub(r"[^a-z0-9]", "", w)[:3] for w in said if len(w) >= 3})
    if not starts:
        return []
    where = " OR ".join(f"System.FileName LIKE '{s}%'" for s in starts)
    sql = f"SELECT TOP {limit} System.ItemPathDisplay FROM SystemIndex WHERE SCOPE='file:' AND ({where})"
    out = []

    def run():
        try:
            import comtypes
            import comtypes.client
            comtypes.CoInitialize()
            rs = comtypes.client.CreateObject("ADODB.Recordset", dynamic=True)
            rs.Open(sql, "Provider=Search.CollatorDSO;Extended Properties='Application=Windows';")
            while not rs.EOF:
                out.append(str(rs.Fields.Item(0).Value))
                rs.MoveNext()
            rs.Close()
        except Exception:  # no index, the service stopped, a policy: the walk is enough
            pass
    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(seconds)
    return list(out)


def _picks():
    try:
        return json.loads(PICKS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def remember(query, path):
    p = _picks()
    p[key(query)] = path
    try:
        paths.ensure()
        PICKS.write_text(json.dumps(dict(list(p.items())[-300:]), indent=1), encoding="utf-8")
    except OSError:
        pass


def candidates(query, dirs=False):
    """Every place worth scoring: (path, mtime, opened lately)."""
    said = spoken(query)
    rec = recent()
    lately = {p.lower() for p in rec}
    seen = set()
    for p, mtime in walk(dirs=dirs):
        seen.add(p.lower())
        yield p, mtime, p.lower() in lately
    picked = _picks().get(key(query))
    extra = list(rec.items()) + [(p, 0) for p in indexed(said)] + ([(picked, 0)] if picked else [])
    for p, mtime in extra:
        if p.lower() not in seen:
            seen.add(p.lower())
            yield p, mtime, p.lower() in lately


def rank(query, dirs=False, found=None, top=5):
    """[(score, coverage, path)] best first. found: (path, mtime, recent) to score instead of looking."""
    said = spoken(query)
    picked = _picks().get(key(query))
    # A quick look at each name's words first: only names with a word like one you said get scored
    probe = [w for w in said if not w.isdigit()] or said
    probe += [a + b for a, b in zip(said, said[1:])]
    memo = {}

    def near(t):
        v = memo.get(t)
        if v is None:
            v = memo[t] = any(word_match(w, t) for w in probe)
        return v
    now, out = time.time(), []
    for p, mtime, rec in (found if found is not None else candidates(query, dirs)):
        if not any(near(t) for t in words(os.path.basename(p))):
            continue
        cover, sc = match(p, said)
        if cover < 0.4:
            continue
        sc += min(0.15, max(0.0, (mtime - now + 90 * 86400) / (90 * 86400)) * 0.15)  # changed lately
        sc += 0.2 if rec else 0.0                                                    # opened lately
        sc += 0.6 if picked and p.lower() == picked.lower() else 0.0                 # picked before
        out.append((sc, cover, p))
    out.sort(reverse=True)
    good = []
    for sc, cover, p in out:  # files from the Recent list or the index may be gone, or the wrong kind
        if found is not None or (os.path.isdir(p) if dirs else os.path.isfile(p)):
            good.append((sc, cover, p))
            if len(good) == top:
                break
    return good


def decide(ranked):
    """'open' (sure), 'pick' (a short list) or 'none'."""
    if not ranked:
        return "none"
    best = ranked[0]
    if best[1] >= 0.75 and (len(ranked) == 1 or best[0] - ranked[1][0] >= 0.12):
        return "open"
    return "pick"


def find(query, dirs=False):
    """The one clear best match, or None."""
    r = rank(query, dirs)
    return r[0][2] if decide(r) == "open" else None


# ----------------------------------------------------------------- the short list
def offer(query, items):
    """'Which one?' with the files that fit about as well; the pick is remembered for next time."""
    from . import choices

    def use(path):
        remember(query, path)
        _open(path)
        ui.notify(f"Opened {Path(path).name}")
    choices.offer("Which one?", [(Path(p).name, Path(p).parent.name, p) for p in items], use)


def newest(folder, exts=None):
    try:
        files = [e for e in os.scandir(folder) if e.is_file() and not e.name.lower().endswith(PARTIAL)
                 and not e.name.startswith((".", "~$")) and (not exts or e.name.lower().endswith(exts))]
    except OSError:
        return None
    return max(files, key=lambda e: e.stat().st_mtime).path if files else None


def _open(path, reveal=False):
    if reveal:
        subprocess.Popen(["explorer.exe", "/select,", path], creationflags=0x08000000)
    else:
        os.startfile(path)


# ----------------------------------------------------------------- commands
def open_found(query, dirs=False):
    if CTX.dry:
        return CTX.log(f"  find {'folder' if dirs else 'file'} {query!r} under your folders and open it")
    ranked = rank(query, dirs)
    what = decide(ranked)
    if what == "none":
        ui.notify(f"Couldn't find “{query}” in your folders: opening Windows search")
        return search_files(query)
    if what == "pick":
        return offer(query, [p for _, _, p in ranked[:3]])
    hit = ranked[0][2]
    _open(hit)
    ui.notify(f"Opened {Path(hit).name}  ({Path(hit).parent})")


def search_files(query):
    """Explorer's own search over your user folder (uses Windows' index: everything, quickly)."""
    from urllib.parse import quote
    url = f"search-ms:query={quote(query)}&crumb=location:{quote(str(Path.home()))}"
    if CTX.dry:
        return CTX.log(f"  open {url}")
    os.startfile(url)


LATEST = {  # what -> (folders to look in, extensions or None)
    "download": (lambda: [paths.user_folder("downloads")], None),
    "screenshot": (lambda: [paths.user_folder("pictures") / "Screenshots"], (".png", ".jpg", ".jpeg")),
    "clip": (lambda: [paths.user_folder("videos") / "Captures", paths.user_folder("videos")], VIDEO),
    "recording": (lambda: [paths.user_folder("videos") / "Captures", paths.user_folder("videos")], VIDEO),
}


def latest(what, reveal=False):
    """'open my last download' / 'show my last screenshot' (reveal: in Explorer, selected)."""
    folders, exts = LATEST[what]
    if CTX.dry:
        return CTX.log(f"  {'show' if reveal else 'open'} the newest {what}")
    found = [p for p in (newest(f, exts) for f in folders()) if p]
    if not found:
        ui.notify(f"No {what}s found")
        return
    path = max(found, key=os.path.getmtime)
    _open(path, reveal)
    ui.notify(f"{'Showing' if reveal else 'Opened'} {Path(path).name}")
