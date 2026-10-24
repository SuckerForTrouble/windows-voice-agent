"""Push-to-talk keys with RegisterHotKey (no keyboard hook: nothing that looks like a
keylogger to antivirus, works while a game or an admin window is in front).
Windows reports the press; the release is watched with GetAsyncKeyState.

The mouse's side buttons can be push-to-talk too ("mouse4" = back, "mouse5" =
forward): hotkeys can't see mouse buttons, so a tiny native helper
(native/mouse-buttons) watches just those two and reports each press. It only
runs while a side button is one of the keys."""
import ctypes
import logging
import subprocess
import threading
import time
from ctypes import wintypes

from . import paths, win

log = logging.getLogger("wva.keys")
MOUSE = {"mouse4": 1, "mouse5": 2}  # config name -> the helper's button number
MOUSE_LABEL = {"mouse4": "Mouse back button", "mouse5": "Mouse forward button"}


def label(combo):
    """How a key is shown: 'F9', 'Ctrl + Alt + Space', 'Mouse back button'."""
    return MOUSE_LABEL.get(combo) or combo.upper().replace("+", " + ")

WM_HOTKEY, WM_APP = 0x0312, 0x8000
MOD = {"alt": 0x1, "ctrl": 0x2, "control": 0x2, "shift": 0x4, "win": 0x8}
MOD_NOREPEAT = 0x4000


def parse(combo):
    """'f9' / 'ctrl+alt+space' -> (modifier flags, vk) or None."""
    parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
    if not parts or parts[-1] not in win.VK:
        return None
    mods = 0
    for p in parts[:-1]:
        if p not in MOD:
            return None
        mods |= MOD[p]
    return mods, win.VK[parts[-1]]


class Hotkeys:
    """on_press(name) runs when a key goes down; on_release(name, held_seconds) when it comes up."""

    def __init__(self, on_press, on_release):
        self.on_press, self.on_release = on_press, on_release
        self.mouse = {}      # helper button number -> name ("agent" / "dictate")
        self.mouse_proc = None
        self._mouse_job = None
        self.keys = {}       # id -> (name, mods, vk)
        self.thread_id = None
        self._todo = []      # (register?, id, mods, vk, done-event, result-list)
        self._ready = threading.Event()
        threading.Thread(target=self._loop, daemon=True, name="hotkeys").start()
        self._ready.wait(5)

    def _loop(self):
        user32 = ctypes.windll.user32
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # make sure this thread has a queue
        self._ready.set()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_APP:
                while self._todo:
                    reg, hid, mods, vk, ev, res = self._todo.pop(0)
                    if reg:
                        res.append(bool(user32.RegisterHotKey(None, hid, mods | MOD_NOREPEAT, vk)))
                    else:
                        user32.UnregisterHotKey(None, hid)
                        res.append(True)
                    ev.set()
            elif msg.message == WM_HOTKEY and msg.wParam in self.keys:
                name, _, vk = self.keys[msg.wParam]
                threading.Thread(target=self._pressed, args=(name, vk), daemon=True).start()

    def _call(self, reg, hid, mods=0, vk=0):
        ev, res = threading.Event(), []
        self._todo.append((reg, hid, mods, vk, ev, res))
        ctypes.windll.user32.PostThreadMessageW(self.thread_id, WM_APP, 0, 0)
        ev.wait(3)
        return bool(res and res[0])

    def register(self, name, combo):
        if combo in MOUSE:
            self.mouse[MOUSE[combo]] = name
            return self._start_mouse()
        p = parse(combo)
        if not p:
            return False
        hid = len(self.keys) + 1
        while hid in self.keys:
            hid += 1
        if self._call(True, hid, *p):
            self.keys[hid] = (name, *p)
            return True
        return False

    def unregister(self, name):
        if name in self.mouse.values():
            self.mouse = {b: n for b, n in self.mouse.items() if n != name}
            self._start_mouse()
        for hid, (n, _, _) in list(self.keys.items()):
            if n == name:
                self._call(False, hid)
                del self.keys[hid]

    def unregister_all(self):
        for hid in list(self.keys):
            self._call(False, hid)
        self.keys.clear()
        self.mouse = {}
        self._start_mouse()

    # ------------------------------------------------------------- mouse side buttons
    def _start_mouse(self):
        """(Re)start the helper for the buttons in use; stop it when none are. True if it runs."""
        if self.mouse_proc and self.mouse_proc.poll() is None:
            self.mouse_proc.stdin.close()  # it exits when its stdin closes
            try:
                self.mouse_proc.wait(2)
            except subprocess.TimeoutExpired:
                self.mouse_proc.kill()
        self.mouse_proc = None
        if not self.mouse:
            return True
        exe = paths.INSTALL / "helpers" / "mouse-buttons.exe"
        if not exe.exists():
            log.warning("no %s", exe)
            return False
        proc = subprocess.Popen([str(exe), *map(str, sorted(self.mouse))], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=0x08000000)
        self._mouse_job = win.kill_with_me(proc)
        if proc.stdout.readline().strip() != b"ready":
            log.warning("mouse-buttons didn't start (exit %s)", proc.poll())
            return False
        self.mouse_proc = proc
        threading.Thread(target=self._mouse_events, args=(proc, dict(self.mouse)), daemon=True, name="mouse").start()
        return True

    def _mouse_events(self, proc, mapping):
        """One press at a time, in order: a quick tap's 'up' can't overtake its 'down'."""
        t0 = {}
        for line in proc.stdout:
            what, _, button = line.decode(errors="replace").strip().partition(" ")
            name = mapping.get(int(button)) if button.isdigit() else None
            if not name:
                continue
            if what == "down":
                t0[name] = time.time()
                self.on_press(name)
            elif what == "up" and name in t0:
                self.on_release(name, time.time() - t0.pop(name))

    def _pressed(self, name, vk):
        t0 = time.time()
        self.on_press(name)
        if name == "cancel":
            return
        while win.key_is_down(vk) and time.time() - t0 < 60:
            time.sleep(0.015)
        self.on_release(name, time.time() - t0)
