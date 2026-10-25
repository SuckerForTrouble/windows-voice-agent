"""The tray panel: click the tray icon (left or right) and this opens above it, Windows 11
quick-settings style: status, four switch tiles, the pill style, microphone, speech model,
and buttons. The classic menu is one click away ("More options…").

Kept light: the whole panel is ONE canvas (a few dozen shapes, no widget tree), drawn
on the pill's GUI thread (no extra process), built when it opens and freed when it
closes. Nothing runs while it's closed. Clicking anywhere else or Esc closes it."""
import ctypes
import sys
import threading
import time

from . import config, listen, osd
from .osd import _rounded

W, PAD = 360, 16
BG, CARD, HOVER, LINE = "#1b1e27", "#262a36", "#30354a", "#333848"
INK, SOFT, ACCENT, ON_INK, DANGER = "#eef0f5", "#9aa2b3", "#8b95ff", "#10121a", "#f76b15"
DOT = {"ready": "#46a758", "listen": "#e5484d", "busy": "#f5a623", "paused": "#9aa2b3", "loading": "#9aa2b3",
       "error": "#f76b15"}
FONT = "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"

_panel = None
_closed_at = 0.0


def icon(c, kind, x, y, color, tag):
    """Tile icons drawn as shapes: no font has to have the symbol."""
    t = (tag,)
    if kind == "listen":    # a dot with sound waves either side
        c.create_oval(x - 3, y - 3, x + 3, y + 3, fill=color, outline="", tags=t)
        for r in (7, 11):
            c.create_arc(x - r, y - r, x + r, y + r, start=-40, extent=80, style="arc", outline=color, width=2, tags=t)
            c.create_arc(x - r, y - r, x + r, y + r, start=140, extent=80, style="arc", outline=color, width=2, tags=t)
    elif kind == "pause":   # two bars
        for dx in (-5, 3):
            _rounded(c, x + dx, y - 8, x + dx + 4, y + 8, 2, fill=color)
            c.addtag_overlapping(tag, x + dx, y - 8, x + dx + 4, y + 8)
    elif kind == "voice":   # a speech bubble
        _rounded(c, x - 10, y - 8, x + 10, y + 5, 4, fill=color)
        c.create_polygon(x - 6, y + 4, x - 1, y + 4, x - 7, y + 10, fill=color, outline="", tags=t)
        c.addtag_overlapping(tag, x - 10, y - 8, x + 10, y + 10)
    elif kind == "beeps":   # a note
        c.create_oval(x - 7, y + 2, x + 1, y + 8, fill=color, outline="", tags=t)
        c.create_line(x + 1, y + 5, x + 1, y - 9, fill=color, width=2, tags=t)
        c.create_line(x + 1, y - 9, x + 7, y - 5, fill=color, width=2, tags=t)


def chevron(c, x, y, up, color, tag):
    d = -4 if up else 4
    c.create_line(x - 5, y - d / 2, x, y + d / 2, x + 5, y - d / 2, fill=color, width=2, capstyle="round",
                  joinstyle="round", tags=(tag,))


