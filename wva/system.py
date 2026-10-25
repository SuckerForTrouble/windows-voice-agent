"""System commands, questions (time, weather, RAM, GPU…) and timers."""
import json
import os
import re
import shutil
import socket
import threading
import time
import uuid
from datetime import datetime

from . import config, paths, ui, win
from .actions import CTX, keys, log, run
from .engine import fmt_dur, num, parse_duration


# ----------------------------------------------------------------- capture & power
def screenshot(kind="region"):
    if kind == "window":
        keys("alt+printscreen")
        ui.notify("Window screenshot copied, paste it anywhere")
    elif kind == "full":
        keys("win+printscreen")  # saved to Pictures\Screenshots
        ui.notify("Saved to Pictures > Screenshots")
    else:
        keys("win+shift+s")


def lock():
    if CTX.dry:
        return log("lock the PC")
    win.lock()


def sleep_pc():
    if CTX.dry:
        return log("sleep")
    ui.notify("Going to sleep")
    time.sleep(1)
    import ctypes
    ctypes.windll.powrprof.SetSuspendState(0, 1, 0)


def shutdown(kind="shutdown", minutes=None):
    """Shut down / restart with a grace period; 'cancel shutdown' stops it."""
    secs = 30 if minutes is None else int(minutes * 60)
    flag = {"shutdown": "/s", "restart": "/r"}[kind]
    run(["shutdown", flag, "/t", str(secs)])
    ui.tell(f"{'Restarting' if kind == 'restart' else 'Shutting down'} in {fmt_dur(secs)}. Say 'cancel shutdown' to stop it.")


def cancel_shutdown():
    run(["shutdown", "/a"])
    ui.notify("Shutdown cancelled")


def sign_out():
    run(["shutdown", "/l"])


def restart_explorer():
    """Fixes a frozen taskbar / Start menu."""
    run(["taskkill", "/f", "/im", "explorer.exe"], wait=True)
    if not CTX.dry:
        time.sleep(1)
    run(["explorer.exe"])


# ----------------------------------------------------------------- display & radios
def _ps(script, timeout=10):
    return run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], wait=True, timeout=timeout)


def brightness(spec):
    """Laptop screens only (external monitors don't take it from Windows)."""
    if CTX.dry:
        return log(f"brightness {spec}")
    r = _ps("(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness")
    try:
        cur = int((r.stdout or "").split()[0])
    except (AttributeError, ValueError, IndexError):
        ui.notify("This screen's brightness can't be changed from Windows (use the monitor's buttons)")
        return
    new = cur + 10 if spec == "up" else cur - 10 if spec == "down" else num(spec)
    new = max(0, min(100, new))
    _ps(f"(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1,{new})")
    ui.notify(f"Brightness {new}%")


def radio(what, state):
    """Wi-Fi / Bluetooth on or off (Windows radio switches); the settings page if that fails."""
    on = state in ("on", "enable", "connect")
    if CTX.dry:
        return log(f"{what} {'on' if on else 'off'}")
    try:
        import asyncio

        from winrt.windows.devices.radios import Radio, RadioKind, RadioState

        async def go():
            await Radio.request_access_async()
            kind = RadioKind.BLUETOOTH if what == "bluetooth" else RadioKind.WI_FI
            done = False
            for r in await Radio.get_radios_async():
                if r.kind == kind:
                    await r.set_state_async(RadioState.ON if on else RadioState.OFF)
                    done = True
            return done
        if asyncio.run(go()):
            ui.notify(f"{'Bluetooth' if what == 'bluetooth' else 'Wi-Fi'} {'on' if on else 'off'}")
            return
    except Exception:
        pass
    os.startfile("ms-settings:bluetooth" if what == "bluetooth" else "ms-settings:network-wifi")


def theme(mode):
    """'dark mode' / 'light mode' for apps and Windows itself (the switch in Settings → Colours)."""
    light = 1 if mode == "light" else 0
    if CTX.dry:
        return log(f"Windows theme: {mode}")
    import ctypes
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", 0,
                        winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "AppsUseLightTheme", 0, winreg.REG_DWORD, light)
        winreg.SetValueEx(k, "SystemUsesLightTheme", 0, winreg.REG_DWORD, light)
    # tell open windows (Explorer, the taskbar, apps) to repaint in the new theme
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "ImmersiveColorSet", 0x2, 2000, None)
    ui.notify(f"{mode.capitalize()} mode")


