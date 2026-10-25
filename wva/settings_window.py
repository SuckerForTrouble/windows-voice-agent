"""The welcome window (first start, before the speech model downloads) and, later, the
Settings window (tray → Settings…). One page, Windows 11-style: switches, cards you
click, a few plain words each. Runs as its own process (dialogs.ask("settings", …))
and returns the settings chosen; the app applies them."""
import ctypes
import json
import sys

from . import hotkey, listen
from .stt import MODELS, PARAKEET

BG, CARD, CARD_HI, INK, SOFT, LINE, ACCENT, WARN_BG = (
    "#16181f", "#20232d", "#2a2e3b", "#eef0f5", "#9aa2b3", "#2e3240", "#8b95ff", "#3a2a1c")
FONT = "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"

MODEL_CARDS = [  # id, title, line under it
    (PARAKEET, "Parakeet", "Fastest: about a tenth of a second. English."),
    ("large-v3-turbo-q5_0", "Best", "Most accurate, and Hindi typing."),
    ("small.en-q5_1", "Balanced", "Lighter, for weaker GPUs."),
    ("base.en-q5_1", "Fast", "Smallest download, least accurate."),
]
PILLS = [("off", "Off"), ("minimal", "Minimal"), ("advanced", "Advanced"), ("funky", "Funky")]
MUSIC = [("spotify", "Spotify"), ("youtube_music", "YouTube Music"), ("youtube", "YouTube")]
MOVIES = [("stremio", "Stremio"), ("netflix", "Netflix"), ("prime", "Prime Video")]
BROWSERS = [("", "Windows default"), ("chrome", "Chrome"), ("edge", "Edge"), ("firefox", "Firefox"), ("brave", "Brave")]
EXTRAS = [("voice_replies", "Spoken answers", "Hear the time, weather… as well as seeing them"),
          ("sounds", "Beeps", "A beep when it starts and stops listening"),
          ("start_with_windows", "Start with Windows", "Ready as soon as you log in"),
          ("unload_in_games", "Free the GPU in games", "The model steps out while a game runs (not with always listening)"),
          ("auto_update", "Update by itself", "New versions install quietly"),
          ("hindi", "Type in Hindi", "The typing key writes Hindi (needs the Best model)")]


