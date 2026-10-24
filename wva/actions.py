"""What the commands do on Windows. Everything that touches the system goes through
a helper here that, in a dry run, prints what it would do instead."""
import re
import subprocess
import sys
import threading
import time
from urllib.parse import quote, quote_plus

from . import apps, ui, win
from .engine import CTX, num

WINDOWS = sys.platform == "win32"
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW


def log(msg):
    if CTX.dry:
        CTX.log(f"  {msg}")


def run(argv, wait=False, timeout=10):
    """A program without a console window popping up."""
    if CTX.dry:
        log("$ " + " ".join(argv))
        return None
    if wait:
        try:
            return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, creationflags=NO_WINDOW)
        except Exception as e:
            ui.notify(f"{argv[0]} failed: {e}")
            return None
    subprocess.Popen(argv, creationflags=NO_WINDOW)
    return None


# ----------------------------------------------------------------- keyboard
KEY_NAMES = {
    "enter": "enter", "return": "enter", "escape": "escape", "esc": "escape", "tab": "tab",
    "space": "space", "spacebar": "space", "space bar": "space", "backspace": "backspace", "back space": "backspace",
    "delete": "delete", "insert": "insert", "up": "up", "down": "down", "left": "left", "right": "right",
    "page up": "pageup", "page down": "pagedown", "home": "home", "end": "end", "print screen": "printscreen",
    "caps lock": "capslock", "windows": "win", "windows key": "win", "win": "win", "start": "win",
    "plus": "plus", "minus": "minus", "period": "period", "dot": "period", "comma": "comma", "slash": "slash",
    **{f"f{i}": f"f{i}" for i in range(1, 25)}, **{f"f {i}": f"f{i}" for i in range(1, 25)},
}
MODIFIERS = {"control": "ctrl", "ctrl": "ctrl", "shift": "shift", "alt": "alt",
             "windows": "win", "win": "win", "super": "win"}


def keys(combo, times=1):
    """'ctrl+shift+t' / 'enter' / 'alt+left' / 'win+d' into the focused window."""
    if CTX.dry:
        log(f"keys {combo}" + (f" x{times}" if times > 1 else ""))
        return
    parsed = win.parse_combo(combo)
    if not parsed:
        ui.notify(f"Unknown key: {combo}")
        return
    win.send_keys(*parsed, times=times)


def type_text(text):
    i = CTX.raw.lower().find(text)  # the words as spoken, with their capitals
    if i >= 0:
        text = CTX.raw[i:i + len(text)]
    if CTX.dry:
        log(f"type {text!r}")
        return
    win.type_unicode(text)


def press(spec):
    """'enter' / 'control shift t' / 'alt f4' / 'down three times'"""
    spec = spec.strip()
    times = 1
    m = re.fullmatch(r"(.+?) (\w+(?: \w+)?) times?", spec)
    if m and num(m.group(2)):
        spec, times = m.group(1), min(num(m.group(2)), 20)
    words = spec.split()
    mods = []
    while len(words) > 1 and words[0] in MODIFIERS:
        mods.append(MODIFIERS[words.pop(0)])
    rest = " ".join(words)
    key = KEY_NAMES.get(rest) or (rest if len(rest) == 1 and rest.isalnum() else None)
    if key is None:
        ui.notify(f"Unknown key: {spec}")
        return
    keys("+".join(mods + [key]), times)


def press_ok(spec):
    spec = re.sub(r" (\w+(?: \w+)?) times?$", "", spec.strip())
    words = spec.split()
    while len(words) > 1 and words[0] in MODIFIERS:
        words.pop(0)
    rest = " ".join(words)
    return rest in KEY_NAMES or (len(rest) == 1 and rest.isalnum())


# ----------------------------------------------------------------- windows of an app
def fg():
    return None if CTX.dry or not WINDOWS else win.foreground()


def fg_title_has(*words):
    """The window in front has one of these words in its title or program name.
    Dry runs (the tests) pretend CTX.front is in front."""
    if CTX.dry or not WINDOWS:
        t = CTX.front or ""
    else:
        w = win.foreground()
        t = (w.title.lower() + " " + w.exe.lower()) if w else ""
    return any(x in t for x in words)