def wifi_connect(name):
    """'connect to wifi home5g': one of the networks Windows already knows (it has the password)."""
    if CTX.dry:
        return log(f"wifi: connect to the saved network like {name!r}")
    r = run(["netsh", "wlan", "show", "profiles"], wait=True)
    known = re.findall(r":\s*(.+?)\s*$", r.stdout if r else "", re.M)
    known = [k for k in known if k and "profile" not in k.lower()]
    import difflib
    key = lambda x: re.sub(r"[^a-z0-9]", "", x.lower())  # noqa: E731
    pick = next((k for k in known if key(k) == key(name)), None) or \
        next(iter(difflib.get_close_matches(key(name), [key(k) for k in known], n=1, cutoff=0.6)), None)
    if pick and pick not in known:
        pick = next(k for k in known if key(k) == pick)
    if not pick:
        ui.notify(f"No saved Wi-Fi called “{name}”" + (f". Saved: {', '.join(known[:6])}" if known else ""))
        return
    r = run(["netsh", "wlan", "connect", f"name={pick}"], wait=True)
    ui.notify(f"Connecting to {pick}" if r and r.returncode == 0 else f"Couldn't connect to {pick}")


def wifi_disconnect():
    run(["netsh", "wlan", "disconnect"])
    ui.notify("Wi-Fi disconnected")


def bluetooth_panel():
    """'connect my earbuds': Windows 11's Bluetooth list in Quick Settings (one tap connects).
    Connecting by voice alone isn't reliable on Windows, so it stops at the list."""
    if CTX.dry:
        return log("open the Bluetooth device list (Quick Settings)")
    import sys
    try:
        if sys.getwindowsversion().build < 22621:  # the deep link came with Windows 11 22H2
            raise OSError
        os.startfile("ms-actioncenter:controlcenter/bluetooth")
    except OSError:
        os.startfile("ms-settings:bluetooth")
    ui.notify("Tap your device to connect or disconnect it")


# Battery of Bluetooth devices, as Windows shows it in Settings (DEVPKEY_Bluetooth_Battery)
_BT_BATTERY = r"""
$ids = Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match '^(BTHENUM|BTHLE|BTHHFENUM|BTHLEDEVICE)' }
$ids | ForEach-Object {
  $b = Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName '{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2' -ErrorAction SilentlyContinue
  if ($b -and $b.Data -ne $null) { "$($_.FriendlyName)`t$($b.Data)" }
}
"""


def bt_batteries(text):
    """'Galaxy Buds2 Hands-Free AG\t80' lines -> {'Galaxy Buds2': 80}: one name per device, the lowest level."""
    out = {}
    for line in text.splitlines():
        name, _, level = line.rpartition("\t")
        if not name.strip() or not level.strip().isdigit():
            continue
        name = re.sub(r"\s+(?:hands-?free(?: ag)?(?: audio)?|avrcp transport|stereo|a2dp(?: snk)?|le|audio)$", "", name.strip(), flags=re.I)
        out[name] = min(out.get(name, 100), int(level))
    return out


def bluetooth_battery(which=""):
    """'earbuds battery': each connected Bluetooth device that reports one (most headphones and controllers do)."""
    if CTX.dry:
        return log("read the battery of connected Bluetooth devices")
    r = _ps(_BT_BATTERY, timeout=20)
    levels = bt_batteries(r.stdout if r else "")
    if not levels:
        ui.tell("No connected Bluetooth device reports its battery",
                "None of your connected Bluetooth devices report a battery level")
        return
    ui.tell("  ·  ".join(f"{n} {v}%" for n, v in levels.items()),
            ", ".join(f"{n} at {v} percent" for n, v in levels.items()))


# ----------------------------------------------------------------- answers
def clock():
    now = datetime.now()
    ui.tell(now.strftime("%I:%M %p, %A %d %B").lstrip("0"), f"It's {now.strftime('%I:%M %p').lstrip('0')}")


def date_today():
    now = datetime.now()
    ui.tell(now.strftime("%A %d %B %Y"), f"It's {now.strftime('%A, %B')} {now.day}")


def _wttr(fmt):
    import urllib.parse
    import urllib.request
    url = f"https://wttr.in/{urllib.parse.quote(config.get('weather_place') or '')}?{fmt}&m"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "curl/8"}), timeout=8) as r:
        return r.read().decode()


