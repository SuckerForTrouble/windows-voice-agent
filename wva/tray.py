"""The tray icon: its colour says what the agent is doing (grey loading, blue ready,
red listening, amber thinking), and its menu holds every setting, so nobody has
to edit a file. The default is the light one: push-to-talk, the pill, beeps.
Everything extra is off until you turn it on (tray, or Settings…)."""
import os
import sys

import pystray

from . import APP_NAME, config, paths, state, stt
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

    def _checked(self, key):
        return lambda item: bool(config.get(key))

    # pystray only takes handlers of (icon, item) or fewer: a value baked in as a default
    # argument (lambda icon, item, m=mid) makes it refuse the whole menu, so these close over it.
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
            M(lambda i: self._in_use(), lambda: None, enabled=False),
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
