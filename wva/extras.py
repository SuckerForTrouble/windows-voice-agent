"""App-specific commands: Spotify, Discord, Stremio, YouTube, Instagram reels / Shorts
and game clips. Shortcuts that only work while an app is focused are sent by
flicking to that app and straight back to where you were."""
import difflib
import json
import re
import threading
import time
import urllib.parse
import urllib.request

from . import apps, config, ui, win
from .actions import CTX, app_windows, fg, fg_title_has, keys, log, open_app, type_text
from .engine import num


def send_to_app(app, combo, label=None, back=True, then=None):
    """Focus the app, press combo (and run `then`), return to the window you were in.
    Starts the app first when it only lives in the tray."""
    exes = set(apps.APP_PROCS[app])
    if CTX.dry:
        log(f"in {app}: keys {combo}")
        if then:
            then()
        return True
    prev = win.foreground()
    ws = app_windows(exes)
    if not ws:
        if not apps.resolve(app):
            ui.notify(f"{label or app.capitalize()} isn't open")
            return False
        open_app(app)  # brings its window back from the tray
        for _ in range(30):
            time.sleep(0.2)
            ws = app_windows(exes)
            if ws:
                break
        else:
            ui.notify(f"{label or app.capitalize()} didn't show a window")
            return False
        time.sleep(0.8)
    target = ws[0]
    if not (prev and prev.hwnd == target.hwnd):
        win.focus(target.hwnd)
        time.sleep(0.25)
    if combo:
        keys(combo)
    if then:
        then()
    if back and prev and prev.hwnd != target.hwnd and win.is_alive(prev.hwnd):
        time.sleep(0.2)
        win.focus(prev.hwnd)
    return True


# ----------------------------------------------------------------- Spotify
# Spotify's own shortcuts (Windows desktop app, 2025): they need its window focused.
def spotify_search(query):
    """Opens Spotify's search results for it (click the top result to play)."""
    uri = "spotify:search:" + urllib.parse.quote(query)
    if CTX.dry:
        return log(f"open {uri}")
    if apps._protocol_registered(uri):
        apps.launch("uri", uri)
    else:  # no Spotify app: the web player
        apps.launch("url", "https://open.spotify.com/search/" + urllib.parse.quote(query))


def spotify_open(what):
    uri = {"liked": "spotify:collection:tracks", "library": "spotify:collection",
           "playlists": "spotify:collection:playlists", "podcasts": "spotify:collection:podcasts"}[what]
    if CTX.dry:
        return log(f"open {uri}")
    apps.launch("uri", uri)


def spotify_like():
    send_to_app("spotify", "alt+shift+b", "Spotify")


def spotify_shuffle():
    send_to_app("spotify", "alt+s", "Spotify")


def spotify_repeat():
    send_to_app("spotify", "alt+r", "Spotify")


# ----------------------------------------------------------------- Discord
def _discord_global(kind):
    combo = config.get(f"discord_{kind}_keys")
    if CTX.dry:
        return log(f"keys {combo} (Discord keybind)")
    keys(combo)


def discord_mute():
    if config.get("discord_keybinds"):
        return _discord_global("mute")
    send_to_app("discord", "ctrl+shift+m", "Discord")


def discord_deafen():
    if config.get("discord_keybinds"):
        return _discord_global("deafen")
    send_to_app("discord", "ctrl+shift+d", "Discord")


def discord_answer():
    send_to_app("discord", "ctrl+enter", "Discord", back=False)


def discord_decline():
    send_to_app("discord", "escape", "Discord")


def discord_goto(name):
    """Quick switcher (Ctrl+K): a server, channel, or friend's DM by name. Stays in Discord."""
    def pick():
        if not CTX.dry:
            time.sleep(0.35)
        type_text(name)
        if not CTX.dry:
            time.sleep(0.6)
        keys("enter")
    send_to_app("discord", "ctrl+k", "Discord", back=False, then=pick)


# ----------------------------------------------------------------- Stremio
CINEMETA = "https://v3-cinemeta.strem.io/catalog/{type}/top/search={q}.json"


