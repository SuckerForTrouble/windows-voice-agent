"""Small windows the tray opens: "press the key you want", "paste your API key", the call
word, and the warning before commands from Discord audio.
Each runs as its own short-lived process (WindowsVoiceAgent.exe --dialog …), so it
never shares a GUI thread with the on-screen pill, and writes its answer to a file."""
import ctypes
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import paths

# Tk key names -> ours (win.VK). Letters and digits are lower-cased as they are.
TK = {"prior": "pageup", "next": "pagedown", "return": "enter", "escape": "escape", "grave": "backtick",
      "scroll_lock": "scrolllock", "caps_lock": "capslock", "app": "apps", "win_l": "win", "win_r": "win"}
MODIFIER_KEYS = {"control_l", "control_r", "shift_l", "shift_r", "alt_l", "alt_r", "win_l", "win_r"}


def ask(kind, *args, timeout=300):
    """Run a dialog and wait for its answer (None when cancelled)."""
    out = Path(tempfile.gettempdir()) / f"wva-dialog-{time.time_ns()}.json"
    argv = [sys.executable] + ([] if paths.FROZEN else ["-m", "wva"]) + ["--dialog", kind, str(out), *args]
    try:
        subprocess.run(argv, timeout=timeout, cwd=str(paths.INSTALL))
        return json.loads(out.read_text(encoding="utf-8")).get("value")
    except Exception:
        return None
    finally:
        out.unlink(missing_ok=True)


def _window(title):
    import tkinter as tk

    from . import win
    win.dpi_aware()
    root = tk.Tk()
    root.title(title)
    root.configure(bg="#1d2029", padx=26, pady=22)
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.update_idletasks()
    win.modern_window(ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id(), dark=True)
    return tk, root


def _answer(out, value):
    Path(out).write_text(json.dumps({"value": value}), encoding="utf-8")


def pick_key(out, which, current):
    """'Press the key you want': F-keys, Pause, Insert…, or anything with Ctrl / Alt / Win
    (a plain letter would stop you typing it, so that is refused)."""
    from . import hotkey, win
    tk, root = _window("Change key")
    label = {"agent": "commands", "dictate": "typing"}.get(which, which)
    tk.Label(root, text=f"Press the key for {label}", bg="#1d2029", fg="#e8eaf0", font=("Segoe UI", 15, "bold")).pack()
    tk.Label(root, text=f"Now: {hotkey.label(current)}   ·   F-keys, Pause, Insert, or a combination like Ctrl+Alt+Space",
             bg="#1d2029", fg="#a2a9b8", font=("Segoe UI", 10)).pack(pady=(6, 14))
    shown = tk.Label(root, text="…", bg="#262a39", fg="#8b95ff", font=("Segoe UI", 18, "bold"), width=22, pady=8)
    shown.pack()
    note = tk.Label(root, text="Esc cancels", bg="#1d2029", fg="#a2a9b8", font=("Segoe UI", 10))
    note.pack(pady=(12, 0))
    result = {}

    def use(combo):
        result["combo"] = combo
        shown.config(text=hotkey.label(combo))
        note.config(text="Saved", fg="#46a758")
        root.after(700, root.destroy)

    # Mouse side buttons can't be pressed into a window as a key, so they get buttons here.
    tk.Label(root, text="or use a mouse side button (it stops doing Back / Forward in browsers):",
             bg="#1d2029", fg="#a2a9b8", font=("Segoe UI", 10)).pack(pady=(16, 6))
    row = tk.Frame(root, bg="#1d2029")
    row.pack()
    for combo in hotkey.MOUSE:
        tk.Button(row, text=hotkey.label(combo), command=lambda c=combo: use(c), font=("Segoe UI", 10),
                  bg="#262a39", fg="#e8eaf0", activebackground="#34384a", activeforeground="#ffffff",
                  relief="flat", padx=12, pady=6).pack(side="left", padx=4)

    def down(e):
        k = e.keysym.lower()
        if k in MODIFIER_KEYS:
            return
        if k == "escape" and not result:
            root.destroy()
            return
        mods = [m for m, vk in (("ctrl", 0x11), ("alt", 0x12), ("shift", 0x10), ("win", 0x5B))
                if ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000]
        k = TK.get(k, k)
        combo = "+".join(mods + [k])
        if hotkey.parse(combo) is None or k not in win.VK:
            note.config(text=f"{e.keysym} can't be used, try another key", fg="#f76b15")
            return
        if not mods and (len(k) == 1 or k in ("space", "enter", "tab", "backspace", "delete", "up", "down", "left", "right")):
            note.config(text=f"{k.upper()} alone would stop it working for typing: add Ctrl, Alt or Win", fg="#f76b15")
            return
        use(combo)

    root.bind("<KeyPress>", down)
    root.focus_force()
    root.mainloop()
    _answer(out, result.get("combo"))


