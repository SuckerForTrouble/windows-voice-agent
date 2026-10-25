"""The tray icon: its colour says what the agent is doing (grey loading, blue ready,
red listening, amber thinking), and its menu holds every setting, so nobody has
to edit a file. The default is the light one: push-to-talk, the pill, beeps.
Everything extra is off until you turn it on (tray, or Settings…)."""
import os
import sys

import pystray

from . import APP_NAME, config, hotkey, osd, paths, state, stt
from .icon import icon_image


class Tray:
    def __init__(self, app):
        self.app = app
        self.kind = "loading"
        self.icon = pystray.Icon("WindowsVoiceAgent", icon_image("loading"), APP_NAME, menu=self._menu())
        self._hook_clicks()

    SHOW_MENU = 0x8051  # WM_APP + 0x51: "show the classic menu now" (posted by the panel's More options…)

    def _hook_clicks(self):
        """A click on the icon (left or right) opens the tray panel instead of the classic menu,
        which stays available through show_menu(). pystray keeps its Windows message handlers
        in a dict per icon, so this swaps one entry; elsewhere (tests) nothing changes."""
        handlers = getattr(self.icon, "_message_handlers", None)
        if sys.platform != "win32" or not handlers:
            return
        key = next((k for k, v in handlers.items() if getattr(v, "__name__", "") == "_on_notify"), None)
        if key is None:
            return
        classic = handlers[key]

        def on_click(wparam, lparam):
            if lparam in (0x0202, 0x0205):  # WM_LBUTTONUP, WM_RBUTTONUP
                self.app.toggle_panel()
                return 0
            return classic(wparam, lparam)
        handlers[key] = on_click
        handlers[self.SHOW_MENU] = lambda wparam, lparam: classic(0, 0x0205)

    def show_menu(self):
        hwnd = getattr(self.icon, "_hwnd", None)
        if hwnd:
            import ctypes
            ctypes.windll.user32.PostMessageW(hwnd, self.SHOW_MENU, 0, 0)

    def _toggle(self, key):
        def fn(icon, item):
            config.set(key, not config.get(key))
        return fn

    def _checked(self, key):
        return lambda item: bool(config.get(key))

    # pystray only takes handlers of (icon, item) or fewer: a value baked in as a default
    # argument (lambda icon, item, m=mid) makes it refuse the whole menu, so these close over it.
    def _is(self, key, value):
        return lambda item: config.get(key) == value

    def _call(self, fn, *args):
        return lambda icon, item: fn(*args)

    def _set(self, key, value, after=None):
        def fn(icon, item):
            config.set(key, value)
            if after:
                after()
        return fn

    # ------------------------------------------------------------- submenus
    def _mic_items(self):
        from . import recorder
        M = pystray.MenuItem
        items = [M("Windows default", self._set("mic", "", self.app.mic_changed), checked=lambda i: not config.get("mic"),
                   radio=True)]
        try:
            for name in recorder.input_devices():
                items.append(M(name, self._set("mic", name, self.app.mic_changed), checked=self._is("mic", name), radio=True))
        except Exception:
            pass
        return items

    def _in_use(self):
        """'In use: Best on the GPU · 140 MB RAM · 0.9 GB VRAM · last command 0.4 s' (measured)."""
        s = state.stt
        if not s:
            return "Not loaded"
        if s.backend == "cloud":
            parts = [f"In use: {s.device} (cloud) · no RAM or graphics memory used here"]
        elif not s.ready:
            return "In use: not loaded right now" + (" (a game is running)" if state.gaming else "")
        else:
            where = "the GPU" if s.backend == "vulkan" else "the CPU"
            name = stt.MODELS.get(s.model, (s.model,))[0].split(":")[0]
            parts = [f"In use: {name} on {where}"]
            u = state.usage
            if u.get("ram"):
                parts.append(f"{u['ram']} MB RAM")
            if u.get("vram"):
                parts.append(f"{u['vram'] / 1000:.1f} GB VRAM")
        if state.timings:
            parts.append(f"last command {state.timings[-1]['total']:.1f} s")
        return " · ".join(parts)

    def _model_items(self):
        M, S = pystray.MenuItem, pystray.Menu.SEPARATOR
        have = stt.downloaded()
        on_gpu = not state.stt or state.stt.backend != "cpu"
        items = [M(self._in_use(), lambda: None, enabled=False),
                 M(f"The {'GPU' if on_gpu else 'CPU'} only works while it turns speech into text: 0% when idle",
                   lambda: None, enabled=False), S]
        for mid, (label, mb, _, mem, cpu_speed) in stt.MODELS.items():
            size = "downloaded" if mid in have else f"{mb} MB download"
            cost = f"~{mem} MB VRAM + 100 MB RAM" if on_gpu else f"~{mem + 100} MB RAM, {cpu_speed} on CPU"
            items.append(M(f"{label}  ·  {cost}  ·  {size}", self._call(self.app.set_model, mid),
                           checked=self._is("model", mid), radio=True))
        items.append(S)
        for pid, (label, _, _) in stt.CLOUD.items():
            items.append(M(label, self._call(self.app.set_model, pid), checked=self._is("model", pid), radio=True))
        items.append(M("Set a cloud API key…", pystray.Menu(*[
            M(stt.CLOUD[p][0].split(" (")[0].replace("Cloud: ", ""), self._call(self.app.set_cloud_key, p))
            for p in stt.CLOUD])))
        unused = sum(mb for m, mb in have.items() if m != config.get("model"))
        items += [S, M(f"Delete unused models ({unused} MB)" if unused else "No unused models to delete",
                       lambda: self.app.delete_models(), enabled=bool(unused))]
        return items

    def _key_items(self):
        M = pystray.MenuItem
        return [M(lambda i: f"Commands key: {hotkey.label(config.get('agent_key'))}   (change…)", lambda: self.app.change_key("agent")),
                M(lambda i: f"Typing key: {hotkey.label(config.get('dictate_key'))}   (change…)", lambda: self.app.change_key("dictate"))]

    def _pill_items(self):
        M = pystray.MenuItem

        def pick(style):
            def fn(icon, item):
                config.set("osd", style != "off")
                if style != "off":
                    config.set("osd_style", style)
                    osd.show(f"Pill style: {osd.STYLES[style]}", "ok", 3)
            return fn
        return [M("Off", pick("off"), checked=lambda i: not config.get("osd"), radio=True)] + [
            M(label, pick(sid), checked=lambda i, sid=sid: config.get("osd") and config.get("osd_style") == sid, radio=True)
            for sid, label in osd.STYLES.items()]

    def _more(self):
        """The rarer options; the common ones are on the top level and in Settings…"""
        M, S = pystray.MenuItem, pystray.Menu.SEPARATOR
        lang = lambda v: self._set("dictate_language", v, self.app.check_language)  # noqa: E731
        clips = lambda v: self._set("clips", v)  # noqa: E731
        return pystray.Menu(
            M("Push-to-talk keys", pystray.Menu(lambda: self._key_items())),
            M(lambda i: f"Call word: “{config.get('call_word').title()}”   (change…)", lambda: self.app.change_call_word()),
            M("Typing language", pystray.Menu(
                M("English", lang("en"), checked=self._is("dictate_language", "en"), radio=True),
                M("Hindi (needs the Best model or cloud)", lang("hi"), checked=self._is("dictate_language", "hi"), radio=True),
                M("Detect it each time", lang("auto"), checked=self._is("dictate_language", "auto"), radio=True),
            )),
            S,
            M("Spoken answers (time, weather…)", self._toggle("voice_replies"), checked=self._checked("voice_replies")),
            M("Beeps", self._toggle("sounds"), checked=self._checked("sounds")),
            M("Show how long each command took", self._toggle("show_timing"), checked=self._checked("show_timing")),
            M("Free the GPU while a game runs (not while always listening)",
              self._toggle("unload_in_games"), checked=self._checked("unload_in_games")),
            M("Discord keybinds (mute inside games)", self._toggle("discord_keybinds"), checked=self._checked("discord_keybinds")),
            M("Clips with", pystray.Menu(
                M("NVIDIA app (Alt+F10)", clips("nvidia"), checked=self._is("clips", "nvidia"), radio=True),
                M("Xbox Game Bar (Win+Alt+G)", clips("xbox"), checked=self._is("clips", "xbox"), radio=True),
            )),
            S,
            M("Start with Windows", lambda: self.app.set_startup(not config.get("start_with_windows")),
              checked=self._checked("start_with_windows")),
            M("Update by itself", self._toggle("auto_update"), checked=self._checked("auto_update")),
        )

    def _menu(self):
        a = self.app
        M, S = pystray.MenuItem, pystray.Menu.SEPARATOR
        return pystray.Menu(
            M(lambda item: state.status, lambda: None, enabled=False),
            S,
            M("What can I say?", lambda: a.do("guide.open_guide"), default=True),
            M("Settings…", lambda: a.open_settings()),
            S,
            M("Pause for now (keys and mic off)", lambda: a.toggle_pause(), checked=lambda i: state.paused),
            M(lambda i: f"Always listening for “{config.get('call_word').title()}”", lambda: a.toggle_listen(),
              checked=self._checked("always_listen")),
            M("Pill on screen", pystray.Menu(lambda: self._pill_items())),
            M("Speech model", pystray.Menu(lambda: self._model_items())),
            M("Microphone", pystray.Menu(lambda: self._mic_items())),
            M("More options", self._more()),
            S,
            M("Help", pystray.Menu(
                M("Check my setup", lambda: a.do("checkup.run_and_open")),
                M("Teach it my voice", pystray.Menu(
                    M("1. Export my voice history for AI", lambda: a.do("tuning.export_for_ai")),
                    M("2. Import the AI's answer (copy it first)", lambda: a.do("tuning.import_from_clipboard")),
                    M("Open my tuning file", lambda: a.open_file(paths.TUNING)),
                    M("Clear my voice history", lambda: a.do("history.clear")),
                )),
                M("Check for updates", lambda: a.check_updates(interactive=True)),
                S,
                M("Open data folder (logs, history)", lambda: os.startfile(str(paths.DATA))),
                M("Open the settings file", lambda: a.open_file(paths.CONFIG)),
                M("Restart", lambda: a.restart()),
            )),
            M("Quit", lambda: a.quit()),
        )

    def set(self, kind, tooltip=None):
        if kind != self.kind:
            self.kind = kind
            self.icon.icon = icon_image(kind)
        if tooltip is not None:
            state.status = tooltip
            self.icon.title = f"{APP_NAME}: {tooltip}"[:127]
            self.icon.update_menu()

    def notify(self, msg):
        try:
            self.icon.notify(msg[:250], APP_NAME)
        except Exception:
            pass

    def run(self, setup):
        self.icon.run(setup=setup)

    def stop(self):
        self.icon.stop()
