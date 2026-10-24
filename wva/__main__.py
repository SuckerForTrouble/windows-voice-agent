"""WindowsVoiceAgent.exe            the agent (tray icon)
   … --try "open spotify"         what a phrase would do (nothing runs)
   … --list                       every command
   … --selftest out.json          build check: imports, routing, whisper (used by CI)"""
import json
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
    engine.CTX.dry, engine.CTX.raw = True, text
    steps, _ = engine.plan(text, woke=True)
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
    for backend in ("vulkan", "cpu"):
        exe = paths.WHISPER / backend / "whisper-server.exe"
        res["whisper"][backend] = "present" if exe.exists() else "missing"
    if stt_model and wav:
        from . import config
        from .stt import Whisper
        config.load()
        config._cache.update(model=stt_model, backend="cpu")
        w = Whisper()
        t0 = time.time()
        if w.start():
            import wave
            with wave.open(wav) as f:
                pcm = f.readframes(f.getnframes())
            res["whisper"]["heard"] = w.transcribe(pcm)
            res["whisper"]["seconds"] = round(time.time() - t0, 1)
            w.stop()
        else:
            res["whisper"]["error"] = w.error or "did not start"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    ok = all(v == "ok" for v in res["imports"].values()) and not bad
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
