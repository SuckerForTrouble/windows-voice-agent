"""The pill at the top of the screen: "Listening…", what was heard and what it did,
answers and errors, in one of three styles (tray → Pill on screen, or Settings…):

  minimal   a slim pill: a dot and one short line (the default, the lightest)
  advanced  a card: title, what it heard, a chip per command, timing and model,
            a live mic meter while you talk
  funky     an animated colour gradient, bouncing level bars, playful titles
  island    liquid glass like Apple's (liquid.py): clear, what's behind it showing through,
            bent at the rim, lit along the edge; it springs open from a small pill to fit what
            it says and shrinks back before it goes. Where Windows can't make the glass window
            it's drawn as black glass instead.

Every style fades and slides in and out, and anything that moves is drawn at ~60 frames
a second, only while it's on screen. The mic level is smoothed (quick to rise, slow to
fall), so meters move like a real VU meter instead of flickering.

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

STYLES = {"minimal": "Minimal", "advanced": "Advanced", "funky": "Funky", "island": "Island"}
ACCENT = {"listen": "#e5484d", "ok": "#46a758", "error": "#f76b15", "info": "#8b95ff", "busy": "#a2a9b8"}
TITLE = {"listen": "Listening", "busy": "Working on it", "ok": "Done", "error": "Problem", "info": "Voice Agent"}
FUNKY = {"listen": ("✦ I'm all ears ✦",), "busy": ("Thinking…", "Hmm, one sec…"),
         "ok": ("Done! ✨", "On it! ⚡", "Boom ✨", "Easy ✓"), "error": ("Huh? ✗", "Say again? ✗"), "info": ("Psst ✦",)}
KEY = "#010203"          # painted transparent: the rounded corners
BADGE = {"Discord": "#5865f2"}  # where a command came from, when it wasn't you
BG, INK, SOFT, LINE, CHIP = "#1b1e27", "#eef0f5", "#9aa2b3", "#2c303b", "#262a39"
# The island's liquid glass, top to bottom: a bright rim (light catching the curved edge, strongest
# on top), a body that is lighter where the light falls and dark below, a reflective band in its
# upper half, and light bouncing back along the bottom edge. The window itself is see-through.
GLASS = "#0b0c10"                                   # what the words fade in from
RIM_TOP, RIM_BOTTOM = "#d9defa", "#3a3e52"
BODY = ("#454a5c", "#22242e", "#101117", "#0b0c10")  # top, upper middle, lower middle, bottom
CAUSTIC = "#2f3343"
ALPHA = {"minimal": 0.93, "advanced": 0.96, "funky": 0.96, "island": 0.84}  # the island lets the screen through
TOP = 18
FRAME = 16              # ms between frames while something moves (~60 a second)
SLIDE = 12              # px it slides down while fading in
COMPACT = (118, 36)     # the island's size before it opens and after it closes
_now = time.monotonic   # the clock (the previews step it by hand)
_q = queue.Queue()
_thread = None
level_source = None      # the app sets this: () -> 0..1, the mic level while listening


def _start():
    global _thread
    if _thread is None:
        _thread = threading.Thread(target=_loop, daemon=True, name="osd")
        _thread.start()


def show(text, kind="info", seconds=3.0, title=None, chips=None, footer=None, source=None):
    """kind: listen | busy | ok | error | info. seconds=0 keeps it up until the next call.
    title, chips (one per command) and footer are used by the richer styles. source:
    "Discord" when the command was heard in Discord's sound (a badge in every style)."""
    if not config.get("osd"):
        return
    _start()
    _q.put({"text": text, "kind": kind, "seconds": seconds, "title": title, "chips": chips or [], "footer": footer or "",
            "source": source})


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


