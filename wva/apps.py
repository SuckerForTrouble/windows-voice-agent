"""What "open X" / "close X" / "switch to X" can mean: apps from the Start menu (and
Store apps), Steam and Epic games, websites, folders and Windows settings pages,
plus which processes belong to an app so it can be closed even from the tray."""
import difflib
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import paths

WINDOWS = sys.platform == "win32"

# spoken -> candidates, first one that exists wins
#   app:<Start menu name>   uri:<protocol link>   exe:<program>   url:<web page>
#   folder:<known folder>   path:<file system path>
APPS = {
    "browser": ["url:https://www.google.com"], "web browser": ["url:https://www.google.com"],
    "internet": ["url:https://www.google.com"],
    "chrome": ["app:Google Chrome", "exe:chrome.exe"], "google chrome": ["app:Google Chrome", "exe:chrome.exe"],
    "edge": ["app:Microsoft Edge", "exe:msedge.exe"], "microsoft edge": ["app:Microsoft Edge", "exe:msedge.exe"],
    "firefox": ["app:Firefox", "exe:firefox.exe"], "brave": ["app:Brave", "exe:brave.exe"],
    "opera": ["app:Opera GX Browser", "app:Opera Browser", "exe:opera.exe"], "opera gx": ["app:Opera GX Browser"],
    "spotify": ["app:Spotify", "uri:spotify:", "url:https://open.spotify.com"],
    "discord": ["app:Discord", "uri:discord://", "url:https://discord.com/app"],
    "stremio": ["app:Stremio", "uri:stremio:///", "url:https://web.stremio.com"],
    "whatsapp": ["app:WhatsApp", "uri:whatsapp:", "url:https://web.whatsapp.com"],
    "telegram": ["app:Telegram Desktop", "uri:tg://", "url:https://web.telegram.org"],
    "steam": ["uri:steam://open/main", "url:https://store.steampowered.com"], "steam library": ["uri:steam://open/games", "url:https://store.steampowered.com"],
    "steam friends": ["uri:steam://open/friends", "url:https://steamcommunity.com"], "steam downloads": ["uri:steam://open/downloads", "url:https://store.steampowered.com"],
    "epic": ["app:Epic Games Launcher", "uri:com.epicgames.launcher://", "url:https://store.epicgames.com"],
    "epic games": ["app:Epic Games Launcher", "uri:com.epicgames.launcher://", "url:https://store.epicgames.com"],
    "xbox": ["app:Xbox", "uri:xbox:", "url:https://www.xbox.com"], "game bar": ["uri:ms-gamebar:"],
    "vs code": ["app:Visual Studio Code", "exe:code"], "obs": ["app:OBS Studio"],
    "file explorer": ["exe:explorer.exe"], "explorer": ["exe:explorer.exe"], "files": ["exe:explorer.exe"],
    "my files": ["exe:explorer.exe"], "this pc": ["exe:explorer.exe"],
    "task manager": ["exe:taskmgr.exe"], "control panel": ["exe:control.exe"],
    "terminal": ["app:Terminal", "exe:wt.exe", "exe:cmd.exe"], "command prompt": ["exe:cmd.exe"], "cmd": ["exe:cmd.exe"],
    "powershell": ["exe:powershell.exe"], "notepad": ["exe:notepad.exe"], "calculator": ["exe:calc.exe"],
    "paint": ["exe:mspaint.exe"], "snipping tool": ["app:Snipping Tool", "uri:ms-screenclip:"],
    "camera": ["uri:microsoft.windows.camera:"], "photos": ["uri:ms-photos:"], "clock": ["uri:ms-clock:"],
    "alarms": ["uri:ms-clock:"], "store": ["uri:ms-windows-store:"], "microsoft store": ["uri:ms-windows-store:"],
    "recycle bin": ["path:shell:RecycleBinFolder"],
    "settings": ["uri:ms-settings:"], "windows settings": ["uri:ms-settings:"],
    "display settings": ["uri:ms-settings:display"], "screen settings": ["uri:ms-settings:display"],
    "sound settings": ["uri:ms-settings:sound"], "audio settings": ["uri:ms-settings:sound"],
    "volume mixer": ["uri:ms-settings:apps-volume"], "mixer": ["uri:ms-settings:apps-volume"],
    "bluetooth settings": ["uri:ms-settings:bluetooth"], "wifi settings": ["uri:ms-settings:network-wifi"],
    "network settings": ["uri:ms-settings:network"], "internet settings": ["uri:ms-settings:network"],
    "windows update": ["uri:ms-settings:windowsupdate"], "updates": ["uri:ms-settings:windowsupdate"],
    "apps settings": ["uri:ms-settings:appsfeatures"], "installed apps": ["uri:ms-settings:appsfeatures"],
    "startup apps": ["uri:ms-settings:startupapps"], "storage settings": ["uri:ms-settings:storagesense"],
    "night light": ["uri:ms-settings:nightlight"], "mouse settings": ["uri:ms-settings:mousetouchpad"],
    "keyboard settings": ["uri:ms-settings:keyboard"], "power settings": ["uri:ms-settings:powersleep"],
    "battery settings": ["uri:ms-settings:batterysaver"], "notification settings": ["uri:ms-settings:notifications"],
    "graphics settings": ["uri:ms-settings:display-advancedgraphics"], "game mode": ["uri:ms-settings:gaming-gamemode"],
    "privacy settings": ["uri:ms-settings:privacy"], "wallpaper settings": ["uri:ms-settings:personalization-background"],
    "personalization": ["uri:ms-settings:personalization"], "date and time settings": ["uri:ms-settings:dateandtime"],
    "downloads": ["folder:downloads"], "downloads folder": ["folder:downloads"], "my downloads": ["folder:downloads"],
    "documents": ["folder:documents"], "documents folder": ["folder:documents"],
    "desktop folder": ["folder:desktop"], "pictures": ["folder:pictures"], "pictures folder": ["folder:pictures"],
    "screenshots": ["folder:screenshots"], "screenshots folder": ["folder:screenshots"],
    "music folder": ["folder:music"], "videos": ["folder:videos"], "videos folder": ["folder:videos"],
}