def fg_is(app):
    w = fg()
    return bool(w and w.exe.lower() in apps.APP_PROCS.get(app, []))


_scan = {"t": 0.0, "windows": [], "procs": []}


def scan():
    """Open windows and running process names, reused for 1.5 s: one sentence asks
    'is this app open?' for several rules, and listing processes isn't free."""
    if time.time() - _scan["t"] > 1.5:
        import psutil
        procs = []
        for p in psutil.process_iter(["name"]):
            try:
                procs.append((p.info["name"] or "").lower())
            except Exception:
                continue
        _scan.update(t=time.time(), windows=win.windows(), procs=procs)
    return _scan["windows"], _scan["procs"]


def app_windows(exes):
    return [w for w in win.windows() if w.exe.lower() in exes] if WINDOWS and not CTX.dry else []


def _procs(exes):
    import psutil
    out = []
    for p in psutil.process_iter(["name"]):
        try:
            if (p.info["name"] or "").lower() in exes:
                out.append(p)
        except Exception:
            continue
    return out


def _game_procs():
    """Running games: anything started from a Steam / Epic library folder, or a known game."""
    import psutil
    dirs = apps.game_dirs()
    known = {e for k in ("valorant", "league", "roblox", "minecraft", "fortnite", "gta", "counter strike")
             for e in apps.APP_PROCS[k]}
    out = []
    for p in psutil.process_iter(["name", "exe"]):
        try:
            exe = (p.info["exe"] or "").lower()
            if (p.info["name"] or "").lower() in known or (dirs and any(exe.startswith(d + "\\") for d in dirs)):
                if not exe.endswith(("crashhandler.exe", "unitycrashhandler64.exe", "easyanticheat.exe")):
                    out.append(p)
        except Exception:
            continue
    return out


class Target:
    """An app the user named: its label, its process names, and how it was found."""
    def __init__(self, label, exes, how="table", hwnd=None):
        self.label, self.exes, self.how, self.hwnd = label, set(exes), how, hwnd


WINDOW_WORDS = ("window", "tab", "this", "it", "that", "this window", "this tab", "everything", "all", "all apps",
                "all windows", "left", "right", "up", "down")


def find_target(name):
    """'spotify' / 'the browser' / 'notion' / 'youtube' (a tab title) / 'counter strike' -> Target or None."""
    n = apps.canonical(name)
    if n in WINDOW_WORDS:
        return None
    if n == "browser" or n == "browsers":
        return Target("browser", {e for b in apps.BROWSERS for e in apps.APP_PROCS[b]})
    if n in ("game", "my game", "this game", "games"):
        return Target("game", set(), how="game")
    if n in apps.APP_PROCS:
        return Target(n, apps.APP_PROCS[n])
    if n == "file explorer":
        return Target("File Explorer", {"explorer.exe"}, how="explorer")
    if CTX.dry or not WINDOWS:
        return None
    key = apps.norm(n)
    if len(key) < 3:
        return None
    ws, procs = scan()
    for w in ws:  # by program name: "notion" -> Notion.exe
        a = apps.norm(w.app)
        if a == key or a.replace(" ", "") == key.replace(" ", "") or (len(key) >= 4 and a.startswith(key)):
            return Target(w.app, {w.exe.lower()})
    words = key.split()
    for w in ws:  # by window title: "youtube" -> the browser window showing YouTube
        tw = apps.norm(w.title).split()
        if all(x in tw for x in words):
            return Target(n, {w.exe.lower()}, how="title", hwnd=w.hwnd)
    for nm in procs:  # only in the tray (no window): match the process name
        if nm.endswith(".exe") and nm not in apps.PROTECTED and apps.norm(nm[:-4]).replace(" ", "") == key.replace(" ", ""):
            return Target(nm[:-4], {nm})
    for g in apps.games():  # a game by its library name
        if g.get("dir") and (apps.norm(g["name"]) == key or apps.norm(g["name"]).startswith(key + " ")):
            return Target(g["name"], set(), how="gamedir:" + g["dir"].lower())
    return None