def _mix(a, b, t):
    """Colour a..b at t (0..1): text fading in on the island."""
    t = max(0.0, min(1.0, t))
    x, y = int(a[1:], 16), int(b[1:], 16)
    return "#" + "".join(f"{int(((x >> k) & 255) * (1 - t) + ((y >> k) & 255) * t):02x}" for k in (16, 8, 0))


def _capsule_rows(c, x0, y0, x1, y1, colour_at, step=1.0):
    """A capsule filled row by row: colour_at(t) for t = 0 (top) .. 1 (bottom). Rectangles, not
    lines, so it stays solid when the drawing is scaled up for 125 % / 150 % screens."""
    h = y1 - y0
    r = h / 2
    y = 0.0
    while y < h:
        dy = abs(y + step / 2 - r)
        inset = r - math.sqrt(max(0.0, r * r - dy * dy))
        c.create_rectangle(x0 + inset, y0 + y, x1 - inset, y0 + y + step + 0.6, fill=colour_at(y / h), outline="")
        y += step


def _glass(c, x0, y0, x1, y1, tint):
    """The island's liquid glass (see GLASS above); tint: the state's colour, glowing softly behind the icon."""
    def rim(t):
        return _mix(RIM_TOP, RIM_BOTTOM, min(1.0, t * 1.6))

    def body(t):
        if t < 0.08:
            return _mix(BODY[0], BODY[1], t / 0.08)
        if t < 0.5:
            return _mix(BODY[1], BODY[2], (t - 0.08) / 0.42)
        if t > 0.88:
            return _mix(BODY[3], CAUSTIC, (t - 0.88) / 0.12)  # light bouncing along the bottom
        return _mix(BODY[2], BODY[3], (t - 0.5) / 0.38)
    _capsule_rows(c, x0, y0, x1, y1, rim)
    _capsule_rows(c, x0 + 1.4, y0 + 1.4, x1 - 1.4, y1 - 1.4, body)
    h = y1 - y0
    # the reflective band in the upper half, and a glint where the light hits hardest
    _rounded(c, x0 + h * 0.45, y0 + 3, x1 - h * 0.45, y0 + 3 + h * 0.16, h * 0.08, fill=_mix(BODY[1], RIM_TOP, 0.16))
    c.create_oval(x0 + h * 0.32, y0 + 3.2, x0 + h * 0.32 + h * 0.5, y0 + 3.2 + h * 0.12, fill=_mix(BODY[1], RIM_TOP, 0.45),
                  outline="")
    if tint:
        cx, cy = x0 + h * 0.55, y0 + h / 2
        for k, a in ((h * 0.46, 0.10), (h * 0.36, 0.16), (h * 0.27, 0.22)):
            c.create_oval(cx - k, cy - k * 0.8, cx + k, cy + k * 0.8, fill=_mix(BODY[2], tint, a), outline="")


def _ease(p):
    """0..1 -> 0..1, quick then gentle, with a small overshoot (a pop)."""
    p = max(0.0, min(1.0, p))
    return 1 + 2.2 * (p - 1) ** 3 + 1.2 * (p - 1) ** 2


def _icon(c, kind, x, y, r, t, lv, color, bg):
    """The state at a glance, animated: listening = level bars, working = a spinner,
    done = a check that pops in, problem = an '!' that pops in, else a dot."""
    if kind == "listen":
        for i in range(4):
            amp = 0.3 + 0.7 * max(lv, 0.18 + 0.12 * math.sin(t * 4 + i))
            bh = r * 1.9 * amp * (0.55 + 0.45 * abs(math.sin(t * 7.5 + i * 1.3)))
            bx = x - r + i * (r * 2 / 3.4) + 1
            _rounded(c, bx, y - bh / 2, bx + max(2.5, r * 0.42), y + bh / 2, 2, fill=color)
        return
    if kind == "busy":
        a = (t * 400) % 360
        c.create_oval(x - r, y - r, x + r, y + r, outline=_mix(color, bg, 0.7), width=2)
        c.create_arc(x - r, y - r, x + r, y + r, start=-a, extent=100, style="arc", outline=color, width=2)
        return
    k = r * _ease(t / 0.32) if kind in ("ok", "error") else r
    c.create_oval(x - k, y - k, x + k, y + k, fill=color, outline="")
    if kind == "ok" and k > r * 0.4:
        c.create_line(x - k * 0.45, y + k * 0.02, x - k * 0.1, y + k * 0.36, x + k * 0.48, y - k * 0.34,
                      fill=bg, width=2, capstyle="round", joinstyle="round")
    elif kind == "error" and k > r * 0.4:
        c.create_line(x, y - k * 0.5, x, y + k * 0.12, fill=bg, width=2, capstyle="round")
        c.create_oval(x - 1.3, y + k * 0.38, x + 1.3, y + k * 0.62, fill=bg, outline="")


