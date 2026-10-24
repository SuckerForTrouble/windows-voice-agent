"""The tray icon: its colour says what the agent is doing (grey loading, blue ready,
red listening, amber thinking), and its menu holds every setting, so nobody has
to edit a file. The default is the light one: push-to-talk, the pill, beeps.
Everything else is in "Optional features" and off until you tick it."""
import os

import pystray

from . import APP_NAME, config, paths, state, stt
from .icon import icon_image


class Tray:
    def __init__(self, app):
        self.app = app
        self.kind = "loading"
        self.icon = pystray.Icon("WindowsVoiceAgent", icon_image("loading"), APP_NAME, menu=self._menu())

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
        items = [M("Windows default", self._set("mic", ""), checked=lambda i: not config.get("mic"), radio=True)]
        try:
            for name in recorder.input_devices():
                items.append(M(name, self._set("mic", name), checked=self._is("mic", name), radio=True))
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
        return [M(lambda i: f"Commands key: {config.get('agent_key').upper()}   (change…)", lambda: self.app.change_key("agent")),
                M(lambda i: f"Typing key: {config.get('dictate_key').upper()}   (change…)", lambda: self.app.change_key("dictate"))]

    def _optional(self):
        M, S = pystray.MenuItem, pystray.Menu.SEPARATOR
        lang = lambda v: self._set("dictate_language", v, self.app.check_language)  # noqa: E731
        clips = lambda v: self._set("clips", v)  # noqa: E731
        return pystray.Menu(
            M("Spoken answers (time, weather…)", self._toggle("voice_replies"), checked=self._checked("voice_replies")),
            M("On-screen pill", self._toggle("osd"), checked=self._checked("osd")),
            M("Beeps", self._toggle("sounds"), checked=self._checked("sounds")),
            M("Show how long each command took", self._toggle("show_timing"), checked=self._checked("show_timing")),
            M("Free the GPU while a game runs (model loads back when you press the key)",
              self._toggle("unload_in_games"), checked=self._checked("unload_in_games")),
            S,
            M("Typing language", pystray.Menu(
                M("English", lang("en"), checked=lambda i: config.get("dictate_language") == "en", radio=True),
                M("Hindi (needs the Best model or cloud)", lang("hi"),
                  checked=lambda i: config.get("dictate_language") == "hi", radio=True),
                M("Detect it each time", lang("auto"), checked=lambda i: config.get("dictate_language") == "auto", radio=True),
            )),
            M("Discord keybinds (mute inside games)", self._toggle("discord_keybinds"), checked=self._checked("discord_keybinds")),
            M("Clips with", pystray.Menu(
                M("NVIDIA app (Alt+F10)", clips("nvidia"), checked=lambda i: config.get("clips") == "nvidia", radio=True),
                M("Xbox Game Bar (Win+Alt+G)", clips("xbox"), checked=lambda i: config.get("clips") == "xbox", radio=True),
            )),
        )

    def _menu(self):
        a = self.app
        M, S = pystray.MenuItem, pystray.Menu.SEPARATOR
        return pystray.Menu(
            M(lambda item: state.status, lambda: None, enabled=False),
            S,
            M("What can I say?", lambda: a.do("guide.open_guide"), default=True),
            M("Check my setup", lambda: a.do("checkup.run_and_open")),
            S,
            M("Push-to-talk keys", pystray.Menu(lambda: self._key_items())),
            M("Speech model", pystray.Menu(lambda: self._model_items())),
            M("Microphone", pystray.Menu(lambda: self._mic_items())),
            M("Optional features", self._optional()),
            M("Teach it my voice", pystray.Menu(
                M("1. Export my voice history for AI", lambda: a.do("tuning.export_for_ai")),
                M("2. Import the AI's answer (copy it first)", lambda: a.do("tuning.import_from_clipboard")),
                M("Open my tuning file", lambda: a.open_file(paths.TUNING)),
                M("Clear my voice history", lambda: a.do("history.clear")),
            )),
            S,
            M("Start with Windows", lambda: a.set_startup(not config.get("start_with_windows")),
              checked=self._checked("start_with_windows")),
            M("Update by itself", self._toggle("auto_update"), checked=self._checked("auto_update")),
            M("Check for updates", lambda: a.check_updates(interactive=True)),
            M("More", pystray.Menu(
                M("Open the settings file", lambda: a.open_file(paths.CONFIG)),
                M("Open data folder (logs, history)", lambda: os.startfile(str(paths.DATA))),
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