def weather(when=None):
    """now (default) | tomorrow | rain — from wttr.in."""
    if CTX.dry:
        return log(f"weather ({when or 'now'})")
    try:
        if when in ("tomorrow", "rain", "rain tomorrow"):
            d = json.loads(_wttr("format=j1"))
            day = d["weather"][1 if "tomorrow" in when else 0]
            rain = max(int(h["chanceofrain"]) for h in day["hourly"])
            desc = day["hourly"][4]["weatherDesc"][0]["value"]
            label = "Tomorrow" if "tomorrow" in when else "Today"
            if when.startswith("rain"):
                ui.tell(f"{label}: {rain}% chance of rain", f"{label}, {rain} percent chance of rain")
            else:
                ui.tell(f"Tomorrow: {desc}, {day['mintempC']}–{day['maxtempC']}°C, rain {rain}%",
                        f"Tomorrow, {desc.lower()}, {day['mintempC']} to {day['maxtempC']} degrees, {rain} percent chance of rain")
            return
        place, cond, temp, feels, hum = _wttr("format=%l|%C|%t|%f|%h").strip().split("|")
        t, f = temp.lstrip("+"), feels.lstrip("+")
        ui.tell(f"{cond}, {t} (feels {f}) · humidity {hum} · {place.split(',')[0]}",
                f"{cond}, {t.replace('°C', ' degrees')}" + (f", feels like {f.replace('°C', '')}" if f != t else ""))
    except Exception as e:
        ui.notify(f"Weather unavailable: {e}")


def _gb(b):
    return b / 1024 ** 3


def _mb(mb):
    return f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{mb:.0f} MB"


def ram():
    if CTX.dry:
        return log("RAM used / total")
    import psutil
    m = psutil.virtual_memory()
    used = m.total - m.available
    ui.tell(f"RAM {_gb(used):.1f} / {_gb(m.total):.1f} GB used, {m.available // 1024 ** 2} MB free",
            f"{_gb(used):.1f} gigabytes of RAM used, {_gb(m.available):.1f} free")


FRIENDLY = {"msedge": "Edge", "chrome": "Chrome", "firefox": "Firefox", "brave": "Brave", "opera": "Opera",
            "discord": "Discord", "spotify": "Spotify", "steamwebhelper": "Steam", "steam": "Steam",
            "msmpeng": "Windows Defender", "explorer": "File Explorer", "dwm": "Windows graphics",
            "searchhost": "Windows search", "memcompression": "Windows (compressed memory)",
            "whisper-server": "Voice Agent speech model", "windowsvoiceagent": "Voice Agent",
            "code": "VS Code", "epicwebhelper": "Epic Games", "epicgameslauncher": "Epic Games"}


def _ram_by_app():
    """[(app, MB)], largest first, an app's processes added up."""
    import psutil
    tally = {}
    for p in psutil.process_iter(["name", "memory_info"]):
        try:
            name = (p.info["name"] or "").lower().removesuffix(".exe")
            mi = p.info["memory_info"]
            if not name or not mi:
                continue
            app = FRIENDLY.get(name, name)
            tally[app] = tally.get(app, 0) + mi.rss
        except Exception:
            continue
    return sorted(((a, b / 1024 ** 2) for a, b in tally.items()), key=lambda x: -x[1])


def top_ram():
    if CTX.dry:
        return log("top 5 apps by RAM")
    rows = _ram_by_app()[:5]
    ui.tell("\n".join(f"{_mb(mb)}  {app}" for app, mb in rows),
            "Most RAM: " + ", ".join(f"{app} {_mb(mb).replace('GB', 'gigabytes').replace('MB', 'megabytes')}"
                                     for app, mb in rows[:3]))


def _nvidia():
    """(temp °C, load %, VRAM used MB, VRAM total MB) of the first NVIDIA GPU, or None."""
    exe = shutil.which("nvidia-smi") or r"C:\Windows\System32\nvidia-smi.exe"
    r = run([exe, "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"], wait=True, timeout=5)
    try:
        t, u, mu, mt = [int(float(x)) for x in r.stdout.splitlines()[0].split(",")]
        return t, u, mu, mt
    except Exception:
        return None


def gpu_info():
    if CTX.dry:
        return log("GPU temperature, load, VRAM")
    g = _nvidia()
    if not g:
        ui.notify("No NVIDIA GPU info (nvidia-smi didn't answer)")
        return
    t, u, mu, mt = g
    ui.tell(f"GPU {t}°C · {u}% busy · VRAM {mu / 1024:.1f} / {mt / 1024:.1f} GB",
            f"GPU at {t} degrees, {u} percent busy, {mu / 1024:.1f} of {mt / 1024:.0f} gigabytes of video memory used")


