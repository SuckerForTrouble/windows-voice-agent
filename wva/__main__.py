"""WindowsVoiceAgent.exe            the agent (tray icon)
   … --try "open spotify"         what a phrase would do (nothing runs)
   … --list                       every command
   … --selftest out.json          build check: imports, routing, whisper (used by CI)
   … --dialog pick-key|api-key …  the tray's small windows"""
import json
import os
import sys
import time


def _console():
    """The .exe has no console: answers go to a file next to the data folder instead."""
    if sys.stdout is None:
        from . import paths
        paths.ensure()
        sys.stdout = sys.stderr = open(paths.LOGS / "console.txt", "w", encoding="utf-8")


def try_phrase(text):
    from . import engine, rules  # noqa: F401
    from .actions import streamline
    engine.CTX.dry, engine.CTX.raw, engine.CTX.last_target = True, text, None
    steps = streamline(engine.plan(text, woke=True)[0])
    if not steps:
        print("-> not a command")
    for r, groups, _ in steps:
        print(f"-> {r.say}  {groups}")
        r.fn(*groups)


def list_commands():
    from . import guide, rules  # noqa: F401
    for g in guide.groups():
        print(f"\n{g['name']}")
        for r in g["rules"]:
            print(f"  {r['say']:<48} {r['desc']}")