def app_known(name):
    """Guard for close / quit / switch: something we could act on."""
    n = apps.canonical(name)
    if n in WINDOW_WORDS:
        return False
    if CTX.dry or not WINDOWS:
        return n in apps.APP_PROCS or n in ("browser", "game", "file explorer", "my game", "this game")
    return find_target(name) is not None


# ----------------------------------------------------------------- open
CONTEXT = ("youtube", "stremio", "spotify", "amazon", "reddit", "github", "wikipedia", "netflix", "prime video",
           "maps", "google maps", "flipkart", "twitch", "steam", "steam store", "epic", "instagram", "reels")


def can_open(name):
    return apps.resolve(name) is not None


def open_app(name):
    r = apps.resolve(name)
    if not r:
        ui.notify(f"Don't know an app called {name}")
        return
    kind, target, label = r
    CTX.last_target = apps.canonical(name)
    if CTX.dry:
        log(f"open {kind} {target}")
        return
    try:
        apps.launch(kind, target)
    except OSError as e:
        ui.notify(f"Couldn't open {label}: {e}")


def focus_app(name):
    t = find_target(name)
    if not t:
        if can_open(name):
            open_app(name)
        else:
            ui.notify(f"{name} isn't open")
        return
    if CTX.dry:
        log(f"focus {t.label}")
        return
    ws = [w for w in win.windows() if w.hwnd == t.hwnd] if t.hwnd else app_windows(t.exes)
    if ws:
        win.focus(ws[0].hwnd)
    elif can_open(t.label):  # only in the tray: starting it again shows its window
        open_app(t.label)
    else:
        ui.notify(f"{t.label} has no window to show")


def close_app(name):
    """'close spotify': its windows get a polite close, even behind others or minimised.
    When it only lives in the tray (no windows left), it is quit instead. A browser
    tab named by its title ('close youtube') closes just that tab."""
    t = find_target(name)
    if not t:
        ui.notify(f"{name} isn't open")
        return
    if t.how == "game" or t.how.startswith("gamedir:"):
        close_game(t)
        return
    if CTX.dry:
        log(f"close windows of {t.label} ({', '.join(sorted(t.exes))}); quit it if it is only in the tray")
        return
    if t.how == "title" and t.exes & {e for b in apps.BROWSERS for e in apps.APP_PROCS[b]}:
        prev = win.foreground()
        win.focus(t.hwnd)
        time.sleep(0.2)
        keys("ctrl+w")
        if prev and prev.hwnd != t.hwnd and win.is_alive(prev.hwnd):
            time.sleep(0.15)
            win.focus(prev.hwnd)
        return
    if t.how == "explorer":
        ws = [w for w in win.windows() if w.cls == "CabinetWClass"]
    elif t.hwnd:
        ws = [w for w in win.windows() if w.hwnd == t.hwnd]
    else:
        ws = app_windows(t.exes)
    if ws:
        for w in ws:
            win.close(w.hwnd)
        return
    if t.how != "explorer" and _procs(t.exes):
        quit_app(name)
    else:
        ui.notify(f"{t.label} isn't open")


def _terminate(procs, grace=3.0):
    import psutil
    everything = []
    for p in procs:
        try:
            everything += p.children(recursive=True)
        except Exception:
            pass
        everything.append(p)
    everything = [p for p in everything if (p.name() or "").lower() not in apps.PROTECTED]
    for p in everything:
        try:
            p.terminate()
        except Exception:
            pass
    _, alive = psutil.wait_procs(everything, timeout=grace)
    for p in alive:
        try:
            p.kill()
        except Exception:
            pass


def quit_app(name):
    """'quit spotify' / 'close discord from the tray' / 'kill steam': the whole app, tray icon and all."""
    t = find_target(name)
    if not t:
        ui.notify(f"{name} isn't running")
        return
    if t.how == "game" or t.how.startswith("gamedir:"):
        close_game(t)
        return
    if CTX.dry:
        log(f"quit {t.label}: close its windows, then end {', '.join(sorted(t.exes))}")
        return
    if t.label == "steam":
        apps.launch("uri", "steam://exit")  # Steam shuts down cleanly this way
        return
    if t.how == "explorer":
        close_app(name)
        return
    for w in app_windows(t.exes):
        win.close(w.hwnd)
    procs = _procs(t.exes)
    if not procs:
        return
    time.sleep(1.5)  # let it save and exit by itself first
    _terminate([p for p in _procs(t.exes)])