def cpu_info():
    if CTX.dry:
        return log("CPU load")
    import psutil
    load = psutil.cpu_percent(interval=0.5)
    ui.tell(f"CPU {load:.0f}% busy", f"CPU is {load:.0f} percent busy")


def disk_info():
    if CTX.dry:
        return log("disk space on C:")
    u = shutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\")
    ui.tell(f"Disk C: {_gb(u.free):.0f} GB free of {_gb(u.total):.0f} GB", f"{_gb(u.free):.0f} gigabytes free")


def uptime_info():
    if CTX.dry:
        return log("uptime")
    import psutil
    s = int(time.time() - psutil.boot_time())
    ui.tell(f"Up {s // 3600} h {s % 3600 // 60} min", f"Up for {s // 3600} hours and {s % 3600 // 60} minutes")


def ip_info():
    if CTX.dry:
        return log("local IP")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # picks the route; nothing is sent
        ip = s.getsockname()[0]
        s.close()
    except OSError:
        ip = "none"
    ui.notify(f"IP: {ip}")


def battery():
    if CTX.dry:
        return log("battery")
    import psutil
    b = psutil.sensors_battery()
    if not b:
        ui.tell("No battery: this PC is plugged in")
        return
    ui.tell(f"Battery {b.percent:.0f}%" + (" (charging)" if b.power_plugged else ""),
            f"Battery at {b.percent:.0f} percent" + (", charging" if b.power_plugged else ""))


def status_info():
    if CTX.dry:
        return log("RAM + CPU + GPU + disk in one answer")
    import psutil
    m = psutil.virtual_memory()
    top = _ram_by_app()[0]
    shown = [f"RAM {_gb(m.total - m.available):.1f} / {_gb(m.total):.1f} GB (most: {top[0]} {_mb(top[1])})",
             f"CPU {psutil.cpu_percent(interval=0.3):.0f}%"]
    spoken = [f"RAM {_gb(m.total - m.available):.1f} of {_gb(m.total):.0f} gigabytes"]
    g = _nvidia()
    if g:
        shown.append(f"GPU {g[0]}°C · {g[1]}% · VRAM {g[2] / 1024:.1f} GB")
        spoken.append(f"GPU {g[0]} degrees")
    u = shutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\")
    shown.append(f"Disk {_gb(u.free):.0f} GB free")
    ui.tell("\n".join(shown), ". ".join(spoken))


# ----------------------------------------------------------------- voice replies
def voice_replies(state):
    on = state in ("on", "enable", "start", "back")
    if CTX.dry:
        return log(f"voice replies {'on' if on else 'off'}")
    config.set("voice_replies", on)
    ui.tell("Voice replies on") if on else ui.notify("Voice replies off")


def never_mind():
    if CTX.dry:
        log("(nothing)")


# ----------------------------------------------------------------- timers
# Each running timer is a threading.Timer plus a record in timers.json, so the list
# survives a restart of the agent. Phrasing follows Home Assistant's timer intents.
_TIMERS = {}  # id -> threading.Timer
_tlock = threading.Lock()