SITES = {
    "youtube": "https://www.youtube.com", "youtube shorts": "https://www.youtube.com/shorts", "shorts": "https://www.youtube.com/shorts",
    "github": "https://github.com", "gmail": "https://mail.google.com", "mail": "https://mail.google.com",
    "email": "https://mail.google.com", "maps": "https://www.google.com/maps", "google maps": "https://www.google.com/maps",
    "discord web": "https://discord.com/app", "reddit": "https://www.reddit.com",
    "twitter": "https://x.com", "x": "https://x.com", "instagram": "https://www.instagram.com",
    "instagram reels": "https://www.instagram.com/reels/", "reels": "https://www.instagram.com/reels/",
    "facebook": "https://www.facebook.com", "pinterest": "https://www.pinterest.com",
    "whatsapp web": "https://web.whatsapp.com", "chatgpt": "https://chatgpt.com", "gemini": "https://gemini.google.com",
    "claude": "https://claude.ai", "perplexity": "https://www.perplexity.ai",
    "netflix": "https://www.netflix.com", "prime video": "https://www.primevideo.com", "amazon prime": "https://www.primevideo.com",
    "hotstar": "https://www.hotstar.com", "jio hotstar": "https://www.hotstar.com", "crunchyroll": "https://www.crunchyroll.com",
    "stremio web": "https://web.stremio.com", "amazon": "https://www.amazon.in", "flipkart": "https://www.flipkart.com",
    "google": "https://www.google.com", "drive": "https://drive.google.com", "google drive": "https://drive.google.com",
    "google photos": "https://photos.google.com", "calendar": "https://calendar.google.com",
    "translate": "https://translate.google.com", "google translate": "https://translate.google.com",
    "stackoverflow": "https://stackoverflow.com", "linkedin": "https://www.linkedin.com",
    "wikipedia": "https://en.wikipedia.org", "spotify web": "https://open.spotify.com",
    "youtube music": "https://music.youtube.com", "twitch": "https://www.twitch.tv", "kick": "https://kick.com",
    "steam store": "https://store.steampowered.com", "epic store": "https://store.epicgames.com",
    "speed test": "https://www.speedtest.net", "speedtest": "https://www.speedtest.net",
    "chess": "https://www.chess.com", "lichess": "https://lichess.org", "monkeytype": "https://monkeytype.com",
}

TLDS = "com|org|net|io|dev|in|co|app|ai|me|tv|gg|xyz|sh|so|to"