def close_game(t=None):
    """'close the game': the game in front, else the running Steam/Epic game."""
    if CTX.dry:
        log("close the running game (polite close, then end it after 4 s)")
        return
    procs = []
    if t and t.how.startswith("gamedir:"):
        d = t.how.split(":", 1)[1]
        import psutil
        for p in psutil.process_iter(["exe"]):
            try:
                if (p.info["exe"] or "").lower().startswith(d + "\\"):
                    procs.append(p)
            except Exception:
                continue
    else:
        procs = _game_procs()
        f = win.foreground()
        if not procs and f and win.covers_monitor(f.hwnd) and f.exe.lower() not in apps.PROTECTED \
                and f.exe.lower() not in {e for b in apps.BROWSERS for e in apps.APP_PROCS[b]}:
            import psutil
            procs = [psutil.Process(f.pid)]
    if not procs:
        ui.notify("No game is running")
        return
    pids = {p.pid for p in procs}
    for w in win.windows():
        if w.pid in pids:
            win.close(w.hwnd)
    # games often ignore a polite close: whatever is still running after 4 s is ended
    threading.Thread(target=lambda: (time.sleep(4), _terminate([p for p in procs if p.is_running()], 2)),
                     daemon=True).start()


def close_everything():
    """'close everything': a polite close to every app window (apps still ask about unsaved work)."""
    if CTX.dry:
        log("close every app window")
        return
    for w in win.windows():
        if w.exe.lower() not in apps.PROTECTED:
            win.close(w.hwnd)


def minimize_app(name):
    t = find_target(name)
    ws = app_windows(t.exes) if t else []
    if CTX.dry:
        log(f"minimise {name}")
        return
    if not ws:
        ui.notify(f"{name} has no window open")
    for w in ws:
        win.minimize(w.hwnd)


def minimize_others():
    if CTX.dry:
        log("minimise everything except the focused window")
        return
    f = win.foreground()
    for w in win.windows():
        if not f or w.hwnd != f.hwnd:
            win.minimize(w.hwnd)


def list_open():
    if CTX.dry:
        log("list open apps")
        return
    seen = []
    for w in win.windows():
        if w.app and w.app not in seen:
            seen.append(w.app)
    ui.tell("Open: " + ", ".join(seen) if seen else "Nothing is open")


# ----------------------------------------------------------------- search
SEARCH = {
    "web": "https://www.google.com/search?q=", "google": "https://www.google.com/search?q=",
    "duckduckgo": "https://duckduckgo.com/?q=",
    "youtube": "https://www.youtube.com/results?search_query=",
    "wikipedia": "https://en.wikipedia.org/w/index.php?search=",
    "maps": "https://www.google.com/maps/search/", "google maps": "https://www.google.com/maps/search/",
    "github": "https://github.com/search?q=", "amazon": "https://www.amazon.in/s?k=",
    "flipkart": "https://www.flipkart.com/search?q=", "reddit": "https://www.reddit.com/search/?q=",
    "netflix": "https://www.netflix.com/search?q=", "prime video": "https://www.primevideo.com/search/ref=atv_nb_sug?phrase=",
    "twitch": "https://www.twitch.tv/search?term=", "steam": "https://store.steampowered.com/search/?term=",
    "steam store": "https://store.steampowered.com/search/?term=", "epic": "https://store.epicgames.com/browse?q=",
    "chatgpt": "https://chatgpt.com/?q=", "perplexity": "https://www.perplexity.ai/search?q=",
    "images": "https://www.google.com/search?tbm=isch&q=",
}


def web(query, engine=None):
    """'search X': where you are decides — right after 'open stremio' (or with Stremio /
    Spotify / YouTube in front) it searches there, otherwise Google."""
    if engine is None:
        ctx = CTX.last_target
        if ctx is None and WINDOWS and not CTX.dry:
            w = win.foreground()
            t = (w.title.lower() + " " + w.exe.lower()) if w else ""
            ctx = next((k for k, needle in (("stremio", "stremio"), ("spotify", "spotify.exe"),
                                            ("youtube", "youtube")) if needle in t), None)
        if ctx == "stremio":
            from . import extras
            return extras.stremio_find(query)
        if ctx == "spotify":
            from . import extras
            return extras.spotify_search(query)
        if ctx in ("reels", "instagram"):
            ctx = None
        engine = ctx if ctx in SEARCH else "web"
    url = SEARCH[engine] + (quote(query) if engine in ("maps", "google maps") else quote_plus(query))
    if CTX.dry:
        log(f"open {url}")
        return
    apps.launch("url", url)


