"""Files by voice: 'find the file budget', 'open my last download', 'show my last screenshot'.

Looks through your own folders (Desktop, Documents, Downloads, Pictures, Videos, Music,
OneDrive), not the whole drive, with a time and size limit so it answers in a second or
two. For a search across everything Windows has indexed: 'search my files for …' opens
Explorer's own search."""
import difflib
import os
import re
import subprocess
import time
from pathlib import Path

from . import paths, ui
from .engine import CTX

SKIP = {"appdata", "node_modules", ".git", "$recycle.bin", "__pycache__", ".cache", "venv", ".venv", "cache"}
PARTIAL = (".crdownload", ".part", ".tmp", ".download", ".partial")
VIDEO = (".mp4", ".mkv", ".webm", ".mov", ".avi")


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


def score(path, query):
    """How well a file name fits what was said: all words in it beats a fuzzy match."""
    name = re.sub(r"[_\-.]+", " ", Path(path).stem.lower())
    q = query.lower().split()
    if not q:
        return 0.0
    hits = sum(1 for w in q if w in name)
    s = hits / len(q) * 2 + difflib.SequenceMatcher(None, " ".join(q), name).ratio()
    return s - len(name) / 400  # shorter names win a tie


def find(query, dirs=False):
    """Best match under your folders, or None."""
    best = None
    for p, mtime in walk(dirs=dirs):
        sc = score(p, query) + min(0.15, max(0.0, (mtime - time.time() + 90 * 86400) / (90 * 86400)) * 0.15)
        if best is None or sc > best[0]:
            best = (sc, p)
    return best[1] if best and best[0] >= 1.2 else None


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
    hit = find(query, dirs)
    if not hit:
        ui.notify(f"Couldn't find “{query}” in your folders: opening Windows search")
        return search_files(query)
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