def _cinemeta(kind, q):
    url = CINEMETA.format(type=kind, q=urllib.parse.quote(q))
    req = urllib.request.Request(url, headers={"User-Agent": "WindowsVoiceAgent"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.load(r).get("metas") or []


def parse_show(query):
    """'breaking bad season 2 episode 3' / 'season 2 of breaking bad' -> (title, season, episode)."""
    q = re.sub(r"^(?:the (?:movie|film|show|series) )|(?: (?:movie|film|the movie|show|series|tv show))$", "", query.strip())
    m = re.fullmatch(r"(.+?) (?:season|s) (\w+)(?:,? (?:episode|ep|e) (\w+))?", q) or \
        re.fullmatch(r"(?:episode (\w+) of )?season (\w+) of (.+)", q)
    if not m:
        return q, None, None
    if q.startswith(("episode", "season")):
        ep, season, title = m.groups()
    else:
        title, season, ep = m.groups()
    return title, num(season) if season else None, num(ep) if ep else None


def stremio_find(query, kind=None):
    """Find the movie or show and open its page in Stremio, where its streams are listed."""
    title, season, ep = parse_show(query)
    if re.search(r"\b(?:movie|film)\b", query):
        kind = "movie"
    elif re.search(r"\b(?:show|series|season|episode)\b", query):
        kind = "series"
    if CTX.dry:
        return log(f"stremio: {title!r} {kind or 'movie|series'} s{season} e{ep}")
    best = None
    try:
        for t in ([kind] if kind else ["movie", "series"]):
            for i, meta in enumerate(_cinemeta(t, title)[:6]):
                score = difflib.SequenceMatcher(None, apps.norm(meta.get("name", "")), apps.norm(title)).ratio() - i * 0.02
                if best is None or score > best[0] + 0.05:  # a movie wins a tie
                    best = (score, t, meta)
    except Exception as e:
        ui.notify(f"Stremio search failed: {e}")
        return
    use_app = apps.resolve("stremio") and apps.resolve("stremio")[0] != "url"
    if not best or best[0] < 0.45:
        uri = ("stremio:///search?search=" if use_app else "https://web.stremio.com/#/search?search=") + urllib.parse.quote(title)
        apps.launch("uri" if use_app else "url", uri)
        return
    _, t, meta = best
    vid = f"/{meta['id']}:{season}:{ep or 1}" if t == "series" and season else ""
    path = f"/detail/{t}/{meta['id']}{vid}"
    apps.launch("uri", "stremio://" + path) if use_app else apps.launch("url", "https://web.stremio.com/#" + path)
    ui.notify(f"Stremio: {meta.get('name')} ({meta.get('releaseInfo', '')})"
              + (f" S{season}E{ep or 1}" if vid else ""))


# ----------------------------------------------------------------- reels / shorts
def reels_front():
    """Instagram (or YouTube for 'next short') is the window in front."""
    return fg_title_has("instagram")


def shorts_front():
    return fg_title_has("instagram", "youtube")


def reel(direction):
    keys("down" if direction == "next" else "up")


def reel_like():
    """Double-click the middle of the video, like a double tap on the phone."""
    if CTX.dry:
        return log("double-click the middle of the reel")
    w = fg()
    if w:
        x, y, ww, hh = win.rect(w.hwnd)
        win.double_click(x + ww / 2, y + hh / 2)


_scroll = {"on": False, "thread": None}


def doomscroll(seconds=None):
    """Next reel every few seconds until 'stop' (or until you leave the reels)."""
    secs = num(seconds) if seconds else int(config.get("doomscroll_seconds"))
    if CTX.dry:
        return log(f"doom scroll every {secs}s")
    if _scroll["on"]:
        _scroll["secs"] = secs
        return
    _scroll.update(on=True, secs=secs)

    def loop():
        while _scroll["on"]:
            for _ in range(int(_scroll["secs"] * 10)):
                if not _scroll["on"]:
                    return
                time.sleep(0.1)
            if not fg_title_has("instagram", "youtube"):
                _scroll["on"] = False
                ui.notify("Doom scroll stopped")
                return
            keys("down")
    _scroll["thread"] = threading.Thread(target=loop, daemon=True)
    _scroll["thread"].start()
    ui.notify(f"Scrolling every {secs} s, say 'stop' to stop")


def scrolling():
    return _scroll["on"]


def stop_scroll():
    _scroll["on"] = False
    if CTX.dry:
        log("stop doom scroll")


def scroll_instagram(seconds=None):
    """'scroll instagram for me': open reels (unless they're already in front), then doom scroll."""
    if not reels_front():
        open_app("reels")
        if not CTX.dry:
            time.sleep(5)
    doomscroll(seconds)


# ----------------------------------------------------------------- YouTube (in the browser, in front)
def youtube_front():
    return fg_title_has("youtube")


YT_KEYS = {"fullscreen": "f", "theater": "t", "captions": "c", "mute": "m", "faster": "shift+period",
           "slower": "shift+comma", "next": "shift+n", "previous": "shift+p", "miniplayer": "i"}


def youtube(what):
    keys(YT_KEYS[what])


# ----------------------------------------------------------------- game clips (NVIDIA app or Xbox Game Bar)
CLIP_KEYS = {
    "nvidia": {"clip": "alt+f10", "record": "alt+f9", "screenshot": "alt+f1", "overlay": "alt+z", "fps": "alt+r"},
    "xbox": {"clip": "win+alt+g", "record": "win+alt+r", "screenshot": "win+alt+printscreen", "overlay": "win+g",
             "fps": "win+g"},
}


def game_capture(what):
    keys(CLIP_KEYS.get(config.get("clips"), CLIP_KEYS["nvidia"])[what])