def windows_search(query):
    keys("win+s")
    if not CTX.dry:
        time.sleep(0.6)
    type_text(query)


# ----------------------------------------------------------------- the focused window
def _fg_or_none():
    if CTX.dry:
        return None
    w = win.foreground()
    if not w:
        ui.notify("No window in front")
    return w


def close_window():
    if CTX.dry:
        return log("close the focused window")
    w = _fg_or_none()
    if w:
        win.close(w.hwnd)


def minimize():
    if CTX.dry:
        return log("minimise the focused window")
    w = _fg_or_none()
    if w:
        win.minimize(w.hwnd)


def maximize():
    if CTX.dry:
        return log("maximise / restore the focused window")
    w = _fg_or_none()
    if w:
        win.toggle_maximize(w.hwnd)


def restore_minimized(all_=False):
    if CTX.dry:
        return log(f"restore {'all minimised windows' if all_ else 'the last minimised window'}")
    hidden = [w for w in win.windows() if w.minimized]
    if not hidden:
        ui.notify("Nothing is minimised")
        return
    for w in (hidden if all_ else hidden[:1]):
        win.restore(w.hwnd)
    win.focus(hidden[0].hwnd)


def topmost():
    if CTX.dry:
        return log("toggle always-on-top")
    w = _fg_or_none()
    if w:
        ui.notify(f"{w.app}: always on top {'on' if win.toggle_topmost(w.hwnd) else 'off'}")


PLACES = {  # name -> (x, y, w, h) as fractions of the work area
    "left": (0, 0, .5, 1), "right": (.5, 0, .5, 1), "top": (0, 0, 1, .5), "bottom": (0, .5, 1, .5),
    "top left": (0, 0, .5, .5), "top right": (.5, 0, .5, .5), "bottom left": (0, .5, .5, .5),
    "bottom right": (.5, .5, .5, .5), "centre": (.2, .15, .6, .7), "middle": (.2, .15, .6, .7),
}


def place(where):
    where = re.sub(r"\bupper\b", "top", re.sub(r"\blower\b", "bottom", where)).replace("center", "centre")
    fx, fy, fw, fh = PLACES[where]
    if CTX.dry:
        return log(f"place window {where}: {fx, fy, fw, fh} of the work area")
    w = _fg_or_none()
    if not w:
        return
    ax, ay, aw, ah = win.work_area(w.hwnd)
    win.move(w.hwnd, ax + aw * fx, ay + ah * fy, aw * fw, ah * fh)


SIZE_VERB = {
    "shrink": "shrink", "smaller": "shrink", "reduce": "shrink", "decrease": "shrink", "tinier": "shrink",
    "grow": "grow", "bigger": "grow", "larger": "grow", "enlarge": "grow", "expand": "grow",
    "increase": "grow", "raise": "grow", "embiggen": "grow",
    "wider": "wider", "widen": "wider", "broader": "wider",
    "narrower": "narrower", "narrow": "narrower", "thinner": "narrower", "slimmer": "narrower",
    "taller": "taller", "longer": "taller", "shorter": "shorter", "squash": "shorter",
}
SIZE_WORDS = "|".join(sorted(SIZE_VERB, key=len, reverse=True))
AMOUNT = (r"(a (?:little )?bit|a little|a tiny bit|slightly|a touch|a lot|much|way|a ton|a bunch|"
          r"(?:by )?\w+(?: \w+)?(?: percent|%))")


def _amount(word):
    if not word:
        return 10
    w = re.sub(r"^by |(?: percent|%)$", "", word.strip())
    if w in ("a bit", "a little bit", "a little", "a tiny bit", "slightly", "a touch"):
        return 5
    if w in ("a lot", "much", "way", "a ton", "a bunch"):
        return 25
    return num(w)