# Which processes make up an app: for close / quit from the tray / switch to / app volume.
APP_PROCS = {
    "spotify": ["spotify.exe"], "discord": ["discord.exe", "discordptb.exe", "discordcanary.exe", "vesktop.exe"],
    "chrome": ["chrome.exe"], "edge": ["msedge.exe"], "firefox": ["firefox.exe"], "brave": ["brave.exe"],
    "opera": ["opera.exe", "opera_gx.exe"], "zen": ["zen.exe"],
    "steam": ["steam.exe", "steamwebhelper.exe"], "epic": ["epicgameslauncher.exe", "epicwebhelper.exe"],
    "stremio": ["stremio.exe", "stremio-shell-ng.exe", "stremio-runtime.exe", "stremio-service.exe"],
    "whatsapp": ["whatsapp.exe", "whatsapp.root.exe"], "telegram": ["telegram.exe"],
    "obs": ["obs64.exe"], "vlc": ["vlc.exe"], "vs code": ["code.exe"], "notepad": ["notepad.exe"],
    "task manager": ["taskmgr.exe"], "teams": ["ms-teams.exe", "teams.exe"], "zoom": ["zoom.exe"],
    "riot": ["riotclientservices.exe", "riot client.exe", "riotclientux.exe"],
    "valorant": ["valorant-win64-shipping.exe", "valorant.exe"], "league": ["leagueclient.exe", "league of legends.exe"],
    "battle net": ["battle.net.exe"], "ea": ["eadesktop.exe", "eabackgroundservice.exe"], "ubisoft": ["upc.exe", "ubisoftconnect.exe"],
    "xbox": ["xboxpcapp.exe"], "wallpaper engine": ["wallpaper32.exe", "wallpaper64.exe"],
    "afterburner": ["msiafterburner.exe"], "rivatuner": ["rtss.exe"], "qbittorrent": ["qbittorrent.exe"],
    "utorrent": ["utorrent.exe"], "onedrive": ["onedrive.exe"], "word": ["winword.exe"], "excel": ["excel.exe"],
    "powerpoint": ["powerpnt.exe"], "roblox": ["robloxplayerbeta.exe"],
    "minecraft": ["minecraft.windows.exe", "minecraftlauncher.exe"], "fortnite": ["fortniteclient-win64-shipping.exe"],
    "gta": ["gta5.exe", "gta5_enhanced.exe", "playgtav.exe"], "counter strike": ["cs2.exe"],
    "calculator": ["calculatorapp.exe"], "settings": ["systemsettings.exe"], "paint": ["mspaint.exe"],
    "nvidia app": ["nvidia app.exe"], "terminal": ["windowsterminal.exe"], "photos": ["photos.exe"],
}
SPOKEN = {
    "google chrome": "chrome", "microsoft edge": "edge", "mozilla firefox": "firefox", "opera gx": "opera",
    "brave browser": "brave", "code": "vs code", "visual studio code": "vs code", "epic games": "epic",
    "epic games launcher": "epic", "epic launcher": "epic", "riot client": "riot", "league of legends": "league",
    "lol": "league", "battlenet": "battle net", "battle dot net": "battle net", "blizzard": "battle net",
    "ea app": "ea", "origin": "ea", "ubisoft connect": "ubisoft", "uplay": "ubisoft", "counter strike 2": "counter strike",
    "cs2": "counter strike", "cs": "counter strike", "cs go": "counter strike", "grand theft auto": "gta", "gta 5": "gta",
    "gta v": "gta", "gta five": "gta", "obs studio": "obs", "msi afterburner": "afterburner", "whatsapp desktop": "whatsapp",
    "spotify app": "spotify", "discord app": "discord", "steam app": "steam", "explorer": "file explorer",
    "files": "file explorer", "file manager": "file explorer", "windows terminal": "terminal", "the game": "game",
}
BROWSERS = ("chrome", "edge", "firefox", "brave", "opera", "zen")
# Never closed or killed, whatever the name sounds like.
PROTECTED = {"explorer.exe", "csrss.exe", "winlogon.exe", "wininit.exe", "services.exe", "lsass.exe", "smss.exe",
             "svchost.exe", "dwm.exe", "system", "registry", "fontdrvhost.exe", "sihost.exe", "ctfmon.exe",
             "audiodg.exe", "searchhost.exe", "startmenuexperiencehost.exe", "shellexperiencehost.exe",
             "runtimebroker.exe", "taskhostw.exe", "conhost.exe", "whisper-server.exe", "windowsvoiceagent.exe",
             "securityhealthsystray.exe", "msmpeng.exe", "textinputhost.exe", "applicationframehost.exe"}