def draw(c, m, on, mic_open=False):
    """Draw snapshot m on canvas c; clicks call on(action). Returns the height."""
    f = {"title": (FONT, 12, "bold"), "body": (FONT, 10), "bold": (FONT, 10, "bold"), "small": (FONT, 9),
         "glyph": (FONT, 15), "tiny": (FONT, 8)}
    c.delete("all")
    n = [0]

    def press(x0, y0, x1, y1, action, fill=CARD, hover=HOVER, r=10):
        """A clickable rounded area; returns its group tag for the content drawn on top."""
        n[0] += 1
        g = f"g{n[0]}"
        bg = _rounded(c, x0, y0, x1, y1, r, fill=fill)
        c.addtag_withtag(g, bg)
        c.tag_bind(g, "<Enter>", lambda e: (c.itemconfigure(bg, fill=hover), c.configure(cursor="hand2")))
        c.tag_bind(g, "<Leave>", lambda e: (c.itemconfigure(bg, fill=fill), c.configure(cursor="")))
        c.tag_bind(g, "<Button-1>", lambda e: on(action))
        return g

    def text(x, y, s, font, fill=INK, anchor="w", tag=None):
        return c.create_text(x, y, text=s, font=f[font], fill=fill, anchor=anchor, tags=(tag,) if tag else ())

    # header -------------------------------------------------------------------
    y = PAD
    c.create_oval(PAD, y + 4, PAD + 10, y + 14, fill=DOT.get(m["kind"], DOT["ready"]), outline="")
    text(PAD + 18, y + 9, "Voice Agent", "title")
    text(W - PAD, y + 9, f"v{m['version']}", "tiny", SOFT, "e")
    y += 26
    status = m["status"] if len(m["status"]) <= 54 else m["status"][:52] + "…"
    text(PAD, y + 8, status, "small", SOFT)
    y += 18
    bits = [m["engine"]] + [x for x in (m.get("ram"), m.get("vram"), m.get("last")) if x]
    text(PAD, y + 8, "  ·  ".join(b for b in bits if b), "small", SOFT)
    y += 28

    # four switch tiles --------------------------------------------------------
    tiles = [("listen", "Always listening", f"say “{m['call_word']}”", m["always_listen"]),
             ("pause", "Pause", "keys and mic off", m["paused"]),
             ("voice", "Spoken answers", "read answers out", m["voice_replies"]),
             ("beeps", "Beeps", "start / stop sounds", m["sounds"])]
    tw, th, gap = (W - 2 * PAD - 10) / 2, 62, 10
    for i, (action, title, sub, on_) in enumerate(tiles):
        x0, y0 = PAD + (i % 2) * (tw + gap), y + (i // 2) * (th + gap)
        g = press(x0, y0, x0 + tw, y0 + th, action, fill=ACCENT if on_ else CARD, hover="#a3abff" if on_ else HOVER,
                  r=12)
        ink, soft = (ON_INK, "#2a2f55") if on_ else (INK, SOFT)
        icon(c, action, x0 + 24, y0 + th / 2, ink, g)
        text(x0 + 46, y0 + 23, title, "bold", ink, tag=g)
        text(x0 + 46, y0 + 42, sub if len(sub) < 22 else sub[:20] + "…", "small", soft, tag=g)
    y += 2 * th + gap + 18

    # pill style ---------------------------------------------------------------
    text(PAD, y, "Pill on screen", "small", SOFT)
    y += 12
    styles = [("off", "Off"), ("minimal", "Minimal"), ("advanced", "Advanced"), ("funky", "Funky")]
    cur = m["osd_style"] if m["osd"] else "off"
    sw = (W - 2 * PAD) / len(styles)
    _rounded(c, PAD, y, W - PAD, y + 32, 10, fill=CARD)
    for i, (sid, label) in enumerate(styles):
        x0 = PAD + i * sw
        if sid == cur:
            g = press(x0 + 3, y + 3, x0 + sw - 3, y + 29, f"pill:{sid}", fill=ACCENT, hover="#a3abff", r=8)
            text(x0 + sw / 2, y + 16, label, "bold", ON_INK, "center", g)
        else:
            g = press(x0 + 3, y + 3, x0 + sw - 3, y + 29, f"pill:{sid}", fill=CARD, hover=HOVER, r=8)
            text(x0 + sw / 2, y + 16, label, "body", INK, "center", g)
    y += 44

    # microphone and speech model rows -------------------------------------------
    for action, label, value, right in (("mic", "Microphone", m["mic"], None),
                                        ("model", "Speech model", m["model"], "Change…")):
        g = press(PAD, y, W - PAD, y + 46, action)
        text(PAD + 14, y + 14, label, "small", SOFT, tag=g)
        value = value if len(value) <= 40 else value[:38] + "…"
        text(PAD + 14, y + 31, value, "bold", tag=g)
        if right:
            text(W - PAD - 14, y + 23, right, "small", ACCENT, "e", g)
        else:
            chevron(c, W - PAD - 20, y + 23, mic_open, ACCENT, g)
        y += 52
        if action == "mic" and mic_open:
            for name in m.get("mics", []):
                sel = name == m["mic"]
                g = press(PAD + 12, y, W - PAD, y + 30, f"mic:{name}", fill=HOVER if sel else BG, hover=HOVER, r=8)
                text(PAD + 26, y + 15, ("●  " if sel else "    ") + (name if len(name) <= 42 else name[:40] + "…"),
                     "body", INK if sel else SOFT, tag=g)
                y += 32
            y += 6

    # buttons ------------------------------------------------------------------
    y += 4
    buttons = [("guide", "What can I say?"), ("settings", "Settings…"), ("checkup", "Check setup")]
    bw = (W - 2 * PAD - 16) / 3
    for i, (action, label) in enumerate(buttons):
        x0 = PAD + i * (bw + 8)
        g = press(x0, y, x0 + bw, y + 36, action, fill=CARD if i else ACCENT, hover=HOVER if i else "#a3abff", r=18)
        text(x0 + bw / 2, y + 18, label, "bold" if not i else "body", ON_INK if not i else INK, "center", g)
    y += 50

    # footer -------------------------------------------------------------------
    c.create_line(PAD, y, W - PAD, y, fill=LINE)
    y += 8
    g = press(PAD - 6, y, PAD + 120, y + 28, "more", fill=BG, hover=CARD, r=8)
    text(PAD + 2, y + 14, "More options…", "small", ACCENT, tag=g)
    g = press(W - PAD - 60, y, W - PAD + 6, y + 28, "quit", fill=BG, hover="#3a2420", r=8)
    text(W - PAD - 27, y + 14, "Quit", "small", DANGER, "center", g)
    y += 30
    text(W / 2, y + 6, "made by profane for Billa Janta Party", "tiny", "#5d6577", "center")
    return y + 18


def toggle(app):
    osd.ui(lambda root: _toggle(app, root))


def _toggle(app, root):
    global _panel
    if _panel:
        _panel.close()
    elif time.time() - _closed_at > 0.4:  # not the click that just closed it (focus jumped to the tray)
        _panel = Panel(app, root)


class Panel:
    def __init__(self, app, root):
        import tkinter as tk
        self.app, self.mic_open = app, False
        top = self.top = tk.Toplevel(root)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.configure(bg=BG)
        self.c = tk.Canvas(top, width=W, height=100, bg=BG, highlightthickness=0, bd=0)
        self.c.pack()
        self.render()
        top.update_idletasks()
        self.hwnd = None
        if sys.platform == "win32":
            from . import win
            self.hwnd = ctypes.windll.user32.GetParent(top.winfo_id()) or top.winfo_id()
            win.modern_window(self.hwnd, dark=True)  # rounded corners and a hairline border on Windows 11
            win.focus(self.hwnd)
        top.focus_force()
        top.bind("<FocusOut>", lambda e: top.after(150, self._maybe_close))
        top.bind("<Escape>", lambda e: self.close())

    def snapshot(self):
        from . import __version__, hotkey, state, stt
        a = self.app
        s = a.stt
        kind = ("paused" if state.paused else "listen" if a.rec.active else "error" if s.error
                else "loading" if not s.ready else "ready")
        u = state.usage
        m = {"kind": kind, "status": state.status, "version": __version__, "engine": a._engine_name(),
             "ram": f"{u['ram']} MB RAM" if u.get("ram") else "", "vram": f"{u['vram'] / 1000:.1f} GB VRAM" if u.get("vram") else "",
             "last": f"last {state.timings[-1]['total']:.1f} s" if state.timings else "",
             "call_word": listen.call_words(config.get("call_word"))[0].title(), "always_listen": config.get("always_listen"),
             "paused": state.paused, "voice_replies": config.get("voice_replies"), "sounds": config.get("sounds"),
             "osd": config.get("osd"), "osd_style": config.get("osd_style"),
             "mic": config.get("mic") or "Windows default",
             "model": stt.MODELS.get(s.model, (s.model,))[0].split(":")[0] if s.backend != "cloud" else s.device,
             "key": hotkey.label(config.get("agent_key"))}
        if self.mic_open:
            from . import recorder
            try:
                m["mics"] = ["Windows default"] + recorder.input_devices()
            except Exception:
                m["mics"] = ["Windows default"]
        return m

    def render(self):
        h = draw(self.c, self.snapshot(), self.do, self.mic_open)
        self.c.configure(height=h)
        self._place(h)

    def _place(self, h):
        x, y, w, hh = self._work_area()
        self.top.geometry(f"{W}x{int(h)}+{int(x + w - W - 12)}+{int(y + hh - h - 12)}")

    def _work_area(self):
        """The work area (screen minus taskbar) of the monitor the mouse is on."""
        if sys.platform == "win32":
            from . import win
            return win.work_area_at_cursor()
        return 0, 0, self.top.winfo_screenwidth(), self.top.winfo_screenheight() - 48

    def _maybe_close(self):
        try:
            if self.top.focus_get() is None:
                self.close()
        except Exception:
            self.close()

    def close(self):
        global _panel, _closed_at
        _closed_at = time.time()
        _panel = None
        try:
            self.top.destroy()
        except Exception:
            pass

    def later(self, fn):
        """App actions can block (keys re-registering, the mic opening): off this thread, then redraw."""
        threading.Thread(target=fn, daemon=True).start()
        self.top.after(300, lambda: self.top.winfo_exists() and self.render())

    def do(self, action):
        a = self.app
        if action == "listen":
            self.later(a.toggle_listen)
        elif action == "pause":
            self.later(a.toggle_pause)
        elif action in ("voice", "beeps"):
            key = {"voice": "voice_replies", "beeps": "sounds"}[action]
            config.set(key, not config.get(key))
            self.render()
        elif action.startswith("pill:"):
            style = action[5:]
            config.set("osd", style != "off")
            if style != "off":
                config.set("osd_style", style)
                osd.show(f"Pill style: {osd.STYLES[style]}", "ok", 2.5)
            self.render()
        elif action == "mic":
            self.mic_open = not self.mic_open
            self.render()
        elif action.startswith("mic:"):
            name = action[4:]
            config.set("mic", "" if name == "Windows default" else name)
            self.mic_open = False
            self.later(a.mic_changed)
        else:  # these open something else: the panel steps aside
            self.close()
            {"model": a.open_settings, "settings": a.open_settings,
             "guide": lambda: a.do("guide.open_guide"), "checkup": lambda: a.do("checkup.run_and_open"),
             "more": a.tray.show_menu, "quit": a.quit}[action]()
