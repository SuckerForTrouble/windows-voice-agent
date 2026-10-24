"""'Check my setup': goes through everything the commands rely on, on this PC,
and writes a page that says what works and, for what doesn't, exactly what to do.
Opened by itself after the first install, then by voice or from the tray."""
import html
import os
import sys
import time

from . import APP_NAME, __version__, apps, config, paths, state, ui
from .engine import CTX

OK, WARN, FAIL = "ok", "warn", "fail"


def _check(name, fn):
    try:
        st, detail, fix = fn()
    except Exception as e:  # a check that crashes is itself a finding
        st, detail, fix = FAIL, f"{type(e).__name__}: {e}", "Send the logs folder (tray → Open data folder) to whoever gave you the app."
    return {"name": name, "status": st, "detail": detail, "fix": fix}


def c_speech():
    s = state.stt
    if not s:
        return FAIL, "The speech model hasn't started.", "Wait for 'Ready' in the tray tooltip. The first start downloads ~550 MB."
    if s.error:
        return FAIL, s.error, "Restart the app from the tray. If it keeps failing, set the model to small.en-q5_1 (see FAQ in the README)."
    if not s.ready:
        return WARN, s.progress or "Still loading…", "Give it a minute, then run the check again."
    if s.backend == "cpu":
        return WARN, f"Running on the CPU ({s.model}). Works, but slower and uses more RAM.", \
            "Update your NVIDIA driver (GeForce Experience / NVIDIA app → Drivers), then restart the voice agent."
    return OK, f"{s.model} on the GPU ({s.device or 'Vulkan'})", ""


def c_mic():
    import sounddevice as sd
    name = config.get("mic")
    dev = None
    if name:
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0 and name.lower() in d["name"].lower():
                dev = i
                break
    info = sd.query_devices(dev, "input")
    frames = []
    with sd.RawInputStream(samplerate=16000, channels=1, dtype="int16", device=dev,
                           callback=lambda data, n, t, st: frames.append(bytes(data))):
        time.sleep(0.6)
    import array
    a = array.array("h", b"".join(frames))
    peak = max((abs(v) for v in a), default=0)
    if not a or peak == 0:
        return FAIL, f"{info['name']}: only silence came through.", \
            "Settings → Privacy & security → Microphone: turn on 'Microphone access' and 'Let desktop apps access your microphone'. " \
            "Also check the mic isn't muted (a button on the headset?)."
    return OK, f"{info['name']} (level {peak})", ""


def c_hotkeys():
    bad = [m for m, ok in state.hotkeys.items() if not ok]
    if not state.hotkeys:
        return WARN, "Not registered yet.", "Restart the app from the tray."
    if bad:
        keys = ", ".join(config.get(f"{m}_key").upper() for m in bad)
        return FAIL, f"Another app already uses {keys}.", \
            f"Close the app using {keys}, or change agent_key / dictate_key in config.json (tray → Open data folder), then restart."
    return OK, f"Hold {config.get('agent_key').upper()} for commands, {config.get('dictate_key').upper()} to type", ""


def c_routing():
    from .examples import CASES
    from .engine import plan
    was = CTX.dry
    CTX.dry = True
    bad = 0
    try:
        for case in CASES:
            CTX.front = case[2] if len(case) > 2 else ""
            if [r.say for r, _, _ in plan(case[0], woke=True)[0]] != case[1]:
                bad += 1
    finally:
        CTX.dry, CTX.front = was, ""
    if bad:
        return FAIL, f"{bad} of {len(CASES)} example phrases don't route.", "Check for updates (tray). Your tuning file may also clash: tray → Open my tuning file."
    return OK, f"All {len(CASES)} example phrases reach their command", ""


def c_volume():
    from . import audio
    return OK, f"System volume is {audio.get_volume()}%", ""


def c_media():
    from . import media
    if not media.AVAILABLE:
        return WARN, "Windows media controls unavailable: play/pause fall back to media keys.", "Check for updates."
    ss = media.sessions()
    return OK, ("Players seen: " + ", ".join(sid for sid, _ in ss)) if ss else "Ready (nothing playing right now)", ""


def _installed(name):
    r = apps.resolve(name)
    return r and r[0] != "url"


