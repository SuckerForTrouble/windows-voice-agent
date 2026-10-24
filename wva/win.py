"""Thin ctypes layer over the Win32 calls the agent needs: keystrokes, typing,
top-level windows (list, focus, close, move), the clipboard, mouse clicks.
Imports fine on Linux (for the routing tests); nothing here is called there."""
import ctypes
import sys
import time

WINDOWS = sys.platform == "win32"

# ----------------------------------------------------------------- key names
VK = {
    "backspace": 0x08, "tab": 0x09, "enter": 0x0D, "return": 0x0D, "shift": 0x10, "ctrl": 0x11, "control": 0x11,
    "alt": 0x12, "pause": 0x13, "capslock": 0x14, "escape": 0x1B, "esc": 0x1B, "space": 0x20,
    "prior": 0x21, "pageup": 0x21, "next": 0x22, "pagedown": 0x22, "end": 0x23, "home": 0x24,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28, "printscreen": 0x2C, "insert": 0x2D, "delete": 0x2E,
    "win": 0x5B, "windows": 0x5B, "apps": 0x5D, "menu": 0x5D,
    "volumemute": 0xAD, "volumedown": 0xAE, "volumeup": 0xAF,
    "medianext": 0xB0, "mediaprev": 0xB1, "mediastop": 0xB2, "mediaplay": 0xB3,
    "semicolon": 0xBA, "plus": 0xBB, "equals": 0xBB, "comma": 0xBC, "minus": 0xBD, "period": 0xBE,
    "slash": 0xBF, "backtick": 0xC0, "bracketleft": 0xDB, "backslash": 0xDC, "bracketright": 0xDD, "quote": 0xDE,
    **{f"f{i}": 0x6F + i for i in range(1, 25)},
    **{str(i): 0x30 + i for i in range(10)},
    **{chr(c): c - 32 for c in range(ord("a"), ord("z") + 1)},
}
EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2C, 0x2D, 0x2E, 0x5B, 0x5D,
            0xAD, 0xAE, 0xAF, 0xB0, 0xB1, 0xB2, 0xB3}
MODS = ("ctrl", "control", "shift", "alt", "win", "windows")


def parse_combo(combo):
    """'ctrl+shift+t' -> ([0x11, 0x10], 0x54); None for an unknown key name."""
    parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
    if not parts or any(p not in VK for p in parts):
        return None
    return [VK[p] for p in parts[:-1]], VK[parts[-1]]


