"""The pill at the top of the screen: "Listening…", what was heard and what it did,
answers and errors. It never takes focus (the keys you asked for must reach the
window you were in) and clicks go straight through it."""
import ctypes
import queue
import threading

from . import config

COLORS = {"listen": "#e5484d", "ok": "#46a758", "error": "#f76b15", "info": "#8b95ff", "busy": "#a2a9b8"}
_q = queue.Queue()
_thread = None


def show(text, kind="info", seconds=3.0):
    """kind: listen | busy | ok | error | info. seconds=0 keeps it up until the next call."""
    global _thread
    if not config.get("osd"):
        return
    if _thread is None:
        _thread = threading.Thread(target=_loop, daemon=True, name="osd")
        _thread.start()
    _q.put((text, kind, seconds))


def hide():
    if _thread is not None:
        _q.put(None)


def _loop():
    import tkinter as tk
    user32 = ctypes.windll.user32
    root = tk.Tk()
    # Shown and hidden by its opacity, never by mapping it again: Windows hands focus to
    # a window that appears, and the pill must not take it from the app you're in.
    root.attributes("-alpha", 0.0)
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.configure(bg="#1d2029")
    frame = tk.Frame(root, bg="#1d2029", padx=16, pady=9)
    frame.pack()
    dot = tk.Label(frame, text="●", bg="#1d2029", fg=COLORS["info"], font=("Segoe UI", 13))
    dot.pack(side="left", padx=(0, 8))
    label = tk.Label(frame, text="", bg="#1d2029", fg="#e8eaf0", font=("Segoe UI", 12), wraplength=760, justify="left")
    label.pack(side="left")
    root.update_idletasks()
    hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
    GWL_EXSTYLE = -20
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    # WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOPMOST
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | 0x08000000 | 0x80 | 0x20 | 0x80000 | 0x8)
    from . import win
    win.modern_window(hwnd, dark=True)  # rounded corners on Windows 11
    timer = [None]

    def off():
        root.attributes("-alpha", 0.0)

    def place():
        root.update_idletasks()
        w = root.winfo_reqwidth()
        root.geometry(f"+{(root.winfo_screenwidth() - w) // 2}+{18}")

    def poll():
        try:
            while True:
                item = _q.get_nowait()
                if timer[0]:
                    root.after_cancel(timer[0])
                    timer[0] = None
                if item is None:
                    off()
                    continue
                text, kind, secs = item
                label.config(text=text[:220])
                dot.config(fg=COLORS.get(kind, COLORS["info"]))
                place()
                root.attributes("-alpha", 0.94)
                user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x1 | 0x2 | 0x10)  # topmost, no move/size/activate
                if secs:
                    timer[0] = root.after(int(secs * 1000), off)
        except queue.Empty:
            pass
        root.after(40, poll)

    root.after(40, poll)
    root.mainloop()
