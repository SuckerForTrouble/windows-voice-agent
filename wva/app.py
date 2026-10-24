"""The running agent: tray icon, push-to-talk keys, microphone -> whisper -> commands.

Hold the agent key (F9) and talk; let go and it runs. A quick tap toggles
instead (tap, talk, tap). Esc while listening cancels. The dictation key (F10)
types what you say; "computer …" through it still runs a command."""
import importlib
import logging
import logging.handlers
import os
import queue
import re
import sys
import threading
import time

from . import (APP_ID, APP_NAME, __version__, apps, config, engine, history, osd, paths, speak, state, system, tuning, ui,
               updater, win)
from . import rules  # noqa: F401  (registers the commands)
from .recorder import Recorder
from .stt import Whisper

log = logging.getLogger("wva")
TAP = 0.35            # a press shorter than this is a tap: toggle mode
MIN_SECONDS = 0.35    # shorter recordings are ignored
MIN_PEAK = 600        # quieter than this (of 32767) is silence
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def beep(kind):
    if not config.get("sounds"):
        return
    import winsound
    tones = {"start": [(880, 70)], "stop": [(660, 70)], "error": [(330, 140)], "cancel": [(500, 60), (400, 60)]}
    threading.Thread(target=lambda: [winsound.Beep(f, d) for f, d in tones[kind]], daemon=True).start()


def startup_enabled():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_ID)
            return True
    except OSError:
        return False