def c_spotify():
    if not _installed("spotify"):
        return WARN, "Spotify app not found.", "Install Spotify (spotify.com/download or the Microsoft Store) for the Spotify commands."
    return OK, "Installed. 'Like this song', shuffle and repeat flick to Spotify for a moment.", ""


def c_discord():
    if not _installed("discord"):
        return WARN, "Discord app not found.", "Install Discord for the Discord commands."
    if config.get("discord_keybinds"):
        return OK, "Installed, using your global keybinds (works inside games)", \
            "Make sure Discord → Settings → Keybinds has Toggle Mute = Ctrl+Shift+Alt+M and Toggle Deafen = Ctrl+Shift+Alt+D."
    return WARN, "Installed. Mute/deafen flick to Discord and back (can kick you out of a fullscreen game).", \
        "For in-game use: Discord → Settings → Keybinds → add Toggle Mute = Ctrl+Shift+Alt+M and Toggle Deafen = Ctrl+Shift+Alt+D, " \
        "then tick 'Discord keybinds' in the tray menu."


def c_stremio():
    if not _installed("stremio"):
        return WARN, "Stremio app not found: movies will open on web.stremio.com instead.", \
            "Install Stremio from stremio.com for the desktop app (the web version works too)."
    return OK, "Installed: 'watch <movie>' opens its page with the streams", ""


def c_games():
    g = apps.games()
    if not g:
        return WARN, "No Steam or Epic games found.", "Nothing to do if you don't use them. 'open <game>' also works for anything in the Start menu."
    return OK, f"{len(g)} games: " + ", ".join(sorted(x["name"] for x in g)[:8]) + ("…" if len(g) > 8 else ""), ""


def c_clips():
    import psutil
    names = {(p.info["name"] or "").lower() for p in psutil.process_iter(["name"])}
    if config.get("clips") == "xbox":
        return OK, "Using Xbox Game Bar for clips (Win+Alt+G)", "Turn on Settings → Gaming → Captures → 'Record what happened'."
    if names & {"nvidia overlay.exe", "nvidia app.exe", "nvcontainer.exe", "nvidia share.exe"}:
        return OK, "NVIDIA overlay is running", "'Clip that' needs Instant Replay: press Alt+Z → Instant Replay → Turn on."
    return WARN, "NVIDIA app / overlay not running: 'clip that' won't do anything.", \
        "Install the NVIDIA app (nvidia.com/apps) and turn on Instant Replay (Alt+Z), or pick Xbox Game Bar in the tray menu."


def c_gpu():
    from . import system
    g = system._nvidia()
    if not g:
        return WARN, "nvidia-smi didn't answer.", "Install / update the NVIDIA driver. ('gpu temperature' needs it.)"
    return OK, f"{g[0]}°C, {g[1]}% busy, VRAM {g[2]} / {g[3]} MB", ""


def c_radios():
    import asyncio

    from winrt.windows.devices.radios import Radio

    async def go():
        await Radio.request_access_async()
        return [str(r.kind).split(".")[-1] for r in await Radio.get_radios_async()]
    kinds = asyncio.run(go())
    if not kinds:
        return WARN, "No Wi-Fi/Bluetooth switches found: those commands open Settings instead.", ""
    return OK, "Switches: " + ", ".join(kinds), ""


def c_voice():
    import comtypes.client
    v = comtypes.client.CreateObject("SAPI.SpVoice")
    n = v.GetVoices().Count
    return (OK, f"{n} Windows voices", "") if n else (WARN, "No Windows voice installed.", "Settings → Time & language → Speech → Add voices.")


def c_internet():
    import urllib.request
    urllib.request.urlopen("https://api.github.com", timeout=6).read(1)
    return OK, "Online (weather, Stremio search, updates)", ""


def c_update():
    from . import updater
    latest = updater.latest_version()
    if latest and updater.newer(latest, __version__):
        return WARN, f"Version {latest} is out (you have {__version__}).", "Tray → Check for updates (or say 'check for updates')."
    return OK, f"Up to date ({__version__})", ""


def c_startup():
    from . import app
    return (OK, "Starts with Windows", "") if app.startup_enabled() else \
        (WARN, "Doesn't start with Windows.", "Tray → tick 'Start with Windows'.")


