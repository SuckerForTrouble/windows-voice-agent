"""The pill at the top of the screen: "Listening…", what was heard and what it did,
answers and errors, in one of three styles (tray → Pill on screen, or Settings…):

  minimal   a slim pill: a dot and one short line (the default, the lightest)
  advanced  a card: title, what it heard, a chip per command, timing and model,
            a live mic meter while you talk
  funky     an animated colour gradient, bouncing level bars, playful titles

It never takes focus (the keys you asked for must reach the window you were in) and
clicks go straight through it. It animates only while it's on screen.

Over games: it is a topmost window, put back on top twice a second while it shows (some
games push themselves above other topmost windows), so it is seen over borderless and
"fullscreen optimized" games, which is how most games run on Windows 10 and 11. A game in
true exclusive fullscreen owns the screen: nothing outside the game can draw over it,
short of hooking into the game, which anti-cheat treats as a cheat (never done here).
unseen() spots that case, and then answers and notices are said out loud instead."""
import colorsys
import ctypes
import math
import queue
import random
import sys
import threading
import time

from . import config

STYLES = {"minimal": "Minimal", "advanced": "Advanced", "funky": "Funky"}
ACCENT = {"listen": "#e5484d", "ok": "#46a758", "error": "#f76b15", "info": "#8b95ff", "busy": "#a2a9b8"}
TITLE = {"listen": "Listening", "busy": "Working on it", "ok": "Done", "error": "Problem", "info": "Voice Agent"}
FUNKY = {"listen": ("✦ I'm all ears ✦",), "busy": ("Thinking…", "Hmm, one sec…"),
         "ok": ("Done! ✨", "On it! ⚡", "Boom ✨", "Easy ✓"), "error": ("Huh? ✗", "Say again? ✗"), "info": ("Psst ✦",)}
KEY = "#010203"          # painted transparent: the rounded corners
BG, INK, SOFT, LINE, CHIP = "#1b1e27", "#eef0f5", "#9aa2b3", "#2c303b", "#262a39"
TOP = 18
_q = queue.Queue()
_thread = None
level_source = None      # the app sets this: () -> 0..1, the mic level while listening


def _start():
    global _thread
    if _thread is None:
        _thread = threading.Thread(target=_loop, daemon=True, name="osd")
        _thread.start()


def show(text, kind="info", seconds=3.0, title=None, chips=None, footer=None):
    """kind: listen | busy | ok | error | info. seconds=0 keeps it up until the next call.
    title, chips (one per command) and footer are used by the richer styles."""
    if not config.get("osd"):
        return
    _start()
    _q.put({"text": text, "kind": kind, "seconds": seconds, "title": title, "chips": chips or [], "footer": footer or ""})


def ui(fn):
    """Run fn(root) on this thread's Tk (the tray panel lives here too: one GUI thread for both)."""
    _start()
    _q.put(fn)


def hide():
    if _thread is not None:
        _q.put(None)


_unseen = {"t": 0.0, "v": False}


def unseen():
    """A game in exclusive fullscreen is in front, so the pill can't be seen (Windows' own
    check, the one that holds back notifications: SHQueryUserNotificationState)."""
    if sys.platform != "win32":
        return False
    if time.time() - _unseen["t"] > 1.0:
        st = ctypes.c_int(0)
        try:
            ok = ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(st)) == 0
        except Exception:
            ok = False
        _unseen.update(t=time.time(), v=ok and st.value == 3)  # QUNS_RUNNING_D3D_FULL_SCREEN
    return _unseen["v"]


_ids = iter(range(1, 1 << 30))