def _recs():
    try:
        recs = json.loads(paths.TIMERS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    now = time.time()
    return [r for r in recs if r.get("left") is not None or r["ends"] > now - 5]


def _save(recs):
    if not CTX.dry:
        paths.ensure()
        paths.TIMERS.write_text(json.dumps(recs), encoding="utf-8")


def _schedule(rec, secs):
    rec["ends"] = time.time() + secs
    rec["left"] = None
    t = threading.Timer(secs, timer_done, args=(rec["id"],))
    t.daemon = True
    with _tlock:
        _TIMERS[rec["id"]] = t
    t.start()


def _unschedule(rec):
    with _tlock:
        t = _TIMERS.pop(rec["id"], None)
    if t:
        t.cancel()


def restore_timers():
    """At start-up: timers that were running before the agent restarted carry on."""
    recs = _recs()
    for r in recs:
        if r.get("left") is None and r["ends"] > time.time():
            _schedule(r, r["ends"] - time.time())
    _save(recs)


def _left(rec):
    return rec["left"] if rec.get("left") is not None else max(0, rec["ends"] - time.time())


def _name(rec):
    return f"{rec['label']} timer" if rec.get("label") else f"{fmt_dur(rec['total'])} timer"


def find_timer(*specs):
    """The timer a phrase means: by name, by its length, the only one, or the newest."""
    recs = _recs()
    spec = " ".join(s for s in specs if s and s.strip()).strip()
    spec = re.sub(r"^(?:the|my|a|an)\s+|\s*\b(?:timer|timers)\b\s*", " ", spec).strip()
    if spec:
        for r in recs:
            if r.get("label") and r["label"] in spec:
                return r
        d = parse_duration(spec)
        for r in recs:
            if d and r["total"] == d:
                return r
    return recs[-1] if recs else None


def timer_start(dur, label=None):
    secs = parse_duration(dur)
    label = (label or "").strip().rstrip(".")
    if CTX.dry:
        return log(f"timer {fmt_dur(secs)}" + (f" '{label}'" if label else ""))
    recs = _recs()
    rec = {"id": uuid.uuid4().hex[:8], "label": label, "total": secs}
    _schedule(rec, secs)
    recs.append(rec)
    _save(recs)
    ui.tell(f"Timer set: {fmt_dur(secs)}" + (f" · {label}" if label else ""),
            f"{fmt_dur(secs)}" + (f" {label} timer" if label else " timer") + ", starting now")


def timer_done(tid):
    recs = _recs()
    rec = next((r for r in recs if r["id"] == tid), None)
    _save([r for r in recs if r["id"] != tid])
    with _tlock:
        _TIMERS.pop(tid, None)
    try:
        import winsound
        for _ in range(3):
            winsound.MessageBeep(0x30)  # MB_ICONEXCLAMATION
            time.sleep(0.6)
    except Exception:
        pass
    ui.tell(f"Timer: {rec['label']}" if rec and rec.get("label") else "Time's up",
            f"Your {rec['label']} timer is done" if rec and rec.get("label") else "Time's up")


def timer_status(*specs):
    if CTX.dry:
        return log(f"timer status {specs}")
    recs = _recs()
    if not recs:
        ui.tell("No timers running")
        return
    pick = [find_timer(*specs)] if any(s and s.strip() for s in specs) else recs
    lines = [f"{_name(r)}: {fmt_dur(_left(r))} left" + (" (paused)" if r.get("left") is not None else "") for r in pick]
    ui.tell("\n".join(lines), ". ".join(lines))


def timer_cancel(*specs, all_=False):
    if CTX.dry:
        return log(f"cancel timer {'all' if all_ else specs}")
    recs = _recs()
    targets = recs if all_ else [r for r in [find_timer(*specs)] if r]
    if not targets:
        ui.tell("No timers running")
        return
    for r in targets:
        _unschedule(r)
    _save([r for r in recs if r not in targets])
    ui.tell(f"Cancelled {len(targets)} timers" if len(targets) > 1 else f"Cancelled the {_name(targets[0])}")


def timer_adjust(delta, sign, *specs):
    d = parse_duration(delta)
    if CTX.dry:
        return log(f"timer {'+' if sign > 0 else '-'}{d}s {specs}")
    rec = find_timer(*specs)
    if not d or not rec:
        ui.tell("No timer to change" if not rec else f"Bad time: {delta}")
        return
    recs = _recs()
    rec = next(r for r in recs if r["id"] == rec["id"])
    new = max(1, _left(rec) + sign * d)
    rec["total"] = max(1, rec["total"] + sign * d)
    if rec.get("left") is not None:
        rec["left"] = new
    else:
        _unschedule(rec)
        _schedule(rec, new)
    _save(recs)
    ui.tell(f"{_name(rec)}: {fmt_dur(new)} left")


def timer_pause(resume, *specs):
    if CTX.dry:
        return log(f"timer {'resume' if resume else 'pause'} {specs}")
    rec = find_timer(*specs)
    if not rec:
        ui.tell("No timers running")
        return
    recs = _recs()
    rec = next(r for r in recs if r["id"] == rec["id"])
    if resume and rec.get("left") is not None:
        _schedule(rec, rec["left"])
        msg = f"Resumed the {_name(rec)}: {fmt_dur(_left(rec))} left"
    elif not resume and rec.get("left") is None:
        _unschedule(rec)
        rec["left"] = max(1, rec["ends"] - time.time())
        msg = f"Paused the {_name(rec)} with {fmt_dur(rec['left'])} left"
    else:
        msg = f"The {_name(rec)} is already {'running' if resume else 'paused'}"
    _save(recs)
    ui.tell(msg)