def size_ok(*words):
    verbs = [w for w in words if w in SIZE_VERB]
    rest = [w for w in words if w not in SIZE_VERB]
    return len(verbs) == 1 and all(_amount(w) is not None and 0 < _amount(w) <= 90 for w in rest)


def resize_cmd(*words):
    """'make it a little smaller' / 'wider by 20 percent': scales about the window's centre."""
    how = SIZE_VERB[next(w for w in words if w in SIZE_VERB)]
    pct = _amount(next((w for w in words if w not in SIZE_VERB), None))
    if CTX.dry:
        return log(f"resize {how} {pct}%")
    w = _fg_or_none()
    if not w:
        return
    f = 1 + pct / 100 if how in ("grow", "wider", "taller") else 1 - pct / 100
    fx = f if how in ("wider", "narrower", "grow", "shrink") else 1
    fy = f if how in ("taller", "shorter", "grow", "shrink") else 1
    x, y, ww, hh = win.rect(w.hwnd)
    ax, ay, aw, ah = win.work_area(w.hwnd)
    nw, nh = min(aw, max(300, ww * fx)), min(ah, max(200, hh * fy))
    nx, ny = max(ax, x + (ww - nw) / 2), max(ay, y + (hh - nh) / 2)
    win.move(w.hwnd, nx, ny, nw, nh)


def _desktops():
    """(current index, count) of the virtual desktops, read from the registry."""
    try:
        import winreg
        base = r"Software\Microsoft\Windows\CurrentVersion\Explorer\VirtualDesktops"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base) as k:
            ids = winreg.QueryValueEx(k, "VirtualDesktopIDs")[0]
            try:
                cur = winreg.QueryValueEx(k, "CurrentVirtualDesktop")[0]
            except OSError:  # Windows 10 keeps it per session
                import ctypes
                sid = ctypes.c_ulong()
                ctypes.windll.kernel32.ProcessIdToSessionId(ctypes.windll.kernel32.GetCurrentProcessId(), ctypes.byref(sid))
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                    rf"Software\Microsoft\Windows\CurrentVersion\Explorer\SessionInfo\{sid.value}\VirtualDesktops") as s:
                    cur = winreg.QueryValueEx(s, "CurrentVirtualDesktop")[0]
        chunks = [ids[i:i + 16] for i in range(0, len(ids), 16)]
        return chunks.index(cur), len(chunks)
    except Exception:
        return None


def desktop(n):
    """'desktop 3': step there with Ctrl+Win+arrows (Windows has no direct jump)."""
    target = num(n) - 1
    if CTX.dry:
        return log(f"virtual desktop {target + 1}")
    d = _desktops()
    if not d:
        keys("ctrl+win+left", 9)
        keys("ctrl+win+right", target)
        return
    cur, count = d
    if target >= count:
        ui.notify(f"There are only {count} desktops")
        return
    step = target - cur
    if step:
        keys("ctrl+win+right" if step > 0 else "ctrl+win+left", abs(step))


# ----------------------------------------------------------------- sound
def _audio():
    from . import audio
    return audio


def _media_keys_volume(direction, pct):
    keys("volumeup" if direction == "up" else "volumedown", max(1, round(pct / 2)))  # one press = 2%


def volume_step(direction, amount="5"):
    step = num(amount) or 5
    if CTX.dry:
        return log(f"volume {direction} {step}%")
    try:
        a = _audio()
        a.set_volume(max(0, min(100, a.get_volume() + (step if direction == "up" else -step))))
    except Exception:
        _media_keys_volume(direction, step)


def vol_ok(n):
    v = num(n)
    return v is not None and 0 <= v <= 100


def volume_set(n):
    v = num(n)
    if CTX.dry:
        return log(f"volume {v}%")
    try:
        _audio().set_volume(v)
    except Exception:
        keys("volumedown", 50)
        keys("volumeup", round(v / 2))


def mute_sound(state=None):
    if CTX.dry:
        return log(f"speakers mute {state}")
    try:
        _audio().set_mute(state)
    except Exception:
        keys("volumemute")