def _rounded(c, x0, y0, x1, y1, r, fill="", outline="", width=1):
    """A rounded rectangle from four circles and two rectangles (Tk's smoothed polygons
    barely round the corners). Returns the tag of its parts, for tag_lower."""
    tag = f"rr{next(_ids)}"
    r = max(1, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    d = 2 * r
    corners = ((x0, y0, 90), (x1 - d, y0, 0), (x1 - d, y1 - d, 270), (x0, y1 - d, 180))
    if fill:
        for ax, ay, _ in corners:
            c.create_oval(ax, ay, ax + d, ay + d, fill=fill, outline="", tags=tag)
        c.create_rectangle(x0 + r, y0, x1 - r, y1, fill=fill, outline="", tags=tag)
        c.create_rectangle(x0, y0 + r, x1, y1 - r, fill=fill, outline="", tags=tag)
    if outline:
        for ax, ay, start in corners:
            c.create_arc(ax, ay, ax + d, ay + d, start=start, extent=90, style="arc", outline=outline,
                         width=width, tags=tag)
        for line in ((x0 + r, y0, x1 - r, y0), (x1, y0 + r, x1, y1 - r), (x0 + r, y1, x1 - r, y1), (x0, y0 + r, x0, y1 - r)):
            c.create_line(*line, fill=outline, width=width, tags=tag)
    return tag


def _corners(c, w, h, r, fill=KEY):
    """Paint the four corners outside a rounded rectangle (they turn transparent)."""
    steps = 12
    for cx, cy, a0, sx, sy in ((r, r, 90, 0, 0), (w - r, r, 0, w, 0), (w - r, h - r, 270, w, h), (r, h - r, 180, 0, h)):
        pts = [sx, sy]
        for i in range(steps + 1):
            a = math.radians(a0 + 90 * i / steps)
            pts += [cx + r * math.cos(a), cy - r * math.sin(a)]
        c.create_polygon(pts, fill=fill, outline="")


def _hue(h, s=0.75, v=0.95):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


class Pill:
    def __init__(self, root, canvas, screen_w):
        import tkinter.font as tkfont
        self.root, self.c, self.screen_w = root, canvas, screen_w
        f = "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"
        self.font = {"small": tkfont.Font(family=f, size=9), "body": tkfont.Font(family=f, size=10),
                     "text": tkfont.Font(family=f, size=12), "title": tkfont.Font(family=f, size=11, weight="bold"),
                     "funky": tkfont.Font(family=f, size=13, weight="bold")}
        self.msg = None
        self.t0 = time.time()
        self.funky_title = ""

    # ------------------------------------------------------------- layout per style
    def draw(self):
        """(width, height) after drawing the current message on the canvas."""
        c, m = self.c, self.msg
        c.delete("all")
        style = config.get("osd_style")
        if m["kind"] == "pick":
            return self._pick(c, m)
        if style == "advanced":
            return self._advanced(c, m)
        if style == "funky":
            return self._funky(c, m)
        return self._minimal(c, m)

    def _line(self, m):
        text = m["text"]
        if m["kind"] == "ok" and m["chips"]:
            text = " → ".join(m["chips"]) if len(m["chips"]) > 1 else text
        if m["kind"] == "error" and m["title"]:
            text = f"{m['title']}: “{text}”"
        return text if len(text) <= 80 else text[:78] + "…"

    def _minimal(self, c, m):
        text = self._line(m)
        if m["kind"] == "ok":
            text = "✓  " + text + (f"   ·  {m['footer']}" if m["footer"] and config.get("show_timing") else "")
        h, pad = 32, 14
        w = min(self.screen_w - 40, pad * 2 + 18 + self.font["body"].measure(text))
        _rounded(c, 0, 0, w, h, h / 2, fill=BG, outline=LINE)
        dot = ACCENT.get(m["kind"], ACCENT["info"])
        if m["kind"] == "listen":  # a breathing dot, sized by your voice
            lv = level_source() if level_source else 0
            r = 4 + 3 * max(lv, 0.5 + 0.5 * math.sin((time.time() - self.t0) * 5) if lv < 0.05 else lv)
        else:
            r = 4.5
        c.create_oval(pad + 5 - r, h / 2 - r, pad + 5 + r, h / 2 + r, fill=dot, outline="")
        c.create_text(pad + 18, h / 2, text=text, anchor="w", fill=INK, font=self.font["body"])
        return w, h

    def _advanced(self, c, m):
        kind, accent = m["kind"], ACCENT.get(m["kind"], ACCENT["info"])
        w, pad = 460, 18
        title = m["title"] or TITLE.get(kind, "")
        y = pad
        c.create_oval(pad, y + 2, pad + 12, y + 14, fill=accent, outline="")
        c.create_text(pad + 20, y + 8, text=title, anchor="w", fill=INK, font=self.font["title"])
        right = m["footer"]
        if kind == "listen":
            right = f"{time.time() - self.t0:.1f} s · Esc cancels"
        elif kind == "busy":
            right = "." * (1 + int((time.time() - self.t0) * 3) % 3)
        if right:
            c.create_text(w - pad, y + 8, text=right, anchor="e", fill=SOFT, font=self.font["small"])
        y += 28
        if kind == "listen":  # a live mic meter
            lv = level_source() if level_source else 0
            c.create_rectangle(pad, y + 4, w - pad, y + 12, fill=CHIP, outline="")
            c.create_rectangle(pad, y + 4, pad + (w - 2 * pad) * max(0.02, lv), y + 12, fill=accent, outline="")
            y += 24
            hint = m["text"] if m["text"] not in ("Listening…",) else "Talk now, let go when you're done"
            c.create_text(pad, y, text=hint, anchor="nw", fill=SOFT, font=self.font["body"])
            y += 22
        else:
            said = (kind == "ok" and m["chips"]) or m["title"] == "Didn't understand"  # your words, in quotes
            quoted = f"“{m['text']}”" if said else m["text"]
            t = c.create_text(pad, y, text=quoted, anchor="nw", fill=INK, font=self.font["text"], width=w - 2 * pad)
            y = c.bbox(t)[3] + 10
        if m["chips"]:  # one chip per command it ran
            x = pad
            for chip in m["chips"][:4]:
                label = chip if len(chip) <= 34 else chip[:32] + "…"
                cw = self.font["body"].measure(label) + 20
                if x + cw > w - pad and x > pad:
                    x, y = pad, y + 30
                _rounded(c, x, y, x + cw, y + 24, 12, fill=CHIP, outline=accent)
                c.create_text(x + cw / 2, y + 12, text=label, fill=INK, font=self.font["body"])
                x += cw + 8
            y += 32
        h = y + pad - 6
        bg = _rounded(c, 0, 0, w, h, 16, fill=BG, outline=LINE)
        c.tag_lower(bg)
        c.create_rectangle(1, 16, 4, h - 16, fill=accent, outline="")  # the colour strip on the left
        return w, h

    def _pick(self, c, m):
        """'Which one?': a short numbered list, the same in every style. chips: (name, folder) pairs."""
        pad, fb, fs = 16, self.font["body"], self.font["small"]

        def cut(text, font, room):
            while text and font.measure(text) > room:
                text = text[:-2] + "…" if len(text) > 2 else ""
            return text
        rows = list(m["chips"])[:5]
        w = min(self.screen_w - 40, max(340, pad * 2 + 40 + max(fb.measure(n) + fs.measure(d) + 24 for n, d in rows)), 560)
        y = pad
        c.create_oval(pad, y + 2, pad + 12, y + 14, fill=ACCENT["info"], outline="")
        c.create_text(pad + 20, y + 8, text=m["title"] or "Which one?", anchor="w", fill=INK, font=self.font["title"])
        y += 28
        for i, (name, where) in enumerate(rows, 1):
            _rounded(c, pad, y, w - pad, y + 30, 10, fill=CHIP, outline="")
            _rounded(c, pad + 6, y + 5, pad + 26, y + 25, 10, fill=ACCENT["info"], outline="")
            c.create_text(pad + 16, y + 15, text=str(i), fill=BG, font=self.font["title"])
            where = cut(where, fs, (w - 2 * pad) * 0.35)
            c.create_text(w - pad - 10, y + 15, text=where, anchor="e", fill=SOFT, font=fs)
            room = w - 2 * pad - 50 - fs.measure(where) - 16
            c.create_text(pad + 36, y + 15, text=cut(name, fb, room), anchor="w", fill=INK, font=fb)
            y += 36
        if m["footer"]:
            c.create_text(pad, y + 2, text=m["footer"], anchor="nw", fill=SOFT, font=fs)
            y += 20
        h = y + pad - 4
        bg = _rounded(c, 0, 0, w, h, 16, fill=BG, outline=LINE)
        c.tag_lower(bg)
        return w, h

    def _funky(self, c, m):
        kind = m["kind"]
        t = time.time() - self.t0
        if not self.funky_title:
            self.funky_title = random.choice(FUNKY.get(kind, FUNKY["info"]))
        text = self._line(m) if kind != "listen" else "talk to me…"
        w = max(320, min(self.screen_w - 40, self.font["text"].measure(text) + 60))
        h = 78 if kind != "listen" else 92
        # a moving rainbow, drawn as thin stripes inside the rounded shape
        stripes = 64  # dark enough that white text reads on every colour
        base = {"error": 0.02, "ok": 0.36}.get(kind, 0.72)
        for i in range(stripes):
            x0 = w * i / stripes
            c.create_rectangle(x0, 0, x0 + w / stripes + 1, h, outline="",
                               fill=_hue(base + 0.18 * math.sin(t * 1.6 + i / stripes * math.tau), 0.72, 0.58))
        _corners(c, w, h, 24)
        c.create_text(w / 2 + 1, 24, text=self.funky_title, fill="#0b0d12", font=self.font["funky"])
        c.create_text(w / 2, 22, text=self.funky_title, fill="white", font=self.font["funky"])
        if kind == "listen":  # bouncing bars that follow your voice
            lv = level_source() if level_source else 0
            n, bw = 9, 10
            x0 = w / 2 - n * (bw + 6) / 2
            for i in range(n):
                amp = 0.25 + 0.75 * lv
                bh = 8 + 34 * amp * (0.5 + 0.5 * math.sin(t * 9 + i * 0.9))
                x = x0 + i * (bw + 6)
                _rounded(c, x, 66 - bh / 2, x + bw, 66 + bh / 2, 5, fill="white", outline="")
        else:
            c.create_text(w / 2, 52, text=text, fill="white", font=self.font["text"], width=w - 40)
        return w, h

    def animated(self):
        style, kind = config.get("osd_style"), self.msg["kind"] if self.msg else ""
        return bool(self.msg) and ((style == "funky" and kind != "pick") or kind in ("listen", "busy"))


def _loop():
    import tkinter as tk
    root = tk.Tk()
    # Shown and hidden by its opacity, never by mapping it again: Windows hands focus to
    # a window that appears, and the pill must not take it from the app you're in.
    root.attributes("-alpha", 0.0)
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.configure(bg=KEY)
    if sys.platform == "win32":
        root.attributes("-transparentcolor", KEY)  # the corners outside the rounded shape
    canvas = tk.Canvas(root, bg=KEY, highlightthickness=0, bd=0, width=10, height=10)
    canvas.pack()
    root.update_idletasks()
    hwnd = None
    if sys.platform == "win32":
        user32 = ctypes.windll.user32
        hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
        style = user32.GetWindowLongW(hwnd, -20)
        # WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOPMOST
        user32.SetWindowLongW(hwnd, -20, style | 0x08000000 | 0x80 | 0x20 | 0x80000 | 0x8)
    pill = Pill(root, canvas, root.winfo_screenwidth())
    state = {"hide": None, "visible": False, "on_top": 0.0}

    def on_top():
        if hwnd:
            ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x1 | 0x2 | 0x10)  # topmost, no move/size/activate
        state["on_top"] = time.time()

    def off():
        root.attributes("-alpha", 0.0)
        state["visible"], pill.msg = False, None

    def render():
        w, h = pill.draw()
        canvas.config(width=w, height=h)
        root.geometry(f"{int(w)}x{int(h)}+{int((pill.screen_w - w) // 2)}+{TOP}")

    def poll():
        try:
            while True:
                item = _q.get_nowait()
                if callable(item):  # ui(fn): the tray panel
                    try:
                        item(root)
                    except Exception:
                        import logging
                        logging.getLogger("wva.ui").exception("ui call failed")
                    continue
                if state["hide"]:
                    root.after_cancel(state["hide"])
                    state["hide"] = None
                if item is None:
                    off()
                    continue
                if not pill.msg or pill.msg["kind"] != item["kind"]:
                    pill.t0, pill.funky_title = time.time(), ""
                pill.msg = item
                render()
                root.attributes("-alpha", 0.95 if config.get("osd_style") != "minimal" else 0.92)
                on_top()
                state["visible"] = True
                if item["seconds"]:
                    state["hide"] = root.after(int(item["seconds"] * 1000), off)
        except queue.Empty:
            pass
        if state["visible"] and time.time() - state["on_top"] > 0.5:
            on_top()  # a game that went topmost after us goes back under
        if state["visible"] and pill.animated():
            render()
            root.after(40, poll)  # ~25 frames a second, only while something moves
        else:
            root.after(60, poll)

    root.after(60, poll)
    root.mainloop()
