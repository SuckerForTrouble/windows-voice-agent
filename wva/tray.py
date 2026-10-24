"""The tray icon: its colour says what the agent is doing (grey loading, blue ready,
red listening, amber thinking), and its menu holds every setting, so nobody has
to edit a file."""
import os

import pystray

from . import APP_NAME, config, paths, state
from .icon import icon_image


class Tray:
    def __init__(self, app):
        self.app = app
        self.kind = "loading"
        self.icon = pystray.Icon("WindowsVoiceAgent", icon_image("loading"), APP_NAME, menu=self._menu())

    def _toggle(self, key, after=None):
        def fn(icon, item):
            config.set(key, not config.get(key))
            if after:
                after()
        return fn

    def _checked(self, key):
        return lambda item: bool(config.get(key))

    def _mic_items(self):
        from . import recorder

        def pick(name):
            def fn(icon, item):
                config.set("mic", name)
            return fn
        items = [pystray.MenuItem("Windows default", pick(""), checked=lambda i: not config.get("mic"), radio=True)]
        try:
            for name in recorder.input_devices():
                items.append(pystray.MenuItem(name, pick(name), checked=lambda i, n=name: config.get("mic") == n, radio=True))
        except Exception:
            pass
        return items

    def _menu(self):
        a = self.app
        M, S = pystray.MenuItem, pystray.Menu.SEPARATOR
        clips = lambda v: (lambda icon, item: config.set("clips", v))  # noqa: E731
        return pystray.Menu(
            M(lambda item: state.status, lambda: None, enabled=False),
            S,
            M("Voice guide (what can I say)", lambda: a.do("guide.open_guide"), default=True),
            M("Check my setup", lambda: a.do("checkup.run_and_open")),
            S,
            M("Teach it my voice", pystray.Menu(
                M("1. Export my voice history for AI", lambda: a.do("tuning.export_for_ai")),
                M("2. Import the AI's answer (copy it first)", lambda: a.do("tuning.import_from_clipboard")),
                M("Open my tuning file", lambda: a.open_file(paths.TUNING)),
                M("Clear my voice history", lambda: a.do("history.clear")),
            )),
            M("Microphone", pystray.Menu(lambda: self._mic_items())),
            M("Settings", pystray.Menu(
                M("Spoken answers", self._toggle("voice_replies"), checked=self._checked("voice_replies")),
                M("Beeps", self._toggle("sounds"), checked=self._checked("sounds")),
                M("On-screen pill", self._toggle("osd"), checked=self._checked("osd")),
                M("Discord keybinds (for in-game mute)", self._toggle("discord_keybinds"), checked=self._checked("discord_keybinds")),
                M("Clips with the NVIDIA app", clips("nvidia"), checked=lambda i: config.get("clips") == "nvidia", radio=True),
                M("Clips with Xbox Game Bar", clips("xbox"), checked=lambda i: config.get("clips") == "xbox", radio=True),
                M("Update by itself", self._toggle("auto_update"), checked=self._checked("auto_update")),
                M("Start with Windows", lambda: a.set_startup(not config.get("start_with_windows")),
                  checked=self._checked("start_with_windows")),
                M("Open the settings file", lambda: a.open_file(paths.CONFIG)),
            )),
            S,
            M("Check for updates", lambda: a.check_updates(interactive=True)),
            M("Open data folder (logs, history)", lambda: os.startfile(str(paths.DATA))),
            M("Restart", lambda: a.restart()),
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