def api_key(out, provider):
    tk, root = _window("Cloud speech")
    name = {"groq": "Groq", "openai": "OpenAI"}.get(provider, provider)
    site = {"groq": "console.groq.com/keys", "openai": "platform.openai.com/api-keys"}.get(provider, "")
    tk.Label(root, text=f"Paste your {name} API key", bg="#1d2029", fg="#e8eaf0", font=("Segoe UI", 15, "bold")).pack()
    tk.Label(root, text=f"Get one at {site}. It's stored encrypted for your Windows account only.\n"
                        f"With cloud speech, every recording is sent to {name} to be turned into text.",
             bg="#1d2029", fg="#a2a9b8", font=("Segoe UI", 10), justify="center").pack(pady=(6, 14))
    var = tk.StringVar()
    entry = tk.Entry(root, textvariable=var, show="•", width=46, font=("Segoe UI", 12))
    entry.pack(ipady=4)
    result = {}

    def save(_=None):
        result["key"] = var.get().strip()
        root.destroy()
    tk.Button(root, text="Save", command=save, width=12).pack(pady=(14, 0))
    root.bind("<Return>", save)
    root.bind("<Escape>", lambda e: root.destroy())
    entry.focus_force()
    root.mainloop()
    _answer(out, result.get("key"))


def call_word(out, current):
    tk, root = _window("Call word")
    tk.Label(root, text="Say this first, then the command", bg="#1d2029", fg="#e8eaf0",
             font=("Segoe UI", 15, "bold")).pack()
    tk.Label(root, text="Like “Angel, open Spotify”. Pick a word you don't say in normal talk:\n"
                        "one to three words, at least 4 letters (Angel, Jarvis, Hey Billa…).\n"
                        "Several work too, with commas: Angel, Jarvis",
             bg="#1d2029", fg="#a2a9b8", font=("Segoe UI", 10), justify="center").pack(pady=(6, 14))
    var = tk.StringVar(value=current.title())
    entry = tk.Entry(root, textvariable=var, width=32, font=("Segoe UI", 14), justify="center")
    entry.pack(ipady=4)
    entry.select_range(0, "end")
    result = {}

    def save(_=None):
        result["word"] = var.get().strip()
        root.destroy()
    tk.Button(root, text="Save", command=save, width=12).pack(pady=(14, 0))
    root.bind("<Return>", save)
    root.bind("<Escape>", lambda e: root.destroy())
    entry.focus_force()
    root.mainloop()
    _answer(out, result.get("word"))


def discord_audio(out, words, whole_pc=""):
    """The warning before commands from Discord audio: the switch stays off unless the box
    is ticked and the red button pressed. Enter / Esc keep it off."""
    tk, root = _window("Commands from Discord audio")
    bg, ink, soft, red = "#1d2029", "#e8eaf0", "#a2a9b8", "#e5484d"
    tk.Label(root, text="⚠  DANGEROUS: read this first", bg=bg, fg=red, font=("Segoe UI", 17, "bold")).pack(anchor="w")
    tk.Label(root, text=f"Anyone in your Discord call can control THIS PC by saying “{words}, …”", bg=bg, fg=ink,
             font=("Segoe UI", 12, "bold"), wraplength=520, justify="left").pack(anchor="w", pady=(8, 8))
    risks = ["Every command works for them, exactly like for you: close apps and games, type text, press any key, "
             "open websites, shut down or restart the PC.",
             "Nothing is blocked or filtered. A troll, a soundboard or a video someone streams can do it too.",
             "Only turn it on in a call with people you trust completely.",
             "It turns itself off when the voice agent restarts, and is never saved."]
    if whole_pc:
        risks.insert(2, "On this Windows version it can't hear Discord alone: it listens to EVERYTHING your PC "
                        "plays (games, videos, music), so a video saying the call word counts too. Windows 11 fixes that.")
    for r in risks:
        tk.Label(root, text="•  " + r, bg=bg, fg=soft, font=("Segoe UI", 10), wraplength=520, justify="left").pack(anchor="w", pady=2)
    sure = tk.BooleanVar(value=False)
    tk.Checkbutton(root, text="I understand, and I trust everyone in my Discord calls", variable=sure, bg=bg, fg=ink,
                   selectcolor="#262a39", activebackground=bg, activeforeground=ink, font=("Segoe UI", 10),
                   command=lambda: go.config(state="normal" if sure.get() else "disabled")).pack(anchor="w", pady=(14, 8))
    row = tk.Frame(root, bg=bg)
    row.pack(fill="x")
    result = {}

    def on():
        if sure.get():
            result["v"] = "on"
            root.destroy()
    keep = tk.Button(row, text="Keep it off", command=root.destroy, width=14, font=("Segoe UI", 10))
    keep.pack(side="right")
    go = tk.Button(row, text="Turn it on", command=on, width=14, font=("Segoe UI", 10, "bold"), bg=red, fg="white",
                   activebackground="#c13a3e", activeforeground="white", state="disabled")
    go.pack(side="right", padx=(0, 8))
    root.bind("<Return>", lambda e: root.destroy())
    root.bind("<Escape>", lambda e: root.destroy())
    keep.focus_force()
    root.mainloop()
    _answer(out, result.get("v"))


def run(kind, out, *args):
    if kind == "settings":
        from . import settings_window
        return settings_window.run(out, *args)
    {"pick-key": pick_key, "api-key": api_key, "call-word": call_word, "discord-audio": discord_audio}[kind](out, *args)