class Window:
    def __init__(self, current, first_run):
        import tkinter as tk
        self.tk, self.cur, self.first = tk, dict(current), first_run
        self.v = dict(current)
        self.v["hindi"] = current.get("dictate_language") == "hi"
        self.v["pill"] = current.get("osd_style", "minimal") if current.get("osd", True) else "off"
        self.result = None
        self.capturing = None
        root = self.root = tk.Tk()
        root.title("Windows Voice Agent" + ("" if first_run else ": Settings"))
        root.configure(bg=BG)
        root.geometry("760x720")
        root.minsize(620, 480)
        self._modern()
        self.f = {"h1": (FONT, 20, "bold"), "h2": (FONT, 13, "bold"), "body": (FONT, 10), "small": (FONT, 9),
                  "card": (FONT, 11, "bold"), "key": (FONT, 12, "bold")}
        # a scrolling page
        outer = tk.Frame(root, bg=BG)
        outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        bar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.page = tk.Frame(canvas, bg=BG, padx=28, pady=22)
        win = canvas.create_window(0, 0, anchor="nw", window=self.page)
        self.page.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        root.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
        root.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-3, "units"))
        root.bind_all("<Button-5>", lambda e: canvas.yview_scroll(3, "units"))
        self._build()
        self._footer()
        root.bind("<KeyPress>", self._key)

    def _modern(self):
        try:
            from . import win
            win.dpi_aware()
            self.root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            win.modern_window(hwnd, dark=True)
        except Exception:
            pass

    # ------------------------------------------------------------- small widgets
    def _h2(self, text, sub=None):
        tk = self.tk
        tk.Label(self.page, text=text, bg=BG, fg=INK, font=self.f["h2"], anchor="w").pack(fill="x", pady=(18, 2))
        if sub:
            tk.Label(self.page, text=sub, bg=BG, fg=SOFT, font=self.f["body"], anchor="w", justify="left",
                     wraplength=660).pack(fill="x", pady=(0, 8))

    def _switch(self, parent, key, on_change=None):
        """A Windows 11 switch: a pill track with a sliding knob."""
        tk = self.tk
        c = tk.Canvas(parent, width=46, height=24, bg=parent["bg"], highlightthickness=0, cursor="hand2")

        def draw():
            c.delete("all")
            on = bool(self.v.get(key))
            fill = ACCENT if on else "#3a3f4f"
            c.create_oval(1, 1, 23, 23, fill=fill, outline="")
            c.create_oval(23, 1, 45, 23, fill=fill, outline="")
            c.create_rectangle(12, 1, 34, 23, fill=fill, outline="")
            x = 34 if on else 12
            c.create_oval(x - 8, 4, x + 8, 20, fill="white", outline="")

        def flip(_=None):
            self.v[key] = not self.v.get(key)
            draw()
            if on_change:
                on_change()
        c.bind("<Button-1>", flip)
        draw()
        return c

    def _row(self, title, sub, key, on_change=None):
        tk = self.tk
        row = tk.Frame(self.page, bg=CARD, padx=16, pady=10, highlightthickness=1, highlightbackground=LINE)
        row.pack(fill="x", pady=3)
        text = tk.Frame(row, bg=CARD)
        text.pack(side="left", fill="x", expand=True)
        tk.Label(text, text=title, bg=CARD, fg=INK, font=self.f["card"], anchor="w").pack(fill="x")
        if sub:
            tk.Label(text, text=sub, bg=CARD, fg=SOFT, font=self.f["small"], anchor="w", justify="left",
                     wraplength=520).pack(fill="x")
        self._switch(row, key, on_change).pack(side="right")
        return row

    def _cards(self, options, key, columns=2):
        """Click-to-pick cards: (value, title, line) each."""
        tk = self.tk
        grid = tk.Frame(self.page, bg=BG)
        grid.pack(fill="x")
        cards = []

        def paint():
            for value, frame, labels in cards:
                sel = self.v.get(key) == value
                frame.configure(bg=CARD_HI if sel else CARD, highlightbackground=ACCENT if sel else LINE,
                                highlightthickness=2 if sel else 1)
                for lab in labels:
                    lab.configure(bg=CARD_HI if sel else CARD)

        for i, (value, title, line) in enumerate(options):
            frame = tk.Frame(grid, bg=CARD, padx=14, pady=10, cursor="hand2")
            frame.grid(row=i // columns, column=i % columns, sticky="nsew", padx=4, pady=4)
            grid.grid_columnconfigure(i % columns, weight=1)
            labels = [tk.Label(frame, text=title, bg=CARD, fg=INK, font=self.f["card"], anchor="w")]
            if line:
                labels.append(tk.Label(frame, text=line, bg=CARD, fg=SOFT, font=self.f["small"], anchor="w",
                                       justify="left", wraplength=280))
            for lab in labels:
                lab.pack(fill="x")
            for w in [frame] + labels:
                w.bind("<Button-1>", lambda e, val=value: (self.v.__setitem__(key, val), paint()))
            cards.append((value, frame, labels))
        paint()

    def _segments(self, label, options, key):
        tk = self.tk
        row = tk.Frame(self.page, bg=BG)
        row.pack(fill="x", pady=4)
        tk.Label(row, text=label, bg=BG, fg=INK, font=self.f["body"], width=16, anchor="w").pack(side="left")
        btns = []

        def paint():
            for value, b in btns:
                sel = self.v.get(key) == value
                b.configure(bg=ACCENT if sel else CARD, fg="#10121a" if sel else INK)

        for value, text in options:
            b = tk.Label(row, text=text, bg=CARD, fg=INK, font=self.f["body"], padx=12, pady=6, cursor="hand2")
            b.pack(side="left", padx=2)
            b.bind("<Button-1>", lambda e, val=value: (self.v.__setitem__(key, val), paint()))
            btns.append((value, b))
        paint()

    # ------------------------------------------------------------- the page
    def _build(self):
        tk = self.tk
        title = "Welcome! Let's set it up" if self.first else "Settings"
        tk.Label(self.page, text=title, bg=BG, fg=INK, font=self.f["h1"], anchor="w").pack(fill="x")
        tk.Label(self.page, text="Hold a key, say what you want, let go. Everything here can be changed later "
                                 "(tray icon → Settings).", bg=BG, fg=SOFT, font=self.f["body"], anchor="w",
                 justify="left", wraplength=660).pack(fill="x", pady=(4, 10))
        if self.first:
            w = tk.Frame(self.page, bg=WARN_BG, padx=14, pady=10)
            w.pack(fill="x", pady=(0, 6))
            tk.Label(w, text="⚠  This app is vibe coded: an AI wrote it and a person reviewed only a small part. "
                             "Use it at your own risk.", bg=WARN_BG, fg="#ffd8a8", font=self.f["body"], anchor="w",
                     justify="left", wraplength=640).pack(fill="x")

        self._h2("How you talk to it", "Hold the key while you talk. A quick tap works too: tap, talk, tap.")
        keys = tk.Frame(self.page, bg=BG)
        keys.pack(fill="x")
        self.key_labels = {}
        for mode, name in (("agent_key", "Commands key"), ("dictate_key", "Typing key")):
            card = tk.Frame(keys, bg=CARD, padx=14, pady=10, highlightthickness=1, highlightbackground=LINE)
            card.pack(side="left", fill="x", expand=True, padx=(0, 8) if mode == "agent_key" else 0)
            tk.Label(card, text=name, bg=CARD, fg=SOFT, font=self.f["small"], anchor="w").pack(fill="x")
            lab = tk.Label(card, text=hotkey.label(self.v[mode]), bg=CARD, fg=INK, font=self.f["key"], anchor="w")
            lab.pack(fill="x")
            self.key_labels[mode] = lab
            links = tk.Frame(card, bg=CARD)
            links.pack(fill="x", pady=(4, 0))
            for text, action in (("Press a new key", lambda m=mode: self._capture(m)),
                                 ("Mouse back", lambda m=mode: self._set_key(m, "mouse4")),
                                 ("Mouse forward", lambda m=mode: self._set_key(m, "mouse5"))):
                b = tk.Label(links, text=text, bg=CARD, fg=ACCENT, font=self.f["small"], cursor="hand2")
                b.pack(side="left", padx=(0, 12))
                b.bind("<Button-1>", lambda e, a=action: a())
        self.key_note = tk.Label(self.page, text="", bg=BG, fg="#f76b15", font=self.f["small"], anchor="w")
        self.key_note.pack(fill="x")

        self._row("Always listening", "No key: start with the call word, like “Jarvis, open Spotify”. The mic stays "
                  "on; anything that doesn't start with the call word is thrown away.", "always_listen",
                  on_change=self._call_state)
        cw = tk.Frame(self.page, bg=BG)
        cw.pack(fill="x", pady=(2, 0))
        tk.Label(cw, text="Call word", bg=BG, fg=INK, font=self.f["body"], width=16, anchor="w").pack(side="left")
        self.call_var = tk.StringVar(value=self.v.get("call_word", "computer").title())
        self.call_entry = tk.Entry(cw, textvariable=self.call_var, width=22, font=self.f["body"], bg=CARD, fg=INK,
                                   insertbackground=INK, relief="flat")
        self.call_entry.pack(side="left", ipady=4)
        self.call_note = tk.Label(cw, text="", bg=BG, fg="#f76b15", font=self.f["small"])
        self.call_note.pack(side="left", padx=8)
        self._call_state()

        self._h2("Speech model", "Turns your voice into text, on your PC. Parakeet is the quickest; pick Best if "
                 "you want to type in Hindi.")
        cards = [(m, t + (" (recommended)" if m == PARAKEET else ""),
                  f"{line}  ·  {MODELS[m][1]} MB download") for m, t, line in MODEL_CARDS]
        if self.cur.get("model") not in MODELS:
            cards.append((self.cur.get("model"), "Keep the cloud model", "Set up in the tray menu"))
        self._cards(cards, "model")

        self._h2("The pill on screen", "Shows what it heard and what it did, at the top of the screen.")
        self._cards([(v, t, d) for (v, t), d in zip(PILLS, ("Nothing on screen", "A slim line, gone fast",
                                                             "A card with a mic meter and timing",
                                                             "Colours and bouncing bars"))], "pill", columns=4)

        self._h2("Your apps", "Which app it uses when you don't name one.")
        self._segments("“Play …”", MUSIC, "music_app")
        self._segments("“Watch …”", MOVIES, "movie_app")
        self._segments("“Open browser”", BROWSERS, "browser")

        self._h2("Extras", "All off-by-default things live here too.")
        for key, title, sub in EXTRAS:
            self._row(title, sub, key)

    def _footer(self):
        tk = self.tk
        bar = tk.Frame(self.root, bg="#11131a", padx=20, pady=12)
        bar.pack(fill="x", side="bottom")
        tk.Label(bar, text="made by profane for Billa Janta Party", bg="#11131a", fg="#5d6577",
                 font=self.f["small"]).pack(side="left")
        primary = tk.Label(bar, text="Start" if self.first else "Save", bg=ACCENT, fg="#10121a", font=self.f["card"],
                           padx=22, pady=8, cursor="hand2")
        primary.pack(side="right")
        primary.bind("<Button-1>", lambda e: self._save())
        other = tk.Label(bar, text="Skip for now" if self.first else "Cancel", bg="#11131a", fg=SOFT,
                         font=self.f["body"], padx=14, pady=8, cursor="hand2")
        other.pack(side="right", padx=6)
        other.bind("<Button-1>", lambda e: self.root.destroy())

    # ------------------------------------------------------------- behaviour
    def _call_state(self):
        self.call_entry.configure(state="normal" if self.v.get("always_listen") else "disabled",
                                  disabledbackground=BG, disabledforeground=SOFT)

    def _capture(self, mode):
        self.capturing = mode
        self.key_labels[mode].configure(text="Press a key…", fg=ACCENT)
        self.key_note.configure(text="")

    def _set_key(self, mode, combo):
        other = "dictate_key" if mode == "agent_key" else "agent_key"
        if combo == self.v.get(other):
            self.key_note.configure(text=f"{hotkey.label(combo)} is already the other key")
            return
        self.v[mode] = combo
        self.capturing = None
        self.key_labels[mode].configure(text=hotkey.label(combo), fg=INK)
        self.key_note.configure(text="")

    def _key(self, e):
        if not self.capturing:
            return
        from .dialogs import MODIFIER_KEYS, TK
        k = e.keysym.lower()
        if k in MODIFIER_KEYS:
            return
        if k == "escape":
            self.key_labels[self.capturing].configure(text=hotkey.label(self.v[self.capturing]), fg=INK)
            self.capturing = None
            return
        mods = []
        if sys.platform == "win32":
            mods = [m for m, vk in (("ctrl", 0x11), ("alt", 0x12), ("shift", 0x10), ("win", 0x5B))
                    if ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000]
        k = TK.get(k, k)
        combo = "+".join(mods + [k])
        if hotkey.parse(combo) is None:
            self.key_note.configure(text=f"{e.keysym} can't be used, try another key")
            return
        if not mods and (len(k) == 1 or k in ("space", "enter", "tab", "backspace", "delete", "up", "down", "left", "right")):
            self.key_note.configure(text=f"{k.upper()} alone would stop it working for typing: hold Ctrl, Alt or Win with it")
            return
        self._set_key(self.capturing, combo)

    def _save(self):
        word = " ".join(self.call_var.get().lower().split())
        if self.v.get("always_listen"):
            why = listen.call_word_ok(word)
            if why:
                self.call_note.configure(text=why)
                return
        out = {k: self.v[k] for k in ("agent_key", "dictate_key", "model", "always_listen", "music_app", "movie_app",
                                     "browser", "voice_replies", "sounds", "start_with_windows", "unload_in_games",
                                     "auto_update")}
        out["call_word"] = word or self.cur.get("call_word", "computer")
        out["dictate_language"] = "hi" if self.v.get("hindi") else ("en" if self.cur.get("dictate_language") == "hi"
                                                                      else self.cur.get("dictate_language", "en"))
        out["osd"] = self.v["pill"] != "off"
        out["osd_style"] = self.v["pill"] if self.v["pill"] != "off" else self.cur.get("osd_style", "minimal")
        self.result = out
        self.root.destroy()

    def run(self):
        self.root.mainloop()
        return self.result


def run(out, current_path, first_run="0"):
    from .dialogs import _answer
    with open(current_path, encoding="utf-8") as f:
        current = json.load(f)
    _answer(out, Window(current, first_run == "1").run())