if WINDOWS:
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    dwmapi = ctypes.WinDLL("dwmapi")

    ULONG_PTR = ctypes.c_size_t

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD)]

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _proto(fn, res, *args):
        fn.restype, fn.argtypes = res, list(args)

    _proto(user32.SendInput, wintypes.UINT, wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    _proto(user32.GetForegroundWindow, wintypes.HWND)
    _proto(user32.SetForegroundWindow, wintypes.BOOL, wintypes.HWND)
    _proto(user32.BringWindowToTop, wintypes.BOOL, wintypes.HWND)
    _proto(user32.ShowWindow, wintypes.BOOL, wintypes.HWND, ctypes.c_int)
    _proto(user32.IsIconic, wintypes.BOOL, wintypes.HWND)
    _proto(user32.IsZoomed, wintypes.BOOL, wintypes.HWND)
    _proto(user32.IsWindow, wintypes.BOOL, wintypes.HWND)
    _proto(user32.IsWindowVisible, wintypes.BOOL, wintypes.HWND)
    _proto(user32.GetWindow, wintypes.HWND, wintypes.HWND, wintypes.UINT)
    _proto(user32.GetWindowLongW, wintypes.LONG, wintypes.HWND, ctypes.c_int)
    _proto(user32.GetWindowTextLengthW, ctypes.c_int, wintypes.HWND)
    _proto(user32.GetWindowTextW, ctypes.c_int, wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    _proto(user32.GetClassNameW, ctypes.c_int, wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    _proto(user32.GetWindowThreadProcessId, wintypes.DWORD, wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    _proto(user32.EnumWindows, wintypes.BOOL, WNDENUMPROC, wintypes.LPARAM)
    _proto(user32.PostMessageW, wintypes.BOOL, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    _proto(user32.GetWindowRect, wintypes.BOOL, wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    _proto(user32.SetWindowPos, wintypes.BOOL, wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
           ctypes.c_int, ctypes.c_int, wintypes.UINT)
    _proto(user32.MonitorFromWindow, wintypes.HMONITOR, wintypes.HWND, wintypes.DWORD)
    _proto(user32.GetMonitorInfoW, wintypes.BOOL, wintypes.HMONITOR, ctypes.POINTER(MONITORINFO))
    _proto(user32.AttachThreadInput, wintypes.BOOL, wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
    _proto(user32.MapVirtualKeyW, wintypes.UINT, wintypes.UINT, wintypes.UINT)
    _proto(user32.GetAsyncKeyState, ctypes.c_short, ctypes.c_int)
    _proto(user32.SetCursorPos, wintypes.BOOL, ctypes.c_int, ctypes.c_int)
    _proto(user32.GetCursorPos, wintypes.BOOL, ctypes.POINTER(wintypes.POINT))
    _proto(user32.OpenClipboard, wintypes.BOOL, wintypes.HWND)
    _proto(user32.CloseClipboard, wintypes.BOOL)
    _proto(user32.EmptyClipboard, wintypes.BOOL)
    _proto(user32.GetClipboardData, wintypes.HANDLE, wintypes.UINT)
    _proto(user32.SetClipboardData, wintypes.HANDLE, wintypes.UINT, wintypes.HANDLE)
    _proto(user32.LockWorkStation, wintypes.BOOL)
    _proto(kernel32.GlobalAlloc, wintypes.HGLOBAL, wintypes.UINT, ctypes.c_size_t)
    _proto(kernel32.GlobalLock, wintypes.LPVOID, wintypes.HGLOBAL)
    _proto(kernel32.GlobalUnlock, wintypes.BOOL, wintypes.HGLOBAL)
    _proto(kernel32.GetCurrentThreadId, wintypes.DWORD)
    _proto(kernel32.OpenProcess, wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    _proto(kernel32.CloseHandle, wintypes.BOOL, wintypes.HANDLE)
    _proto(kernel32.QueryFullProcessImageNameW, wintypes.BOOL, wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
           ctypes.POINTER(wintypes.DWORD))
    _proto(dwmapi.DwmGetWindowAttribute, ctypes.c_long, wintypes.HWND, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD)

INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x1, 0x2, 0x4
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x2, 0x4
WM_CLOSE = 0x0010
SW_MAXIMIZE, SW_MINIMIZE, SW_RESTORE, SW_SHOWNOACTIVATE = 3, 6, 9, 4
HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE = 0x1, 0x2, 0x4, 0x10
GWL_EXSTYLE, WS_EX_TOOLWINDOW, WS_EX_TOPMOST = -20, 0x80, 0x8


# ----------------------------------------------------------------- keyboard
def _key_input(vk, up=False):
    flags = (KEYEVENTF_KEYUP if up else 0) | (KEYEVENTF_EXTENDEDKEY if vk in EXTENDED else 0)
    i = INPUT(type=INPUT_KEYBOARD)
    i.ki = KEYBDINPUT(wVk=vk, wScan=user32.MapVirtualKeyW(vk, 0), dwFlags=flags, time=0, dwExtraInfo=0)
    return i


def _send(inputs):
    if inputs:
        arr = (INPUT * len(inputs))(*inputs)
        user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def send_keys(mods, key, times=1):
    for _ in range(max(1, times)):
        seq = [_key_input(m) for m in mods] + [_key_input(key), _key_input(key, True)]
        seq += [_key_input(m, True) for m in reversed(mods)]
        _send(seq)
        time.sleep(0.03)


def type_unicode(text):
    """Type text as unicode key events (no clipboard involved). Newlines become Enter."""
    seq = []
    for ch in text.replace("\r\n", "\n"):
        if ch == "\n":
            seq += [_key_input(0x0D), _key_input(0x0D, True)]
            continue
        units = ch.encode("utf-16-le")
        for k in range(0, len(units), 2):  # characters outside the BMP are two UTF-16 units
            code = int.from_bytes(units[k:k + 2], "little")
            for up in (False, True):
                i = INPUT(type=INPUT_KEYBOARD)
                i.ki = KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0),
                                  time=0, dwExtraInfo=0)
                seq.append(i)
    for k in range(0, len(seq), 200):  # big chunks get dropped by some apps
        _send(seq[k:k + 200])
        time.sleep(0.01)


def key_is_down(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


# ----------------------------------------------------------------- mouse
def double_click(x, y):
    old = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(old))
    user32.SetCursorPos(int(x), int(y))
    seq = []
    for _ in range(2):
        for flag in (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP):
            i = INPUT(type=INPUT_MOUSE)
            i.mi = MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=flag, time=0, dwExtraInfo=0)
            seq.append(i)
    _send(seq)
    time.sleep(0.05)
    user32.SetCursorPos(old.x, old.y)


# ----------------------------------------------------------------- windows
class Win:
    __slots__ = ("hwnd", "title", "cls", "pid", "exe", "minimized")

    def __init__(self, hwnd):
        self.hwnd = hwnd
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        self.title = buf.value
        cbuf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cbuf, 256)
        self.cls = cbuf.value
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        self.pid = pid.value
        self.exe = exe_name(self.pid)
        self.minimized = bool(user32.IsIconic(hwnd))

    @property
    def app(self):
        return self.exe[:-4] if self.exe.lower().endswith(".exe") else self.exe

    def __repr__(self):
        return f"<{self.exe} {self.title[:40]!r}>"


def exe_name(pid):
    h = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value.rsplit("\\", 1)[-1]
        return ""
    finally:
        kernel32.CloseHandle(h)


def exe_path(pid):
    h = kernel32.OpenProcess(0x1000, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        return buf.value if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)) else ""
    finally:
        kernel32.CloseHandle(h)


_SKIP_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Windows.UI.Core.CoreWindow",
                 "TaskManagerWindow", "tkinter_osd"}


def _cloaked(hwnd):
    v = ctypes.c_int(0)
    dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(v), ctypes.sizeof(v))  # DWMWA_CLOAKED
    return v.value != 0


def windows():
    """Top-level app windows the way Alt-Tab sees them, front to back."""
    out = []

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, 4):  # GW_OWNER
            return True
        if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW or _cloaked(hwnd):
            return True
        if not user32.GetWindowTextLengthW(hwnd):
            return True
        w = Win(hwnd)
        if w.cls not in _SKIP_CLASSES:
            out.append(w)
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return out