def selftest(out, stt_model=None, wav=None):
    """Proves a build is whole: every optional module imports, the phrases route, and
    (when given a model and a WAV) whisper-server starts and hears the words."""
    res = {"imports": {}, "routing": None, "whisper": {}}
    for mod in ("sounddevice", "psutil", "pystray", "PIL", "comtypes", "pycaw.pycaw", "tkinter",
                "winrt.windows.media.control", "winrt.windows.devices.radios", "wva.app"):
        try:
            __import__(mod)
            res["imports"][mod] = "ok"
        except Exception as e:  # noqa: BLE001
            res["imports"][mod] = f"{type(e).__name__}: {e}"
    from . import engine, paths, rules  # noqa: F401
    from .examples import CASES
    engine.CTX.dry = True
    engine.CTX.log = lambda m: None
    bad = []
    for case in CASES:
        engine.CTX.front = case[2] if len(case) > 2 else ""
        got = [r.say for r, _, _ in engine.plan(case[0], woke=True)[0]]
        if got != case[1]:
            bad.append(case[0])
    res["routing"] = {"cases": len(CASES), "failed": bad}
    try:  # every tray menu label, tick and submenu builds (as when it's clicked)
        from .tray import Tray

        class _App:
            def __getattr__(self, name):
                return lambda *a, **k: None

        def walk(menu, depth=0):
            n = 0
            for item in menu.items:
                _ = (item.text, item.checked, item.enabled)
                n += 1
                if item.submenu:
                    n += walk(item.submenu, depth + 1)
            return n
        res["tray"] = f"ok: {walk(Tray(_App()).icon.menu)} items"
    except Exception as e:  # noqa: BLE001
        res["tray"] = f"{type(e).__name__}: {e}"
    try:  # the welcome / Settings window builds (it's drawn, then closed straight away)
        from . import config as _config
        from .settings_window import Window
        _config.load()
        w = Window({k: _config.get(k) for k in ("agent_key", "dictate_key", "model", "always_listen", "call_word",
                                                 "music_app", "movie_app", "browser", "voice_replies", "sounds",
                                                 "start_with_windows", "unload_in_games", "auto_update",
                                                 "dictate_language", "osd", "osd_style")}, True)
        w.root.update()
        n = [0]

        def count(widget):
            n[0] += 1
            for child in widget.winfo_children():
                count(child)
        count(w.root)
        w.root.destroy()
        res["settings_window"] = f"ok: {n[0]} widgets"
    except Exception as e:  # noqa: BLE001
        res["settings_window"] = f"{type(e).__name__}: {e}"
    try:  # the tray panel draws (on a hidden canvas, with made-up values)
        import tkinter as tk

        from . import panel
        root = tk.Tk()
        root.withdraw()
        c = tk.Canvas(root, width=panel.W, height=600)
        m = {"kind": "ready", "status": "Ready", "version": "0", "engine": "Parakeet on GPU", "ram": "1 MB RAM",
             "vram": "", "last": "last 0.1 s", "call_word": "Jarvis", "always_listen": True, "paused": False,
             "voice_replies": False, "sounds": True, "osd": True, "osd_style": "minimal", "mic": "Windows default",
             "model": "Parakeet", "key": "F9", "mics": ["Windows default", "Mic"]}
        h = panel.draw(c, m, lambda a: None, True)
        root.update()
        root.destroy()
        res["panel"] = f"ok: {h}px"
    except Exception as e:  # noqa: BLE001
        res["panel"] = f"{type(e).__name__}: {e}"
    try:  # the setup check runs through (here without a mic or GPU, so some say so)
        from . import checkup
        res["checkup"] = {r["name"]: f"{r['status']}: {r['detail']}" for r in checkup.run_all()}
    except Exception as e:  # noqa: BLE001
        res["checkup"] = f"{type(e).__name__}: {e}"
    try:  # a shortcut Windows itself made reads back (the Recent list is read the same way)
        import subprocess
        import tempfile

        from . import files
        d = tempfile.mkdtemp()
        target, lnk = os.path.join(d, "budget 2026 final.xlsx"), os.path.join(d, "budget.lnk")
        open(target, "w").close()
        subprocess.run(["powershell", "-NoProfile", "-Command", f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
                        f"$s.TargetPath='{target}';$s.Save()"], capture_output=True, timeout=60, creationflags=0x08000000)
        got = files.lnk_target(lnk)
        res["shortcut"] = "ok" if got and os.path.normcase(got) == os.path.normcase(target) else f"read {got!r}"
        res["recent_files"] = len(files.recent())
    except Exception as e:  # noqa: BLE001
        res["shortcut"] = f"{type(e).__name__}: {e}"
    from . import audio
    for name, probe in (("sound_devices", lambda: [n for _, n, _ in audio.devices()]), ("app_routing", audio.app_routing_ok)):
        try:  # informational: GitHub's machines have no sound card
            res[name] = probe()
        except Exception as e:  # noqa: BLE001
            res[name] = f"{type(e).__name__}: {e}"
    for backend in ("vulkan", "cpu"):
        for name in ("whisper-server", "parakeet-server"):
            res["whisper"][f"{backend}/{name}"] = "present" if (paths.WHISPER / backend / f"{name}.exe").exists() else "missing"
    exe = paths.INSTALL / "helpers" / "mouse-buttons.exe"  # installs its mouse hook once and says "ok"
    if not exe.exists():
        res["helpers"] = {"mouse-buttons": "missing"}
    else:
        import subprocess
        try:
            r = subprocess.run([str(exe), "--check"], capture_output=True, text=True, timeout=20, creationflags=0x08000000)
            res["helpers"] = {"mouse-buttons": (r.stdout.strip() or r.stderr.strip() or f"exit {r.returncode}")}
        except Exception as e:  # noqa: BLE001
            res["helpers"] = {"mouse-buttons": f"{type(e).__name__}: {e}"}
    if stt_model and wav:  # e.g. "tiny.en,parakeet-tdt-0.6b-v3-q8_0": each model hears the WAV on the CPU
        import wave

        from . import config, stt
        config.load()
        with wave.open(wav) as f:
            pcm = f.readframes(f.getnframes())
        res["speech"] = {}
        for model in stt_model.split(","):
            config._cache.update(model=model, backend="cpu")
            engine_ = stt.make()
            t0 = time.time()
            if engine_.start():
                t1 = time.time()
                res["speech"][model] = {"heard": engine_.transcribe(pcm), "start_s": round(t1 - t0, 2),
                                        "transcribe_s": round(time.time() - t1, 2), "engine": type(engine_).__name__}
                engine_.stop()
            else:
                res["speech"][model] = {"heard": "", "error": engine_.error or "did not start"}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    ok = (all(v == "ok" for v in res["imports"].values()) and not bad and str(res["tray"]).startswith("ok")
          and str(res.get("settings_window")).startswith("ok") and str(res.get("panel")).startswith("ok")
          and res.get("shortcut") == "ok")
    return 0 if ok else 1


def main():
    args = sys.argv[1:]
    if args[:1] == ["--wait-for"]:  # a restart: let the old copy finish quitting first
        try:
            import psutil
            psutil.Process(int(args[1])).wait(10)
        except Exception:
            time.sleep(2)
        args = args[2:]
    if args[:1] == ["--dialog"]:  # a small window the tray asked for (see dialogs.py)
        from . import dialogs
        return dialogs.run(*args[1:])
    if args[:1] in (["--try"], ["--list"], ["--selftest"]):
        _console()
    if args[:1] == ["--try"]:
        return try_phrase(" ".join(args[1:]))
    if args[:1] == ["--list"]:
        return list_commands()
    if args[:1] == ["--selftest"]:
        return selftest(*args[1:4])
    if sys.platform != "win32":
        sys.exit("The agent itself runs on Windows. Here you can use --try \"phrase\" and --list.")
    from .app import main as run
    run()


if __name__ == "__main__":
    code = main()
    sys.exit(code or 0)