def c_admin():
    import ctypes
    if ctypes.windll.shell32.IsUserAnAdmin():
        return OK, "Running as administrator (works inside every game)", ""
    return OK, "Normal user", "If commands do nothing inside one particular game, that game runs as admin: start the voice agent as administrator too."


CHECKS = [("Speech model", c_speech), ("Microphone", c_mic), ("Push-to-talk keys", c_hotkeys),
          ("Every command routes", c_routing), ("Volume control", c_volume), ("Media controls (play/pause/what's playing)", c_media),
          ("Spotify", c_spotify), ("Discord", c_discord), ("Stremio", c_stremio), ("Steam & Epic games", c_games),
          ("Clips & recording", c_clips), ("NVIDIA GPU info", c_gpu), ("Wi-Fi & Bluetooth switches", c_radios),
          ("Spoken answers", c_voice), ("Internet", c_internet), ("Updates", c_update), ("Start with Windows", c_startup),
          ("Games running as admin", c_admin)]


def run_all():
    return [_check(n, f) for n, f in CHECKS]


def render(results):
    icon = {OK: "✓", WARN: "!", FAIL: "✗"}
    rows = "".join(
        f'<tr class="{r["status"]}"><td class="s">{icon[r["status"]]}</td><td><b>{html.escape(r["name"])}</b>'
        f'<div class="d">{html.escape(r["detail"])}</div>'
        + (f'<div class="f">→ {html.escape(r["fix"])}</div>' if r["fix"] else "") + "</td></tr>" for r in results)
    n_ok = sum(r["status"] == OK for r in results)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Setup check</title><style>
:root{{--bg:#f6f7fb;--card:#fff;--ink:#1d2230;--soft:#5d6577;--line:#e3e6ee;--ok:#1f8a4c;--warn:#b45309;--fail:#c2410c}}
@media (prefers-color-scheme:dark){{:root{{--bg:#14161c;--card:#1d2029;--ink:#e8eaf0;--soft:#a2a9b8;--line:#2c303b;--ok:#4ade80;--warn:#fbbf24;--fail:#fb923c}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 "Segoe UI",system-ui,sans-serif}}
main{{max-width:900px;margin:auto;padding:28px 20px 60px}}h1{{margin:0 0 4px}}.sub{{color:var(--soft);margin-bottom:18px}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}}
td{{padding:12px 14px;border-top:1px solid var(--line);vertical-align:top}}tr:first-child td{{border-top:0}}
td.s{{width:34px;font-size:20px;font-weight:700;text-align:center}}.ok td.s{{color:var(--ok)}}.warn td.s{{color:var(--warn)}}.fail td.s{{color:var(--fail)}}
.d{{color:var(--soft);font-size:14px}}.f{{margin-top:4px;font-size:14px}}.next{{margin-top:22px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px}}
.credit{{color:var(--soft);opacity:.6;font-size:11px;text-align:center;margin-top:26px}}
kbd{{border:1px solid var(--line);border-bottom-width:2px;border-radius:6px;padding:1px 7px;font:600 13px Consolas,monospace}}
</style></head><body><main>
<h1>🩺 Setup check</h1><div class="sub">{APP_NAME} {__version__} · {n_ok} of {len(results)} fine · {time.strftime('%d %b %Y %H:%M')}</div>
<table>{rows}</table>
<div class="next"><b>Next:</b> hold <kbd>{config.get('agent_key').upper()}</kbd>, say <i>"what can I say"</i>, let go. That opens the voice guide.
Fixed something above? Say <i>"check my setup"</i> again.</div>
<div class="credit">made by profane for Billa Janta Party</div>
</main></body></html>"""


def run_and_open():
    if CTX.dry:
        return CTX.log("  run the setup check and open its page")
    ui.notify("Checking your setup…")
    results = run_all()
    paths.ensure()
    out = paths.DATA / "setup-check.html"
    out.write_text(render(results), encoding="utf-8")
    os.startfile(str(out))
    bad = [r for r in results if r["status"] == FAIL]
    warn = [r for r in results if r["status"] == WARN]
    ui.speak(f"{len(results) - len(bad) - len(warn)} of {len(results)} checks passed."
             + (f" {len(bad)} need fixing, the page says how." if bad else ""))
    return results


if __name__ == "__main__" and sys.platform == "win32":
    print(run_all())
