"""The running agent: tray icon, push-to-talk keys, microphone -> speech model -> commands.

Hold the agent key (F9) and talk; let go and it runs. A quick tap toggles
instead (tap, talk, tap). Esc while listening cancels. The dictation key (F10)
types what you say; "computer …" through it still runs a command.
While a game runs the speech model can step out of graphics memory; the next
key press loads it back while you talk."""
import importlib
import json
import logging
import logging.handlers
import os
import queue
import re
import sys
import threading
import time

from . import (APP_ID, APP_NAME, __version__, actions, apps, config, engine, history, hotkey, listen, osd, paths, speak, state,
               system, tuning, ui, updater, usage, win)
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
        self.listener = None    # always listening (opt-in)
        self.discord = None     # commands from Discord audio (dangerous opt-in, off at every start, never saved)
        self.follow = {"listen": 0.0, "discord": 0.0}  # after the call word alone: the next phrase is the command
        self.first_run = not paths.CONFIG.exists()
        osd.level_source = lambda: self.rec.level  # the pill's mic meter
        state.reload_stt = self.reload_stt

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
        if not config.get("welcome_done"):  # before the keys and the model: it picks both
            self._welcome()
        self._register_keys()  # before the model: the keys work (and say "loading…") meanwhile
        threading.Thread(target=self._update_loop, daemon=True, name="updates").start()
        if self.first_run:
            mb = speech.MODELS.get(config.get("model"), ("", 0))[1]
            osd.show(f"{APP_NAME} is getting ready" + (f": downloading the speech model ({mb} MB) once." if mb else "."),
                     "busy", 0)
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

    SETTINGS = ("agent_key", "dictate_key", "model", "always_listen", "call_word", "music_app", "movie_app", "browser",
                "voice_replies", "sounds", "start_with_windows", "unload_in_games", "auto_update", "dictate_language",
                "osd", "osd_style")

    def _ask_settings(self, first_run):
        import tempfile

        from . import dialogs
        cur = {k: config.get(k) for k in self.SETTINGS}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(cur, f)
        try:
            return dialogs.ask("settings", f.name, "1" if first_run else "0", timeout=3600)
        finally:
            os.unlink(f.name)

    def _welcome(self):
        """First start (and once after updating to this version): pick keys, model, apps…
        before anything downloads. Closing it keeps the defaults."""
        new = self._ask_settings(first_run=True)
        for k, v in (new or {}).items():
            if k in self.SETTINGS and k != "start_with_windows":
                config.set(k, v)
        if new and new.get("start_with_windows") != config.get("start_with_windows"):
            self.set_startup(new["start_with_windows"])
        config.set("welcome_done", True)
        if new and new.get("model") != self.stt.model:  # made at start-up with the old choice
            self.stt = speech.make(on_progress=self._progress)
            state.stt = self.stt

    def open_settings(self):
        """Tray → Settings…: the same window; changes apply straight away."""
        def go():
            new = self._ask_settings(first_run=False)
            if new:
                self.apply_settings(new)
        threading.Thread(target=go, daemon=True).start()

    def apply_settings(self, new):
        changed = {k: v for k, v in new.items() if k in self.SETTINGS and config.get(k) != v}
        if not changed:
            return
        for mode in ("agent", "dictate"):  # keys: re-register, keep the old one if Windows says no
            key = f"{mode}_key"
            if key in changed:
                old = config.get(key)
                self.hotkeys.unregister(mode)
                if self.hotkeys.register(mode, changed[key]):
                    config.set(key, changed[key])
                    state.hotkeys[mode] = True
                else:
                    state.hotkeys[mode] = self.hotkeys.register(mode, old)
                    self.tray.notify(f"{hotkey.label(changed[key])} couldn't be used, kept {hotkey.label(old)}")
        if "start_with_windows" in changed:
            self.set_startup(changed["start_with_windows"])
        for k, v in changed.items():
            if k not in ("agent_key", "dictate_key", "start_with_windows", "model"):
                config.set(k, v)
        if "model" in changed:
            self.set_model(changed["model"])  # downloads it if needed, then loads
        elif "always_listen" in changed or "call_word" in changed:
            if config.get("always_listen") and self.stt.backend == "cloud":
                config.set("always_listen", False)
                self.tray.notify("Always listening needs a speech model on this PC, not a cloud one.")
            self._sync_listener()
        self._ready_again()
        osd.show("Settings saved", "ok", 2.5)

    def _register_keys(self):
        from .hotkey import Hotkeys
        self.hotkeys = Hotkeys(self._pressed, self._released)
        for mode in ("agent", "dictate"):
            ok = self.hotkeys.register(mode, config.get(f"{mode}_key"))
            state.hotkeys[mode] = ok
            if not ok:
                msg = f"{hotkey.label(config.get(f'{mode}_key'))} is taken by another app: tray → Push-to-talk keys to pick another."
                self.tray.notify(msg)
                log.warning(msg)

    def reload_stt(self):
        """The speech model again with the current settings (the setup check found the other
        backend faster)."""
        with self.load_lock:
            self.stt.stop()
            self.stt = speech.make(on_progress=self._progress)
            state.stt, state.usage = self.stt, {}
        if self._load():
            osd.show(f"Speech model now on the {'CPU' if self.stt.backend == 'cpu' else 'GPU'}: it's faster here", "ok", 4)

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
            osd.show(f"Ready: hold {hotkey.label(config.get('agent_key'))} and talk", "ok", 3)
        threading.Thread(target=usage.refresh, args=(self.stt,), daemon=True).start()
        self._sync_listener()
        return True

    def _unload(self, game):
        self.stt.stop()
        state.usage = {}
        self._ready_again()
        if self.told_game != game:
            self.told_game = game
            osd.show(f"{game} is running: the speech model stepped out of graphics memory. "
                     f"Press {hotkey.label(config.get('agent_key'))} any time, it loads back while you talk.", "info", 7)
        log.info("unloaded for %s", game)

    def _watch_games(self):
        """Every few seconds: a game started -> unload; it ended -> load again."""
        while True:
            time.sleep(5)
            try:
                local = self.stt.backend != "cloud"
                hearing = config.get("always_listen") or self.discord  # these need the model loaded, game or not
                if hearing and local and not self.stt.ready and not self.stt.error:
                    self._load()
                    continue
                unload = config.get("unload_in_games") and local and not hearing
                game = usage.game_running() if unload else ""
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
        key = hotkey.label(config.get("agent_key"))
        if not self.stt.ready and state.gaming:
            return f"Game mode: press {key}, the model loads back while you talk"
        where = {"vulkan": "GPU", "cpu": "CPU", "cloud": "cloud"}.get(self.stt.backend, "")
        call = f", or say “{listen.call_words(config.get('call_word'))[0].title()} …”" if self.listener else ""
        warn = "  ·  ⚠ Discord audio runs commands" if self.discord else ""
        return f"Ready: hold {key} and talk{call}" + (f" ({where})" if where else "") + warn

    def _ready_again(self):
        if state.paused:
            return
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
                if mode in ("listen", "discord"):
                    self._overheard(pcm, secs, released, via=mode)
                    continue
                waited = time.time()
                while not self.stt.ready and not self.stt.error and time.time() - waited < 40:
                    time.sleep(0.05)  # loading back after a game: it was started on the key press
                t0 = time.time()
                idle = t0 - self.last_used if self.last_used else 0.0
                text = self.stt.transcribe(pcm, language=self._language(mode))
                heard_in = time.time() - t0
                model_ms = getattr(self.stt, "last_ms", None)
                log.info("heard (%s, %.2fs audio, %.2fs to text, the model's own %s ms, idle %.0fs before): %r",
                         mode, secs, heard_in, model_ms, idle, text)
                if not text:
                    osd.show("Didn't catch that", "info", 2)
                elif mode == "dictate" and not re.match(engine.WAKE, engine.clean(text)):
                    osd.hide()
                    win.type_unicode(text + " ")
                else:
                    self.run_text(text, woke=mode == "agent", took=time.time() - released)
                total = time.time() - released
                state.timings = (state.timings + [{"stt": round(heard_in, 2), "total": round(total, 2),
                                                   "audio": round(secs, 1), "idle": round(idle), "model_ms": model_ms}])[-20:]
                log.info("timing: %.2fs to text, %.2fs from key release to done", heard_in, total)
            except Exception as e:
                log.exception("job failed")
                osd.show(f"Something went wrong: {e}", "error", 5)
            finally:
                self.busy = False
                self.last_used = time.time()
                self._ready_again()

    # ------------------------------------------------------------- always listening
    def _sync_listener(self):
        """Open or close the always-on mic to match the settings (and what the model allows)."""
        want = config.get("always_listen") and self.stt.ready and self.stt.backend != "cloud" and not state.paused
        if want and not self.listener:
            lst = listen.Listener(self._phrase, paused=lambda: self.rec.active)
            try:
                lst.start(config.get("mic"))
                self.listener = lst
                log.info("always listening for %r", config.get("call_word"))
            except Exception as e:
                self.tray.notify(f"Always listening couldn't open the mic: {e}")
        elif not want and self.listener:
            self.listener.stop()
            self.listener = None
        state.listening = bool(self.listener)
        self._ready_again()

    def _phrase(self, pcm, via="listen"):
        """From the open mic's thread (via="discord": from Discord's sound). While a command is
        still running, new phrases are dropped rather than queued (nobody wants a backlog)."""
        if self.jobs.qsize() < 2:
            self.jobs.put((via, pcm, len(pcm) / 32000, time.time()))

    def _overheard(self, pcm, secs, heard_at, via="listen"):
        """A phrase the open mic (or Discord's sound) caught: acted on only if it starts with
        the call word. Anything else is dropped here, unseen: no pill, no history, no log of the words."""
        if not self.stt.ready or self.stt.backend == "cloud":  # overheard talk never goes to the cloud
            return
        text = self.stt.transcribe(pcm, language=self._language("agent"))
        word = config.get("call_word")
        rest = listen.strip_call(text, word) if text else None
        if rest is None and text and time.time() < self.follow[via]:
            rest = text  # the command that followed the call word on its own
        if rest is None:
            log.info("%s: let %.1fs of speech go", via, secs)
            return
        source = "Discord" if via == "discord" else None
        if rest == "":
            self.follow[via] = time.time() + 6
            beep("start")
            osd.show("Listening…", "listen", 6, source=source)
            return
        self.follow[via] = 0.0
        log.info("call word (%s), then: %r", via, rest)
        self.run_text(rest, woke=True, took=time.time() - heard_at, via=via)

    def toggle_panel(self):
        from . import panel
        panel.toggle(self)

    def toggle_pause(self):
        """Tray → Pause for now: the keys stop being ours and the always-on mic closes, until unticked
        (a competitive game that wants F9, a meeting…). The model stays loaded, so resuming is instant."""
        state.paused = not state.paused
        if state.paused:
            if self.rec.active:
                self._cancel()
            self.hotkeys.unregister_all()
            if self.listener:
                self.listener.stop()
                self.listener = None
            self._discord_off("paused")
            self.tray.set("loading", "Paused: tray → untick Pause to use it again")
            osd.show("Paused: keys and mic off", "info", 2.5)
        else:
            for mode in ("agent", "dictate"):
                state.hotkeys[mode] = self.hotkeys.register(mode, config.get(f"{mode}_key"))
            self._sync_listener()
            osd.show("Back on", "ok", 2)

    def toggle_listen(self):
        on = not config.get("always_listen")
        if on and self.stt.backend == "cloud":
            self.tray.notify("Always listening needs a speech model on this PC (a cloud model would get everything "
                             "said near the mic): tray → Speech model, pick Parakeet or Best first.")
            return
        config.set("always_listen", on)
        self._sync_listener()
        if on:
            names = " or ".join(f"“{w.title()}”" for w in listen.call_words(config.get("call_word")))
            osd.show(f"Always listening: say {names} first. The mic stays on; anything "
                     "that doesn't start with the call word is thrown away.", "info", 7)
        else:
            osd.show("Always listening off: push-to-talk only", "info", 3)

    def change_call_word(self):
        def go():
            from . import dialogs
            word = dialogs.ask("call-word", config.get("call_word"))
            if not word:
                return
            why = listen.call_word_ok(word)
            if why:
                self.tray.notify(f"Call word not changed: {why}")
                return
            word = ", ".join(listen.call_words(word))
            config.set("call_word", word)
            self._ready_again()
            osd.show(f"Call word{'s' if ',' in word else ''}: “{word.title()}”", "ok", 3)
        threading.Thread(target=go, daemon=True).start()

    def toggle_discord_audio(self):
        """Tray → Commands from Discord audio: what the Discord call plays is listened to for the
        call word, and those commands run here. Dangerous: a big warning first, off at every
        start (it's never saved), and nothing is filtered (the user asked for that)."""
        def go():
            if self.discord:
                return self._discord_off()
            if self.stt.backend == "cloud":
                return self.tray.notify("Needs a speech model on this PC: with a cloud one, your friends' voices "
                                        "would be sent to the cloud.")
            if not self.stt.ready:
                return self.tray.notify("The speech model isn't loaded yet: try again in a moment.")
            from . import dialogs, loopback
            words = " or ".join(w.title() for w in listen.call_words(config.get("call_word")))
            if dialogs.ask("discord-audio", words, "" if loopback.process_loopback_ok() else "whole-pc") != "on":
                return
            lst = loopback.DiscordListener(lambda pcm: self._phrase(pcm, "discord"),
                                           paused=lambda: self.rec.active or state.paused,
                                           on_closed=lambda why: self._discord_off(why))
            try:
                lst.start()
            except Exception as e:
                return self.tray.notify(f"Commands from Discord audio didn't start: {e}")
            self.discord = lst
            state.discord_audio = True
            self._ready_again()
            log.info("commands from Discord audio: ON (%s)", "whole PC" if lst.whole_pc else "Discord only")
            osd.show(f"Anyone in your Discord call can now run commands on this PC by saying “{words} …”. "
                     "Tray → untick it to stop.", "error", 9, title="Discord audio runs commands", source="Discord")
        threading.Thread(target=go, daemon=True).start()

    def _discord_off(self, why=""):
        if not self.discord:
            return
        self.discord.stop()
        self.discord = None
        state.discord_audio = False
        self.follow["discord"] = 0.0
        log.info("commands from Discord audio: off (%s)", why or "unticked")
        self._ready_again()
        osd.show("Commands from Discord audio: off" + (f" ({why})" if why else ""), "info", 4)

    def mic_changed(self):
        if self.listener:  # reopen the always-on mic on the new microphone
            self.listener.stop()
            self.listener = None
            self._sync_listener()

    def run_text(self, text, woke=True, took=None, via=None):
        """via="discord": heard in Discord's sound, and the pill says so."""
        engine.CTX.raw, engine.CTX.last_target = text, None
        steps, woke = engine.plan(text, woke=woke)
        steps = actions.streamline(steps)
        heard = re.sub(r"\s+", " ", text).strip()
        source, via = ("Discord", "discord") if via == "discord" else (None, "agent")
        if not steps:
            history.record(via=via, heard=heard, clean=engine.clean(text), result="unmatched")
            beep("error")
            osd.show(heard, "error", 3.5, title="Didn't understand", footer="say “what can I say” for ideas", source=source)
            return
        chips = [(s[:1].upper() + s[1:])[:40] for _, _, s in steps]
        footer = f"{took:.1f} s · {self._engine_name()}" if took is not None else self._engine_name()
        osd.show(heard, "ok", 4 if source else 2.5, chips=chips, footer=footer, source=source)
        errors = []
        for i, (r, groups, _) in enumerate(steps):
            try:
                r.fn(*groups)
            except Exception as e:
                log.exception("%s failed", r.say)
                errors.append(f"{r.say}: {e}")
                beep("error")
                osd.show(f"{r.say}: {e}", "error", 5, title="Problem")
            if i + 1 < len(steps):
                time.sleep(r.after)
        history.record(via=via, heard=heard, clean=engine.clean(text), steps=[r.say for r, _, _ in steps],
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
                self.tray.notify(f"{hotkey.label(combo)} is already the {'typing' if other == 'dictate' else 'commands'} key")
                return
            self.hotkeys.unregister(mode)
            if self.hotkeys.register(mode, combo):
                config.set(f"{mode}_key", combo)
                state.hotkeys[mode] = True
                osd.show(f"{'Commands' if mode == 'agent' else 'Typing'} key is now {hotkey.label(combo)}", "ok", 3)
                self._ready_again()
            else:
                state.hotkeys[mode] = self.hotkeys.register(mode, old)
                why = "couldn't start the mouse helper" if combo in hotkey.MOUSE else "is taken by another app"
                self.tray.notify(f"{hotkey.label(combo)} {why}, kept {hotkey.label(old)}")
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
            if model in speech.CLOUD:  # never send what Discord plays to the cloud
                self._discord_off("a cloud model can't listen to Discord")
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
        choose=lambda title, items, footer, secs: osd.show("", "pick", secs, title=title, chips=items, footer=footer)
        if config.get("osd") else app.tray.notify(f"{title} " + "  ".join(f"{i}. {n}" for i, (n, _) in enumerate(items, 1))),
        speak=speak.say, unseen=osd.unseen,
        update=lambda: app.check_updates(interactive=True),
    )
    app.tray.run(app.start)