class _Font:
    """A Tk font measured in layout units (see Pill: layouts are drawn at 100% and scaled)."""

    def __init__(self, font, scale):
        self.f, self.s = font, scale

    def measure(self, text):
        return self.f.measure(text) / self.s

    def configure(self, **kw):
        self.f.configure(**kw)

    def __str__(self):
        return str(self.f)


def fit(text, font, room):
    """text cut with '…' so it's no wider than room (layout units)."""
    if font.measure(text) <= room:
        return text
    while text and font.measure(text + "…") > room:
        text = text[:-1]
    return text.rstrip() + "…"


class Pill:
    """Each style lays itself out at 100% size; draw() then scales the drawing by the display's
    scaling (125 %, 150 %…) and Tk draws the fonts at that size by itself. So nothing is cramped
    or spills over at any scaling, and widths are capped to the screen in the same units: a
    1280x720 screen at 150 % is only 853 wide, and long text is cut to fit."""

    def __init__(self, root, canvas, screen_w):
        import tkinter.font as tkfont
        self.root, self.c, self.screen_w = root, canvas, screen_w
        try:
            self.S = max(1.0, float(root.tk.call("tk", "scaling")) * 72 / 96)  # how big Tk draws a point
        except Exception:
            self.S = 1.0
        self.room = screen_w / self.S - 40  # the widest it may be, in layout units
        f = "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"
        S = self.S
        self.font = {"small": _Font(tkfont.Font(family=f, size=9), S), "body": _Font(tkfont.Font(family=f, size=10), S),
                     "text": _Font(tkfont.Font(family=f, size=12), S),
                     "title": _Font(tkfont.Font(family=f, size=11, weight="bold"), S),
                     "funky": _Font(tkfont.Font(family=f, size=13, weight="bold"), S),
                     "badge": _Font(tkfont.Font(family=f, size=8, weight="bold"), S),
                     "island": _Font(tkfont.Font(family=f, size=11, weight="bold"), S),
                     "island_small": _Font(tkfont.Font(family=f, size=9), S)}
        self.msg = None
        self.t0 = _now()        # when this kind of message started (animations count from here)
        self.shown = _now()     # when this message came (the advanced card's countdown)
        self.funky_title = ""
        self.lv = 0.0           # the smoothed mic level
        self.closing = False    # fading out: the island shrinks back as it goes
        self.size = list(COMPACT)   # the island's size now, and how fast it changes (a spring)
        self.vel = [0.0, 0.0]
        self.target = list(COMPACT)
        self.stepped = _now()

    def level(self):
        """The mic level, smoothed: up at once, down slowly."""
        raw = level_source() if level_source else 0.0
        self.lv = raw if raw > self.lv else self.lv * 0.86 + raw * 0.14
        return self.lv

    def settled(self):
        return all(abs(a - b) < 0.5 for a, b in zip(self.size, self.target)) and max(map(abs, self.vel)) < 0.5

    def _spring(self):
        """Move the island's size toward its target, in 1/120 s steps (smooth at any frame rate)."""
        now = _now()
        dt, self.stepped = min(0.1, now - self.stepped), now
        for _ in range(max(1, int(dt * 120))):
            for i in (0, 1):
                self.vel[i] += (self.target[i] - self.size[i]) * 0.055 - self.vel[i] * 0.22
                self.size[i] += self.vel[i]

    # ------------------------------------------------------------- layout per style
    def draw(self):
        """(width, height) in screen pixels after drawing the current message on the canvas."""
        c, m = self.c, self.msg
        c.delete("all")
        style = config.get("osd_style")
        if m["kind"] == "pick":
            w, h = self._pick(c, m)
        elif style == "advanced":
            w, h = self._advanced(c, m)
        elif style == "funky":
            w, h = self._funky(c, m)
        elif style == "island":
            w, h = self._island(c, m)
        else:
            w, h = self._minimal(c, m)
        if self.S != 1.0:
            c.scale("all", 0, 0, self.S, self.S)
        return w * self.S, h * self.S

    def _tall(self, item):
        """A text item's height in layout units (Tk reports it in screen pixels)."""
        b = self.c.bbox(item)
        return (b[3] - b[1]) / self.S if b else 0

    def _badge(self, c, x, y, m, anchor="w"):
        """'FROM DISCORD' in a coloured tag at (x, y); returns its width (0 without a source)."""
        src = m.get("source")
        if not src:
            return 0
        label = f"FROM {src.upper()}"
        f = self.font["badge"]
        w = f.measure(label) + 14
        x0 = x - w if anchor == "e" else x
        _rounded(c, x0, y - 10, x0 + w, y + 10, 10, fill=BADGE.get(src, ACCENT["info"]))
        c.create_text(x0 + w / 2, y, text=label, fill="white", font=f)
        return w

    def _line(self, m):
        text = m["text"]
        if m["kind"] == "ok" and m["chips"]:
            text = " → ".join(m["chips"]) if len(m["chips"]) > 1 else text
        if m["kind"] == "ok" and m["title"]:  # "Took it as “open spotify”" (a guess): say what ran
            text = m["title"]
        if m["kind"] == "error" and m["title"]:
            text = f"{m['title']}: “{text}”"
        return text if len(text) <= 80 else text[:78] + "…"

    def _minimal(self, c, m):
        text = self._line(m)
        if m["kind"] == "ok":
            text = text + (f"   ·  {m['footer']}" if m["footer"] and config.get("show_timing") else "")
        h, pad = 34, 13
        bw = self.font["badge"].measure(f"FROM {m['source'].upper()}") + 22 if m.get("source") else 0
        text = fit(text, self.font["body"], self.room - pad * 2 - 26 - bw)
        w = min(self.room, pad * 2 + 26 + bw + self.font["body"].measure(text))
        _rounded(c, 0, 0, w, h, h / 2, fill=BG, outline=LINE)
        c.create_line(h / 2, 1, w - h / 2, 1, fill="#343947")  # a light top edge
        _icon(c, m["kind"], pad + 8, h / 2, 7.5, _now() - self.t0, self.level(), ACCENT.get(m["kind"], ACCENT["info"]), BG)
        bw = self._badge(c, pad + 24, h / 2, m)
        c.create_text(pad + 25 + (bw + 8 if bw else 0), h / 2, text=text, anchor="w", fill=INK, font=self.font["body"])
        return w, h

    def _advanced(self, c, m):
        kind, accent = m["kind"], ACCENT.get(m["kind"], ACCENT["info"])
        w, pad = min(460, self.room), 18
        title = m["title"] or TITLE.get(kind, "")
        y = pad
        _icon(c, kind, pad + 7, y + 8, 7, _now() - self.t0, self.level(), accent, BG)
        title = fit(title, self.font["title"], w - 2 * pad - 150)
        c.create_text(pad + 22, y + 8, text=title, anchor="w", fill=INK, font=self.font["title"])
        self._badge(c, pad + 22 + self.font["title"].measure(title) + 10, y + 8, m)
        right = m["footer"]
        if kind == "listen":
            right = f"{_now() - self.t0:.1f} s · Esc cancels"
        elif kind == "busy":
            right = "." * (1 + int((_now() - self.t0) * 3) % 3)
        if right:
            c.create_text(w - pad, y + 8, text=right, anchor="e", fill=SOFT, font=self.font["small"])
        y += 28
        if kind == "listen":  # a live mic meter: 28 segments, lit up to your voice's level
            lv, n = self.lv, 28
            seg = (w - 2 * pad) / n
            for i in range(n):
                on = i < max(1, round(lv * n))
                hot = "#f5d90a" if i > n * 0.82 else accent
                _rounded(c, pad + i * seg + 1, y + 3, pad + (i + 1) * seg - 2, y + 13, 2, fill=hot if on else CHIP)
            y += 24
            hint = m["text"] if m["text"] not in ("Listening…",) else "Talk now, let go when you're done"
            c.create_text(pad, y, text=hint, anchor="nw", fill=SOFT, font=self.font["body"])
            y += 22
        elif m["text"].rstrip("…. ") != title.rstrip("…. "):  # (not "Working on it" twice)
            said = (kind == "ok" and m["chips"]) or m["title"] == "Didn't understand"  # your words, in quotes
            quoted = f"“{m['text']}”" if said else m["text"]
            t = c.create_text(pad, y, text=quoted, anchor="nw", fill=INK, font=self.font["text"],
                              width=(w - 2 * pad) * self.S)
            y += self._tall(t) + 10
        if m["chips"]:  # one chip per command it ran
            x = pad
            for chip in m["chips"][:4]:
                label = fit(chip, self.font["body"], min(240, w - 2 * pad - 20))
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
        if m["seconds"] and kind not in ("listen", "busy"):  # how long until it goes
            left = max(0.0, 1 - (_now() - self.shown) / m["seconds"])
            c.create_line(16, h - 2, 16 + (w - 32) * left, h - 2, fill=_mix(BG, accent, 0.7), width=2)
        return w, h

    def _pick(self, c, m):
        """'Which one?': a short numbered list, the same in every style. chips: (name, folder) pairs."""
        pad, fb, fs = 16, self.font["body"], self.font["small"]

        def cut(text, font, room):
            while text and font.measure(text) > room:
                text = text[:-2] + "…" if len(text) > 2 else ""
            return text
        rows = list(m["chips"])[:5]
        w = min(self.room, max(340, pad * 2 + 40 + max(fb.measure(n) + fs.measure(d) + 24 for n, d in rows)), 560)
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
        t = _now() - self.t0
        if not self.funky_title:
            self.funky_title = random.choice(FUNKY.get(kind, FUNKY["info"]))
        text = self._line(m) if kind != "listen" else "talk to me…"
        text = fit(text, self.font["text"], 2 * (self.room - 60))  # two lines at most
        w = min(self.room, max(320, self.font["text"].measure(text) + 60))
        if m.get("source"):  # room for the badge on the left without touching the centred title
            bw = self.font["badge"].measure(f"FROM {m['source'].upper()}") + 14
            w = max(w, self.font["funky"].measure(self.funky_title) + 2 * (bw + 30))
        h = 78 if kind != "listen" else 92
        self.level()
        # a moving rainbow, drawn as thin stripes inside the rounded shape
        stripes = 64  # dark enough that white text reads on every colour
        base = {"error": 0.02, "ok": 0.36}.get(kind, 0.72)
        for i in range(stripes):
            x0 = w * i / stripes
            c.create_rectangle(x0, 0, x0 + w / stripes + 1, h, outline="",
                               fill=_hue(base + 0.18 * math.sin(t * 1.6 + i / stripes * math.tau), 0.72, 0.58))
        _corners(c, w, h, 24)
        self._badge(c, 18, 16, m)
        c.create_text(w / 2 + 1, 24, text=self.funky_title, fill="#0b0d12", font=self.font["funky"])
        c.create_text(w / 2, 22, text=self.funky_title, fill="white", font=self.font["funky"])
        if kind == "listen":  # bouncing bars that follow your voice
            lv = self.lv
            n, bw = 9, 10
            x0 = w / 2 - n * (bw + 6) / 2
            for i in range(n):
                amp = 0.25 + 0.75 * lv
                bh = 8 + 34 * amp * (0.5 + 0.5 * math.sin(t * 9 + i * 0.9))
                x = x0 + i * (bw + 6)
                _rounded(c, x, 66 - bh / 2, x + bw, 66 + bh / 2, 5, fill="white", outline="")
        else:
            c.create_text(w / 2, 52, text=fit(text, self.font["text"], w - 40), fill="white", font=self.font["text"])
        return w, h

    def _island(self, c, m):
        """A black glass capsule. Its size springs from where it was (small when it first
        appears) to fit the message; the words fade in once it has opened. The window is
        as big as the larger of the two; the rest of it is transparent."""
        kind, t = m["kind"], _now() - self.t0
        accent = ACCENT.get(kind, ACCENT["info"])
        fb, fs = self.font["island"], self.font["island_small"]
        text = self._line(m) if not (kind == "listen" and m["text"] == "Listening…") else "Listening"
        right = ""
        if kind == "listen":
            right = f"{t:.0f}s" if t >= 1 else ""
        elif kind == "ok" and m["footer"] and config.get("show_timing"):
            right = m["footer"].split(" · ")[0]
        bw = self.font["badge"].measure(f"FROM {m['source'].upper()}") + 22 if m.get("source") else 0
        room = self.room
        text = fit(text, fb, room - 110 - bw - (fs.measure(right) + 14 if right else 0) - (40 if kind == "listen" else 0))
        tw = 22 + 28 + bw + fb.measure(text) + 18 + (fs.measure(right) + 14 if right else 0) + (40 if kind == "listen" else 0)
        self.target = list(COMPACT) if self.closing else [min(room, max(200, tw)), 40]
        self._spring()
        cw, ch = max(COMPACT[1], self.size[0]), max(24, self.size[1])
        w, h = max(cw, self.target[0]) + 4, max(ch, self.target[1]) + 4
        x0, y0 = (w - cw) / 2, (h - ch) / 2
        x1, y1 = x0 + cw, y0 + ch
        _glass(c, x0, y0, x1, y1, ACCENT.get(kind, ACCENT["info"]) if not self.closing else None)
        if self.closing:
            return w, h
        # the words appear as it opens: faded from the glass up to full colour
        open_ = (cw - COMPACT[0]) / max(1.0, self.target[0] - COMPACT[0]) if self.target[0] > COMPACT[0] else 1.0
        fade = max(0.0, min(1.0, (open_ - 0.55) / 0.4))
        _icon(c, kind, x0 + 22, y0 + ch / 2, 8, t, self.level(), _mix(GLASS, accent, max(fade, 0.6)), GLASS)
        x = x0 + 40
        if bw and fade > 0:
            self._badge(c, x, y0 + ch / 2, m)
            x += bw
        if fade > 0:
            c.create_text(x, y0 + ch / 2, text=text, anchor="w", fill=_mix(GLASS, INK, fade), font=fb)
        if right and fade > 0:
            c.create_text(x1 - 18 - (40 if kind == "listen" else 0), y0 + ch / 2, text=right, anchor="e",
                          fill=_mix(GLASS, SOFT, fade), font=fs)
        if kind == "listen":  # a little waveform on the right, like the island's audio view
            for i in range(5):
                amp = 0.25 + 0.75 * max(self.lv, 0.12)
                bh = 4 + 16 * amp * (0.5 + 0.5 * math.sin(t * 8 + i * 1.1))
                bx = x1 - 50 + i * 7
                _rounded(c, bx, y0 + ch / 2 - bh / 2, bx + 4, y0 + ch / 2 + bh / 2, 2, fill=_mix(GLASS, accent, fade))
        return w, h

    def animated(self):
        if not self.msg:
            return False
        style, kind = config.get("osd_style"), self.msg["kind"]
        if kind == "pick":
            return False
        t = _now() - self.t0
        return (style == "funky" or kind in ("listen", "busy") or (kind in ("ok", "error") and t < 0.4)
                or (style == "island" and (not self.settled() or self.closing))
                or (style == "advanced" and bool(self.msg["seconds"])))


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
    state = {"hide": None, "visible": False, "on_top": 0.0, "alpha": 0.0, "want": 0.0, "geo": None,
             "back": None, "back_at": 0.0, "glass": None, "glass_failed": False}

    def glass():
        """The liquid-glass window for the Island style (Windows), made the first time it's needed;
        None elsewhere, or if Windows wouldn't make it (then the island is drawn in black glass)."""
        if config.get("osd_style") != "island" or sys.platform != "win32" or state["glass_failed"]:
            return None
        if state["glass"] is None:
            try:
                from . import liquid
                state["glass"] = liquid.Window()
            except Exception:
                import logging
                logging.getLogger("wva.osd").exception("liquid glass unavailable, using the black island")
                state["glass_failed"] = True
                return None
        return state["glass"]

    def on_top():
        if hwnd:
            ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x1 | 0x2 | 0x10)  # topmost, no move/size/activate
        if state["glass"] is not None:
            state["glass"].on_top()
        state["on_top"] = time.time()

    def off():
        """Fade out (the island shrinks as it goes); the message is dropped once it's gone."""
        state["want"] = 0.0
        pill.closing = True

    def gone():
        root.attributes("-alpha", 0.0)
        if state["glass"] is not None:
            state["glass"].hide()
        state.update(visible=False, alpha=0.0, geo=None, back=None, sig=None)
        pill.msg, pill.closing = None, False
        pill.size, pill.vel = list(COMPACT), [0.0, 0.0]

    def render_glass(g):
        """One frame of liquid glass: what's behind the pill (read every 100 ms), bent, frosted
        and lit by liquid.render, put on screen with per-pixel alpha."""
        from . import liquid
        m, S = pill.msg, pill.S
        width, text, right = liquid.layout(m, pill.room, config.get("show_timing"))
        pill.target = list(liquid.COMPACT) if pill.closing else [width, liquid.H]
        pill._spring()
        # (the spring overshoots a little: kept inside the strip that's read behind it)
        cw = min(pill.room, max(liquid.COMPACT[1], pill.size[0]))
        ch = min(liquid.H + 3, max(24.0, pill.size[1]))
        M = int(round(liquid.MARGIN * S))
        W, Hh = int(round(cw * S)) + 2 * M, int(round(ch * S)) + 2 * M
        a = min(1.0, state["alpha"])
        y = int(TOP - M + (liquid.H * S - ch * S) / 2 - SLIDE * S * (1 - a) ** 2)
        x = int((pill.screen_w - W) // 2)
        # the strip behind it, as wide as the pill can get, read again every 100 ms
        sw = int(min(pill.screen_w, pill.room * S + 2 * M))
        sx = int((pill.screen_w - sw) // 2)
        sh = int((liquid.H + 6) * S) + 2 * M + int(SLIDE * S) + 4
        sy = int(TOP - M - SLIDE * S)
        if (state["back"] is None or time.time() - state["back_at"] > 0.1) and g.can_read_behind():
            state["back"], state["back_at"] = g.backdrop(sx, sy, sw, sh), time.time()
        back = state["back"].crop((x - sx, y - sy, x - sx + W, y - sy + Hh))
        open_ = (cw - liquid.COMPACT[0]) / max(1.0, pill.target[0] - liquid.COMPACT[0]) if pill.target[0] > liquid.COMPACT[0] else 1.0
        fade = 0.0 if pill.closing else max(0.0, min(1.0, (open_ - 0.55) / 0.4))
        # nothing moved and the screen behind didn't change: the frame on screen is still right
        sig = (hash(back.tobytes()), round(cw), round(ch), round(fade, 2), int(255 * a), x, y, id(m))
        if sig == state.get("sig") and not pill.animated():
            return
        state["sig"] = sig
        img = liquid.render(back, cw * S, ch * S, m, t=_now() - pill.t0, lv=pill.level(), fade=fade, scale=S,
                            show_timing=config.get("show_timing"), text=text, right=right)
        g.show(img, x, y, int(255 * a))

    def render():
        g = glass()
        if g is not None:
            try:
                return render_glass(g)
            except Exception:  # Windows wouldn't show the glass: the black island from here on
                import logging
                logging.getLogger("wva.osd").exception("liquid glass failed, using the black island")
                state["glass_failed"] = True
                try:
                    g.hide()
                except Exception:
                    pass
                state["alpha"], state["want"] = 0.0, ALPHA["island"]
                return render()
        if state["glass"] is not None and state["glass"].shown:
            state["glass"].hide()  # switched away from the island
        w, h = pill.draw()
        a = state["alpha"] / max(0.01, ALPHA.get(config.get("osd_style"), 0.95))
        y = TOP - SLIDE * (1 - min(1.0, a)) ** 2  # slides down into place as it fades in
        geo = f"{int(w)}x{int(h)}+{int((pill.screen_w - w) // 2)}+{int(y)}"
        if geo != state["geo"]:
            canvas.config(width=w, height=h)
            root.geometry(geo)
            state["geo"] = geo

    def fading():
        return abs(state["alpha"] - state["want"]) > 0.005

    def step_alpha():
        """Ease the opacity toward what's wanted: ~120 ms in, ~180 ms out."""
        k = 0.3 if state["want"] > state["alpha"] else 0.2
        state["alpha"] += (state["want"] - state["alpha"]) * k
        if not fading():
            state["alpha"] = state["want"]
        if glass() is None:  # (the glass window fades by itself)
            root.attributes("-alpha", max(0.0, state["alpha"]))

    def poll():
        """Messages in, then the next frame. Whatever goes wrong in one frame is logged and the
        loop carries on: the pill and the tray panel (which runs here too) never stop for it."""
        delay = 60
        try:
            delay = step()
        except Exception:
            import logging
            logging.getLogger("wva.osd").exception("pill frame failed")
        root.after(delay, poll)

    def step():
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
                    pill.t0, pill.funky_title = _now(), ""
                pill.msg, pill.closing, pill.shown = item, False, _now()
                pill.stepped = _now()
                state["want"] = 1.0 if glass() is not None else ALPHA.get(config.get("osd_style"), 0.95)
                if not state["visible"]:
                    on_top()
                state["visible"] = True
                if item["seconds"]:  # (set before drawing: a frame that fails still goes away in time)
                    state["hide"] = root.after(int(item["seconds"] * 1000), off)
                render()
        except queue.Empty:
            pass
        if not state["visible"]:
            return 60
        if time.time() - state["on_top"] > 0.5:
            on_top()  # a game that went topmost after us goes back under
        live = glass() is not None  # the glass follows what's behind it, so it's redrawn ~10 times a second anyway
        moving = fading() or pill.animated()
        if fading():
            step_alpha()
        if state["want"] == 0.0 and not fading() and (config.get("osd_style") != "island" or pill.settled()):
            gone()
        elif moving or live:
            render()
        return (33 if live else FRAME) if moving else (100 if live else 60)

    root.after(60, poll)
    root.mainloop()