def mute_mic():
    if CTX.dry:
        return log("toggle mic mute")
    try:
        ui.notify("Mic muted" if _audio().toggle_mic_mute() else "Mic on")
    except Exception as e:
        ui.notify(f"Couldn't reach the mic: {e}")


APP_SOUND = ("spotify", "discord", "chrome", "edge", "firefox", "brave", "opera", "zen", "stremio", "vlc",
             "steam", "whatsapp", "telegram", "game", "browser", "valorant", "roblox", "minecraft", "teams", "zoom")


def sound_app(name):
    n = apps.canonical(re.sub(r"^(?:the|my) ", "", name.strip()))
    return n if n in APP_SOUND else None


def _sound_exes(n):
    if n == "browser":
        return {e for b in apps.BROWSERS for e in apps.APP_PROCS[b]}
    if n == "game":
        return {p.name().lower() for p in _game_procs()}
    return set(apps.APP_PROCS[n])


def app_volume(name, spec):
    n = sound_app(name)
    spec = {"louder": "up", "quieter": "down", "softer": "down"}.get(spec, spec)
    if spec not in ("up", "down"):
        spec = num(spec)
    if CTX.dry:
        return log(f"{n} volume {spec}")
    try:
        level = _audio().app_volume(_sound_exes(n), spec)
    except Exception as e:
        ui.notify(f"Couldn't change {n}'s volume: {e}")
        return
    ui.notify(f"{n.capitalize()} volume {level}%" if level is not None else f"{n.capitalize()} isn't making any sound")


def app_mute(state, name):
    n = sound_app(name)
    on = state in ("mute", "silence")
    if CTX.dry:
        return log(f"{'mute' if on else 'unmute'} {n}'s sound")
    try:
        if not _audio().app_mute(_sound_exes(n), on):
            ui.notify(f"{n.capitalize()} isn't making any sound")
    except Exception as e:
        ui.notify(f"Couldn't mute {n}: {e}")


# ----------------------------------------------------------------- media
def _media():
    from . import media
    return media if media.AVAILABLE else None


def media(action, app=None):
    """pause/next/previous act on everything that plays; play resumes what 'pause' stopped."""
    action = {"resume": "play", "unpause": "play", "skip": "next", "last": "previous"}.get(action, action)
    if CTX.dry:
        return log(f"media {action}" + (f" on {app}" if app else ""))
    m = _media()
    if m:
        try:
            if m.control(action, app) is not None:
                return
            if app:
                ui.notify(f"{app.capitalize()} isn't playing anything")
                return
            if action in ("pause", "play"):
                ui.notify("Nothing is playing" if action == "pause" else "Nothing to resume")
                return
        except Exception:
            pass
    keys({"pause": "mediaplay", "play": "mediaplay", "toggle": "mediaplay", "next": "medianext",
          "previous": "mediaprev", "stop": "mediastop"}[action])


def seek(direction, amount="10", unit="second"):
    secs = (num(amount) or 10) * (60 if unit.startswith("minute") else 1)
    back = direction not in ("forward", "ahead")
    if CTX.dry:
        return log(f"seek {'-' if back else '+'}{secs}s")
    if fg_title_has("youtube"):  # YouTube: J / L = 10 s
        keys("j" if back else "l", max(1, round(secs / 10)))
        return
    m = _media()
    try:
        if m and m.seek(delta=-secs if back else secs):
            return
    except Exception:
        pass
    ui.notify("This player doesn't allow skipping from outside")


def seek_abs(n, unit, extra=None):
    secs = num(n) * (60 if unit.startswith("minute") else 1) + (num(extra) if extra and num(extra) else 0)
    if CTX.dry:
        return log(f"seek to {secs}s")
    m = _media()
    try:
        if m and m.seek(absolute=secs):
            return
    except Exception:
        pass
    ui.notify("This player doesn't allow seeking from outside")


def now_playing(app=None):
    if CTX.dry:
        return log("what's playing")
    m = _media()
    np = None
    try:
        np = m.now_playing(app) if m else None
    except Exception:
        pass
    if not np:
        ui.tell("Nothing is playing")
        return
    title, artist, src, playing = np
    ui.tell(f"{title} · {artist}" + ("" if playing else " (paused)"), f"{title}, by {artist}" if artist else title)
