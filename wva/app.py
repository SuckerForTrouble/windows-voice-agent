"""The running agent: tray icon, push-to-talk keys, microphone -> speech model -> commands.

Hold the agent key (F9) and talk; let go and it runs. A quick tap toggles
instead (tap, talk, tap). Esc while listening cancels. The dictation key (F10)
types what you say; "computer …" through it still runs a command.
While a game runs the speech model can step out of graphics memory; the next
key press loads it back while you talk."""
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
               updater, usage, win)
from . import rules  # noqa: F401  (registers the commands)
from . import stt as speech
from .recorder import Recorder

log = logging.getLogger("wva")
TAP = 0.35            # a press shorter than this is a tap: toggle mode
MIN_SECONDS = 0.35    # shorter recordings are ignored
MIN_PEAK = 600        # quieter than this (of 32767) is silence
GAME_IDLE = 120       # in a game, the model steps out again this long after the last command
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
        self.stt = speech.make(on_progress=self._progress)
        state.stt = self.stt
        self.mode = None        # "agent" / "dictate" while listening
        self.toggled = False    # listening after a tap, until the next tap
        self.jobs = queue.Queue()
        self.busy = False       # a recording is being turned into a command
        self.hotkeys = None
        self.load_lock = threading.Lock()
        self.last_used = 0.0
        self.told_game = ""
        self.first_run = not paths.CONFIG.exists()
        osd.level_source = lambda: self.rec.level  # the pill's mic meter

    # ------------------------------------------------------------- start-up
    def start(self, icon):
        icon.visible = True
        threading.Thread(target=self._boot, daemon=True, name="boot").start()
        threading.Thread(target=self._worker, daemon=True, name="worker").start()

    def _boot(self):
        config.save()  # creates the (empty) settings file on the first run
        if self.first_run and config.get("start_with_windows"):
            self.set_startup(True)
        n_words, n_says = tuning.apply()
        log.info("tuning: %s word fixes, %s phrases", n_words, n_says)
        apps.warm_up()
        system.restore_timers()
        self._register_keys()  # before the model: the keys work (and say "loading…") meanwhile
        threading.Thread(target=self._update_loop, daemon=True, name="updates").start()
        if self.first_run:
            osd.show(f"{APP_NAME} is getting ready. The first start downloads the speech model (~550 MB).", "busy", 0)
        if self._load() and self.first_run:
            time.sleep(1)
            self.do("checkup.run_and_open")
            time.sleep(2)
            self.do("guide.open_guide")
        threading.Thread(target=self._watch_games, daemon=True, name="games").start()

    def _update_loop(self):
        """20 s after start, then every 6 hours (a PC that stays on for days still gets
        updates). Skipped while you're talking; the install itself takes ~10 s."""
        time.sleep(20)
        while True:
            if config.get("auto_update"):
                self.check_updates()
            time.sleep(6 * 3600)

    def _register_keys(self):
        from .hotkey import Hotkeys
        self.hotkeys = Hotkeys(self._pressed, self._released)
        for mode in ("agent", "dictate"):
            ok = self.hotkeys.register(mode, config.get(f"{mode}_key"))
            state.hotkeys[mode] = ok
            if not ok:
                msg = f"{config.get(f'{mode}_key').upper()} is taken by another app: tray → Push-to-talk keys to pick another."
                self.tray.notify(msg)
                log.warning(msg)

    def _load(self):
        """Start the speech model (download it first if needed). Safe to call from anywhere."""
        with self.load_lock:
            if self.stt.ready:
                return True
            self.tray.set("loading", "Loading the speech model…")
            ok = self.stt.start()
        if not ok:
            self.tray.set("error", self.stt.error)
            osd.show(self.stt.error, "error", 12)
            self.tray.notify(self.stt.error)
            return False
        self._ready_again()
        if not state.gaming:
            osd.show(f"Ready: hold {config.get('agent_key').upper()} and talk", "ok", 3)
        threading.Thread(target=usage.refresh, args=(self.stt,), daemon=True).start()
        return True

    def _unload(self, game):
        self.stt.stop()
        state.usage = {}
        self._ready_again()
        if self.told_game != game:
            self.told_game = game
            osd.show(f"{game} is running: the speech model stepped out of graphics memory. "
                     f"Press {config.get('agent_key').upper()} any time, it loads back while you talk.", "info", 7)
        log.info("unloaded for %s", game)

    def _watch_games(self):
        """Every few seconds: a game started -> unload; it ended -> load again."""
        while True:
            time.sleep(5)
            try:
                local = self.stt.backend != "cloud"
                game = usage.game_running() if config.get("unload_in_games") and local else ""
                idle = not (self.rec.active or self.busy or self.jobs.qsize())
                if game:
                    state.gaming = game
                    # straight away when the game starts; after that, once you've stopped using it a while
                    if self.stt.ready and idle and (not self.told_game or time.time() - self.last_used > GAME_IDLE):
                        self._unload(game)
                elif state.gaming:
                    state.gaming, self.told_game = "", ""
                    if not self.stt.ready:
                        self._load()
            except Exception:
                log.exception("game watch")

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
            if state.gaming and not self.stt.error:  # stepped out for a game: load it back while you talk
                threading.Thread(target=self._load, daemon=True).start()
            else:
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
        released = time.time()
        self.hotkeys.unregister("cancel")
        self.mode, self.toggled = None, False
        beep("stop")
        if secs < MIN_SECONDS or peak < MIN_PEAK:
            self._ready_again()
            osd.show("Didn't hear anything" if peak < MIN_PEAK else "Too short", "info", 2)
            return
        self.tray.set("busy", "Thinking…")
        osd.show("…", "busy", 0)
        self.jobs.put((mode, pcm, secs, released))

    def _ready_text(self):
        key = config.get("agent_key").upper()
        if not self.stt.ready and state.gaming:
            return f"Game mode: press {key}, the model loads back while you talk"
        where = {"vulkan": "GPU", "cpu": "CPU", "cloud": "cloud"}.get(self.stt.backend, "")
        return f"Ready: hold {key} and talk" + (f" ({where})" if where else "")

    def _ready_again(self):
        self.tray.set("ready", self._ready_text())

    def _engine_name(self):
        """'Parakeet on GPU' / 'Best on CPU' / 'Groq', for the pill's footer."""
        s = self.stt
        if s.backend == "cloud":
            return s.device
        name = speech.MODELS.get(s.model, (s.model,))[0].split(":")[0]
        return f"{name} on {'GPU' if s.backend == 'vulkan' else 'CPU'}"

    def _language(self, mode):
        """Commands are English; the typing key types in the chosen language (.en models only know English)."""
        lang = config.get("dictate_language") if mode == "dictate" else config.get("language")
        return "en" if ".en" in self.stt.model else (lang or "en")

    # ------------------------------------------------------------- commands
    def _worker(self):
        try:
            import comtypes
            comtypes.CoInitialize()  # pycaw needs COM on this thread
        except Exception:
            pass
        while True:
            mode, pcm, secs, released = self.jobs.get()
            self.busy = True
            try:
                waited = time.time()
                while not self.stt.ready and not self.stt.error and time.time() - waited < 40:
                    time.sleep(0.05)  # loading back after a game: it was started on the key press
                t0 = time.time()
                text = self.stt.transcribe(pcm, language=self._language(mode))
                heard_in = time.time() - t0
                log.info("heard (%s, %.2fs audio, %.2fs to text): %r", mode, secs, heard_in, text)
                if not text:
                    osd.show("Didn't catch that", "info", 2)
                elif mode == "dictate" and not re.match(engine.WAKE, engine.clean(text)):
                    osd.hide()
                    win.type_unicode(text + " ")
                else:
                    self.run_text(text, woke=mode == "agent", took=time.time() - released)
                total = time.time() - released
                state.timings = (state.timings + [{"stt": round(heard_in, 2), "total": round(total, 2),
                                                   "audio": round(secs, 1)}])[-20:]
                log.info("timing: %.2fs to text, %.2fs from key release to done", heard_in, total)
            except Exception as e:
                log.exception("job failed")
                osd.show(f"Something went wrong: {e}", "error", 5)
            finally:
                self.busy = False
                self.last_used = time.time()
                self._ready_again()

    def run_text(self, text, woke=True, took=None):
        engine.CTX.raw, engine.CTX.last_target = text, None
        steps, woke = engine.plan(text, woke=woke)
        heard = re.sub(r"\s+", " ", text).strip()
        if not steps:
            history.record(via="agent", heard=heard, clean=engine.clean(text), result="unmatched")
            beep("error")
            osd.show(heard, "error", 3.5, title="Didn't understand", footer="say “what can I say” for ideas")
            return
        chips = [(s[:1].upper() + s[1:])[:40] for _, _, s in steps]
        footer = f"{took:.1f} s · {self._engine_name()}" if took is not None else self._engine_name()
        osd.show(heard, "ok", 2.5, chips=chips, footer=footer)
        errors = []
        for i, (r, groups, _) in enumerate(steps):
            try:
                r.fn(*groups)
            except Exception as e:
                log.exception("%s failed", r.say)
                errors.append(f"{r.say}: {e}")
                osd.show(f"{r.say}: {e}", "error", 5, title="Problem")
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
    def change_key(self, mode):
        """Tray → Push-to-talk keys: press the new key, it works straight away."""
        def go():
            from . import dialogs
            old = config.get(f"{mode}_key")
            combo = dialogs.ask("pick-key", mode, old)
            if not combo or combo == old:
                return
            other = "dictate" if mode == "agent" else "agent"
            if combo == config.get(f"{other}_key"):
                self.tray.notify(f"{combo.upper()} is already the {'typing' if other == 'dictate' else 'commands'} key")
                return
            self.hotkeys.unregister(mode)
            if self.hotkeys.register(mode, combo):
                config.set(f"{mode}_key", combo)
                state.hotkeys[mode] = True
                osd.show(f"{'Commands' if mode == 'agent' else 'Typing'} key is now {combo.upper()}", "ok", 3)
                self._ready_again()
            else:
                state.hotkeys[mode] = self.hotkeys.register(mode, old)
                self.tray.notify(f"{combo.upper()} is taken by another app, kept {old.upper()}")
        threading.Thread(target=go, daemon=True).start()

    def set_model(self, model):
        """Tray → Speech model: switch (downloading it first if needed)."""
        def go():
            if model in speech.CLOUD and not speech.api_key(model):
                from . import dialogs
                key = dialogs.ask("api-key", model)
                if not key:
                    return
                speech.set_api_key(model, key)
            if model == config.get("model") and self.stt.ready:
                return
            config.set("model", model)
            with self.load_lock:
                self.stt.stop()
                self.stt = speech.make(on_progress=self._progress)
                state.stt, state.usage = self.stt, {}
            if self._load():
                name = speech.MODELS.get(model, speech.CLOUD.get(model, (model,)))[0].split(":")[0].split(" (")[0]
                osd.show(f"Speech model: {name}", "ok", 3)
                self.check_language()
        threading.Thread(target=go, daemon=True).start()

    def set_cloud_key(self, provider):
        def go():
            from . import dialogs
            key = dialogs.ask("api-key", provider)
            if key is None:
                return
            speech.set_api_key(provider, key)
            self.tray.notify("API key saved" if key else "API key removed")
            if config.get("model") == provider:
                with self.load_lock:
                    self.stt.stop()
                    self.stt = speech.make(on_progress=self._progress)
                    state.stt = self.stt
                self._load()
        threading.Thread(target=go, daemon=True).start()

    def delete_models(self):
        freed = speech.delete_unused()
        self.tray.notify(f"Deleted unused models: {freed} MB freed" if freed else "No unused models")

    def check_language(self):
        if config.get("dictate_language") != "en" and ".en" in config.get("model"):
            self.tray.notify("Typing in Hindi needs the Best model or a cloud model: tray → Speech model")

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
            if self.rec.active or self.busy:
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
    win.dpi_aware()          # crisp tray menu and pill on scaled screens
    win.follow_theme_menus()  # dark menus when Windows is dark
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