def norm(s):
    s = re.sub(r"[^a-z0-9]+", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def strip_name(name):
    name = re.sub(r"^(?:the|my|a|an|up) ", "", name.strip())
    return re.sub(r" (?:app|application|program|website|web site|site|page|for me|window|windows|client)$", "", name)


def canonical(name):
    n = strip_name(name)
    return SPOKEN.get(n, n)


# ----------------------------------------------------------------- Start menu index
_START = None
_START_LOCK = threading.Lock()


def _scan_shortcuts():
    """Start menu .lnk files: {name: path}. Fast fallback while Get-StartApps runs."""
    out = {}
    roots = [Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
             Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs"]
    for root in roots:
        for dirpath, _, files in os.walk(root):
            for f in files:
                if f.lower().endswith((".lnk", ".url")):
                    stem = f.rsplit(".", 1)[0]
                    if re.search(r"uninstall|readme|help|website|documentation|release notes|license", stem, re.I):
                        continue
                    out.setdefault(stem, os.path.join(dirpath, f))
    return out


def _refresh_start_apps():
    """Get-StartApps knows Store apps too (Spotify/WhatsApp from the Store have no .lnk)."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"],
                           capture_output=True, text=True, timeout=60, creationflags=0x08000000)
        rows = json.loads(r.stdout or "[]")
        if isinstance(rows, dict):
            rows = [rows]
        data = {"t": time.time(), "apps": {row["Name"]: row["AppID"] for row in rows if row.get("Name") and row.get("AppID")}}
        paths.ensure()
        paths.APPS_CACHE.write_text(json.dumps(data), encoding="utf-8")
        global _START
        with _START_LOCK:
            _START = None
    except Exception:
        pass


def warm_up():
    """At start-up: refresh the Store-app list in the background once a day."""
    if not WINDOWS:
        return
    try:
        fresh = time.time() - json.loads(paths.APPS_CACHE.read_text(encoding="utf-8"))["t"] < 86400
    except (OSError, ValueError, KeyError):
        fresh = False
    if not fresh:
        threading.Thread(target=_refresh_start_apps, daemon=True).start()


def start_apps():
    """{display name: ("aumid", AppID) | ("lnk", path)}"""
    global _START
    with _START_LOCK:
        if _START is not None:
            return _START
        out = {}
        if WINDOWS:
            for name, p in _scan_shortcuts().items():
                out[name] = ("lnk", p)
            try:
                for name, aid in json.loads(paths.APPS_CACHE.read_text(encoding="utf-8"))["apps"].items():
                    out.setdefault(name, ("aumid", aid))
            except (OSError, ValueError, KeyError):
                pass
            for g in games():
                out.setdefault(g["name"], ("uri", g["uri"]))
        _START = out
        return out


def exact_start_app(name):
    """An installed app called exactly this ('instagram' -> the Instagram app), else None."""
    n = norm(name)
    return next((k for k in start_apps() if norm(k) == n), None) if n else None


def find_start_app(name):
    apps = start_apps()
    if not apps:
        return None
    by_norm = {}
    for k in apps:
        by_norm.setdefault(norm(k), k)
    n = norm(name)
    if not n:
        return None
    if n in by_norm:
        return by_norm[n]
    words = n.split()
    best = None
    for key, real in by_norm.items():
        kw = key.split()
        if key.startswith(n + " ") or (len(words) > 1 and all(w in kw for w in words)) or \
                (len(n) >= 4 and key.replace(" ", "") == n.replace(" ", "")):
            if best is None or len(key) < len(best[0]):
                best = (key, real)
    if best:
        return best[1]
    if len(n) >= 5:
        close = difflib.get_close_matches(n, by_norm, n=1, cutoff=0.85)
        if close:
            return by_norm[close[0]]
    return None


# ----------------------------------------------------------------- games
_GAMES = None


def games():
    """Installed Steam and Epic games: [{name, uri, dir}]."""
    global _GAMES
    if _GAMES is not None or not WINDOWS:
        return _GAMES or []
    out = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            steam = Path(winreg.QueryValueEx(k, "SteamPath")[0])
        libs = {steam}
        vdf = (steam / "steamapps/libraryfolders.vdf").read_text(encoding="utf-8", errors="replace")
        libs |= {Path(p.replace("\\\\", "\\")) for p in re.findall(r'"path"\s+"([^"]+)"', vdf)}
        for lib in libs:
            for acf in (lib / "steamapps").glob("appmanifest_*.acf"):
                t = acf.read_text(encoding="utf-8", errors="replace")
                name, appid = re.search(r'"name"\s+"([^"]+)"', t), re.search(r'"appid"\s+"(\d+)"', t)
                inst = re.search(r'"installdir"\s+"([^"]+)"', t)
                if name and appid and not re.search(r"redistributable|steamworks|proton|runtime", name.group(1), re.I):
                    out.append({"name": name.group(1), "uri": f"steam://rungameid/{appid.group(1)}",
                                "dir": str(lib / "steamapps/common" / inst.group(1)) if inst else ""})
    except Exception:
        pass
    try:
        man = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Epic/EpicGamesLauncher/Data/Manifests"
        for item in man.glob("*.item"):
            d = json.loads(item.read_text(encoding="utf-8", errors="replace"))
            if d.get("DisplayName") and d.get("AppName"):
                out.append({"name": d["DisplayName"],
                            "uri": f"com.epicgames.launcher://apps/{d['AppName']}?action=launch&silent=true",
                            "dir": d.get("InstallLocation", "")})
    except Exception:
        pass
    _GAMES = out
    return out


def game_dirs():
    return [g["dir"].lower() for g in games() if g.get("dir")]


# ----------------------------------------------------------------- resolving "open X"
def domain_url(name):
    """'reddit dot com' / 'news ycombinator com' / 'example dot org slash wiki' -> url"""
    m = re.fullmatch(rf"([a-z0-9][a-z0-9 -]*?) (?:dot )?({TLDS})((?: slash [a-z0-9]+)*)", name)
    if not m:
        return None
    host = re.sub(r"\s+dot\s+|\s+", ".", m.group(1).strip()) if " dot " in m.group(1) else m.group(1).replace(" ", "")
    path = m.group(3).replace(" slash ", "/")
    return f"https://{host}.{m.group(2)}{path}"


def _protocol_registered(uri):
    if not WINDOWS:
        return True
    scheme = uri.split(":", 1)[0]
    if scheme in ("ms-settings", "ms-windows-store", "ms-photos", "ms-clock", "ms-screenclip", "ms-gamebar",
                  "microsoft.windows.camera", "xbox"):
        return True
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, scheme))
        return True
    except OSError:
        return False


def resolve(name):
    """Spoken name -> (kind, target, label) or None.
    kind: aumid | lnk | uri | url | exe | path"""
    n = strip_name(name)
    if n in ("browser", "web browser", "internet"):  # the browser picked in Settings, if any
        from . import config
        if config.get("browser") and config.get("browser") in APPS:
            n = config.get("browser")
    for cand in APPS.get(n, []):
        kind, _, target = cand.partition(":")
        if kind == "app":
            real = find_start_app(target) if WINDOWS else None
            if real:
                k, t = start_apps()[real]
                return k, t, real
        elif kind == "uri":
            if _protocol_registered(target):
                return "uri", target, n
        elif kind == "exe":
            return "exe", target, n
        elif kind == "url":
            return "url", target, n
        elif kind == "folder":
            p = paths.user_folder("pictures") / "Screenshots" if target == "screenshots" else paths.user_folder(target)
            return "path", str(p), n
        elif kind == "path":
            return "path", target, n
    # An installed app beats our website for the same name: with the Instagram, Netflix or
    # ChatGPT app installed, "open instagram" opens the app (it opened instagram.com before).
    real = exact_start_app(n) if WINDOWS and n in SITES else None
    if real:
        k, t = start_apps()[real]
        return k, t, real
    if n in SITES:
        return "url", SITES[n], n
    url = domain_url(n)
    if url:
        return "url", url, n
    real = find_start_app(n) if WINDOWS else None
    if real:
        k, t = start_apps()[real]
        return k, t, real
    return None


def launch(kind, target):
    if kind == "aumid":
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{target}"], creationflags=0x08000000)
    elif kind == "exe":
        try:
            os.startfile(target)
        except OSError:
            subprocess.Popen(target, shell=True, creationflags=0x08000000)
    elif kind == "path" and target.startswith("shell:"):
        subprocess.Popen(["explorer.exe", target], creationflags=0x08000000)
    else:  # lnk, uri, url, path
        os.startfile(target)