class App:
    def __init__(self):
        from .tray import Tray
        self.tray = Tray(self)
        self.rec = Recorder()
        self.stt = Whisper(on_progress=self._progress)
        state.stt = self.stt
        self.mode = None        # "agent" / "dictate" while listening
        self.toggled = False    # listening after a tap, until the next tap
        self.jobs = queue.Queue()
        self.hotkeys = None
        self.first_run = not paths.CONFIG.exists()

    # ------------------------------------------------------------- start-up
    def start(self, icon):
        icon.visible = True
        threading.Thread(target=self._boot, daemon=True, name="boot").start()
        threading.Thread(target=self._worker, daemon=True, name="worker").start()

    def _boot(self):
        config.save()  # writes the defaults on the first run
        if self.first_run and config.get("start_with_windows"):
            self.set_startup(True)
        n_words, n_says = tuning.apply()
        log.info("tuning: %s word fixes, %s phrases", n_words, n_says)
        apps.warm_up()
        system.restore_timers()
        if config.get("auto_update"):
            threading.Thread(target=lambda: (time.sleep(20), self.check_updates()), daemon=True).start()
        self.tray.set("loading", "Loading the speech model…")
        if self.first_run:
            osd.show(f"{APP_NAME} is getting ready. The first start downloads the speech model (~550 MB).", "busy", 0)
        if not self.stt.start():
            self.tray.set("error", self.stt.error)
            osd.show(self.stt.error, "error", 12)
            self.tray.notify(self.stt.error)
            return
        self._register_keys()
        key = config.get("agent_key").upper()
        where = "GPU" if self.stt.backend == "vulkan" else "CPU"
        self.tray.set("ready", f"Ready: hold {key} and talk ({where})")
        osd.show(f"Ready: hold {key} and talk", "ok", 4)
        if self.first_run:
            time.sleep(1)
            self.do("checkup.run_and_open")
            time.sleep(2)
            self.do("guide.open_guide")

    def _register_keys(self):
        from .hotkey import Hotkeys
        self.hotkeys = Hotkeys(self._pressed, self._released)
        for mode in ("agent", "dictate"):
            ok = self.hotkeys.register(mode, config.get(f"{mode}_key"))
            state.hotkeys[mode] = ok
            if not ok:
                msg = f"{config.get(f'{mode}_key').upper()} is taken by another app. Say or click 'check my setup' for help."
                self.tray.notify(msg)
                log.warning(msg)

    def _progress(self, msg):
        if msg:
            self.tray.set("loading", msg)
            osd.show(msg, "busy", 0)

    # ------------------------------------------------------------- keys
    def _pressed(self, name):
        if name == "cancel":
            self._cancel()
            return
        if not self.stt.ready:
            osd.show(self.stt.error or self.stt.progress or "Still loading the speech model…", "busy", 3)
            return
        if self.rec.active:
            if self.toggled:  # second tap ends a toggled recording
                self._finish()
            return
        self.mode, self.toggled = name, False
        try:
            self.rec.start(config.get("mic"))
        except Exception as e:
            self.mode = None
            osd.show(f"Microphone problem: {e}", "error", 6)
            beep("error")
            return
        beep("start")
        self.tray.set("listen", "Listening…")
        osd.show("Listening…" if name == "agent" else "Listening… (typing)", "listen", 0)
        self.hotkeys.register("cancel", "escape")

    def _released(self, name, held):
        if not self.rec.active or name != self.mode:
            return
        if held < TAP and not self.toggled:
            self.toggled = True  # a tap: keep listening until the next tap
            osd.show("Listening… tap again when done", "listen", 0)
            threading.Thread(target=self._toggle_timeout, daemon=True).start()
            return
        if not self.toggled:
            self._finish()

    def _toggle_timeout(self):
        t0 = self.rec.started
        while self.rec.active and self.rec.started == t0:
            if time.time() - t0 > 30:
                self._finish()
                return
            time.sleep(0.2)

    def _cancel(self):
        if self.rec.active:
            self.rec.stop()
            self.hotkeys.unregister("cancel")
            self.mode = None
            beep("cancel")
            self._ready_again()
            osd.show("Cancelled", "info", 1.5)

    def _finish(self):
        mode = self.mode
        pcm, secs, peak = self.rec.stop()
        self.hotkeys.unregister("cancel")
        self.mode, self.toggled = None, False
        beep("stop")
        if secs < MIN_SECONDS or peak < MIN_PEAK:
            self._ready_again()
            osd.show("Didn't hear anything" if peak < MIN_PEAK else "Too short", "info", 2)
            return
        self.tray.set("busy", "Thinking…")
        osd.show("…", "busy", 0)
        self.jobs.put((mode, pcm))

    def _ready_again(self):
        self.tray.set("ready", f"Ready: hold {config.get('agent_key').upper()} and talk")

    # ------------------------------------------------------------- commands
    def _worker(self):
        try:
            import comtypes
            comtypes.CoInitialize()  # pycaw needs COM on this thread
        except Exception:
            pass
        while True:
            mode, pcm = self.jobs.get()
            try:
                text = self.stt.transcribe(pcm)
                log.info("heard (%s): %r", mode, text)
                if not text:
                    osd.show("Didn't catch that", "info", 2)
                elif mode == "dictate" and not re.match(engine.WAKE, engine.clean(text)):
                    osd.hide()
                    win.type_unicode(text + " ")
                else:
                    self.run_text(text, woke=mode == "agent")
            except Exception as e:
                log.exception("job failed")
                osd.show(f"Something went wrong: {e}", "error", 5)
            finally:
                self._ready_again()

    def run_text(self, text, woke=True):
        engine.CTX.raw, engine.CTX.last_target = text, None
        steps, woke = engine.plan(text, woke=woke)
        heard = re.sub(r"\s+", " ", text).strip()
        if not steps:
            history.record(via="agent", heard=heard, clean=engine.clean(text), result="unmatched")
            beep("error")
            osd.show(f"Didn't understand: “{heard}”", "error", 3.5)
            return
        chips = " → ".join((s[:1].upper() + s[1:])[:40] for _, _, s in steps)
        osd.show(f"“{heard}”   ✓ {chips}" if len(steps) > 1 or len(heard) > 40 else f"✓ {heard}", "ok", 2.5)
        errors = []
        for i, (r, groups, _) in enumerate(steps):
            try:
                r.fn(*groups)
            except Exception as e:
                log.exception("%s failed", r.say)
                errors.append(f"{r.say}: {e}")
                osd.show(f"{r.say}: {e}", "error", 5)
            if i + 1 < len(steps):
                time.sleep(r.after)
        history.record(via="agent", heard=heard, clean=engine.clean(text), steps=[r.say for r, _, _ in steps],
                       args=[list(g) for _, g, _ in steps], result="error" if errors else "ran", errors=errors or None)

    def do(self, target, *args):
        """Run module.function from the tray (off the tray's thread)."""
        def go():
            mod, _, fn = target.rpartition(".")
            try:
                getattr(importlib.import_module(f"wva.{mod}"), fn)(*args)
            except Exception as e:
                log.exception("%s failed", target)
                self.tray.notify(f"{target}: {e}")
        threading.Thread(target=go, daemon=True).start()

    # ------------------------------------------------------------- tray actions
    def open_file(self, path):
        paths.ensure()
        if not path.exists():
            path.write_text("", encoding="utf-8")
        os.startfile(str(path))

    def set_startup(self, on):
        import winreg
        config.set("start_with_windows", on)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            if on and paths.FROZEN:
                winreg.SetValueEx(k, APP_ID, 0, winreg.REG_SZ, f'"{sys.executable}"')
            else:
                try:
                    winreg.DeleteValue(k, APP_ID)
                except OSError:
                    pass

    def check_updates(self, interactive=False):
        def go():
            if self.rec.active:
                return
            result = updater.check(self.tray.notify, before_install=self.stt.stop)
            if interactive:
                if result == "none":
                    self.tray.notify(f"You have the latest version ({__version__})")
                elif result.startswith("error"):
                    self.tray.notify(f"Couldn't check for updates: {result[7:]}")
        threading.Thread(target=go, daemon=True).start()

    def restart(self):
        import subprocess
        self.stt.stop()
        argv = [sys.executable] if paths.FROZEN else [sys.executable, "-m", "wva"]
        subprocess.Popen(argv + ["--wait-for", str(os.getpid())], creationflags=0x08000000)
        self.quit()

    def quit(self):
        self.stt.stop()
        self.tray.stop()
        os._exit(0)


def setup_logging():
    paths.ensure()
    h = logging.handlers.RotatingFileHandler(paths.LOGS / "agent.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[h])
    sys.excepthook = lambda *exc: log.critical("crash", exc_info=exc)
    threading.excepthook = lambda a: log.critical("thread crash", exc_info=(a.exc_type, a.exc_value, a.exc_traceback))


def main():
    setup_logging()
    log.info("%s %s starting (%s)", APP_NAME, __version__, sys.executable)
    if not win.single_instance(APP_ID):
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, f"{APP_NAME} is already running: look for its icon by the clock.",
                                         APP_NAME, 0x40)
        return
    config.load()
    app = App()
    ui.handlers.update(
        notify=lambda m: osd.show(m, "info", 4 + len(m) / 40) if config.get("osd") else app.tray.notify(m),
        speak=speak.say,
        update=lambda: app.check_updates(interactive=True),
    )
    app.tray.run(app.start)