def foreground():
    h = user32.GetForegroundWindow()
    return Win(h) if h else None


def focus(hwnd):
    """SetForegroundWindow only works for the app that got the last input, so borrow
    the foreground thread's input state for a moment (the usual workaround)."""
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    fg = user32.GetForegroundWindow()
    me = kernel32.GetCurrentThreadId()
    other = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    attached = other and other != me and user32.AttachThreadInput(me, other, True)
    try:
        user32.BringWindowToTop(hwnd)
        ok = user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(me, other, False)
    if not ok:  # last resort: a lone Alt tap unlocks SetForegroundWindow
        send_keys([], VK["alt"])
        ok = user32.SetForegroundWindow(hwnd)
    return bool(ok)


def close(hwnd):
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)


def minimize(hwnd):
    user32.ShowWindow(hwnd, SW_MINIMIZE)


def restore(hwnd):
    user32.ShowWindow(hwnd, SW_RESTORE)


def toggle_maximize(hwnd):
    user32.ShowWindow(hwnd, SW_RESTORE if user32.IsZoomed(hwnd) else SW_MAXIMIZE)


def is_alive(hwnd):
    return bool(user32.IsWindow(hwnd))


def toggle_topmost(hwnd):
    on = not (user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOPMOST)
    user32.SetWindowPos(hwnd, HWND_TOPMOST if on else HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
    return on


def rect(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def move(hwnd, x, y, w, h):
    if user32.IsZoomed(hwnd) or user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetWindowPos(hwnd, None, int(x), int(y), int(w), int(h), SWP_NOZORDER | SWP_NOACTIVATE)


def _monitor_info(hwnd):
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, 2), ctypes.byref(mi))  # MONITOR_DEFAULTTONEAREST
    return mi


def work_area(hwnd):
    r = _monitor_info(hwnd).rcWork
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def covers_monitor(hwnd):
    """Borderless/exclusive fullscreen (how games usually run)."""
    m = _monitor_info(hwnd).rcMonitor
    x, y, w, h = rect(hwnd)
    return x <= m.left and y <= m.top and x + w >= m.right and y + h >= m.bottom


def lock():
    user32.LockWorkStation()


# ----------------------------------------------------------------- clipboard
CF_UNICODETEXT = 13


def clipboard_text():
    for _ in range(10):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        return ""
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        p = kernel32.GlobalLock(h)
        try:
            return ctypes.wstring_at(p) if p else ""
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def set_clipboard(text):
    data = ctypes.create_unicode_buffer(text)
    size = ctypes.sizeof(data)
    for _ in range(10):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        return False
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(0x0002, size)  # GMEM_MOVEABLE
        p = kernel32.GlobalLock(h)
        ctypes.memmove(p, data, size)
        kernel32.GlobalUnlock(h)
        user32.SetClipboardData(CF_UNICODETEXT, h)
        return True
    finally:
        user32.CloseClipboard()


# ----------------------------------------------------------------- processes
def kill_with_me(proc):
    """Put a child process in a job that dies with us, so whisper-server never outlives
    the agent and keeps the GPU memory (even if the agent crashes)."""
    try:
        from ctypes import wintypes as wt

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in ("r", "w", "o", "rb", "wb", "ob")]

        class BASIC(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                        ("LimitFlags", wt.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wt.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wt.DWORD), ("SchedulingClass", wt.DWORD)]

        class EXTENDED(ctypes.Structure):
            _fields_ = [("Basic", BASIC), ("Io", IO_COUNTERS), ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        kernel32.CreateJobObjectW.restype = wt.HANDLE
        job = kernel32.CreateJobObjectW(None, None)
        info = EXTENDED()
        info.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        kernel32.SetInformationJobObject(wt.HANDLE(job), 9, ctypes.byref(info), ctypes.sizeof(info))
        kernel32.AssignProcessToJobObject(wt.HANDLE(job), wt.HANDLE(int(proc._handle)))
        return job  # keep the handle alive for as long as we run
    except Exception:
        return None


def single_instance(name):
    """True if we are the only copy running (named mutex)."""
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32._wva_mutex = kernel32.CreateMutexW(None, False, f"Local\\{name}")
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS
