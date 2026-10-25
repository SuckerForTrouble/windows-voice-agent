"""Commands heard from Discord audio (tray → More options, off at every start, never saved):
what your Discord call plays goes through the same voice detector and call word as
always listening, so a friend saying "Angel, open Spotify" runs it on THIS PC. Nothing
is filtered or blocked (the user's choice): the warnings are the safety.

How it hears Discord (Windows' own audio API, WASAPI, through comtypes):
  Windows 11   process loopback: only Discord's sound (and its helper processes), not
               the game, music or videos (needs build 20348 or newer)
  Windows 10   loopback of the default speakers: EVERYTHING the PC plays, so a video
               saying the call word counts too. The warning says so.
Either way the audio is asked for as 16 kHz mono, the speech model's format; Windows
converts it (AUTOCONVERTPCM), and if a device refuses, it is converted here."""
import array
import ctypes
import sys
import threading
import time

from . import listen

WINDOWS = sys.platform == "win32"
RATE, FRAME_BYTES = listen.RATE, listen.FRAME * 2
PROCESS_LOOPBACK_BUILD = 20348
LOOPBACK, EVENTS, AUTOCONVERT, SRC_QUALITY = 0x00020000, 0x00040000, 0x80000000, 0x08000000
SILENT = 0x2  # AUDCLNT_BUFFERFLAGS_SILENT


def process_loopback_ok():
    return WINDOWS and sys.getwindowsversion().build >= PROCESS_LOOPBACK_BUILD


def discord_pid():
    """The Discord that's running: its first process (the others are its children, and
    process loopback takes the whole tree). None if Discord isn't running."""
    import psutil

    from .extras import CLIENTS
    procs = {}
    for p in psutil.process_iter(["pid", "ppid", "name"]):
        try:
            if (p.info["name"] or "").lower() in CLIENTS:
                procs[p.info["pid"]] = p.info["ppid"]
        except Exception:
            continue
    roots = [pid for pid, parent in procs.items() if parent not in procs]
    return min(roots) if roots else None


def to_16k_mono(data, channels, rate, floats):
    """Interleaved float32 / int16 samples at any rate -> 16 kHz mono int16 bytes. Each
    output sample is the average of the input samples it covers (a cheap low-pass)."""
    a = array.array("f" if floats else "h", data)
    scale = 32767.0 if floats else 1.0
    n = len(a) // channels
    mono = [sum(a[i * channels:(i + 1) * channels]) * scale / channels for i in range(n)]
    step = rate / RATE
    out = array.array("h")
    i = 0.0
    while int(i + step) <= n:
        chunk = mono[int(i):max(int(i) + 1, int(i + step))]
        out.append(max(-32768, min(32767, int(sum(chunk) / len(chunk)))))
        i += step
    return out.tobytes()


# ----------------------------------------------------------------- WASAPI, the parts we need
_I = {}


def _interfaces():
    """The COM interfaces and structs, defined once (comtypes keeps a registry of them)."""
    if not _I:
        _I.update(_define())
    return _I


def _define():
    from ctypes import POINTER, Structure, c_int, c_int64, c_ubyte, c_uint32, c_uint64, c_ulong, c_ushort, c_void_p
    from ctypes.wintypes import DWORD, HANDLE, WORD

    from comtypes import COMMETHOD, GUID, HRESULT, IUnknown

    class WAVEFORMATEX(Structure):
        _fields_ = [("wFormatTag", WORD), ("nChannels", WORD), ("nSamplesPerSec", DWORD), ("nAvgBytesPerSec", DWORD),
                    ("nBlockAlign", WORD), ("wBitsPerSample", WORD), ("cbSize", WORD)]

    class IAudioClient(IUnknown):
        _iid_ = GUID("{1CB9AD4C-DBFA-4C32-B178-C2F568A703B2}")
        _methods_ = [
            COMMETHOD([], HRESULT, "Initialize", (["in"], DWORD, "mode"), (["in"], DWORD, "flags"),
                      (["in"], c_int64, "buffer"), (["in"], c_int64, "period"), (["in"], POINTER(WAVEFORMATEX), "fmt"),
                      (["in"], POINTER(GUID), "session")),
            COMMETHOD([], HRESULT, "GetBufferSize", (["out"], POINTER(c_uint32), "frames")),
            COMMETHOD([], HRESULT, "GetStreamLatency", (["out"], POINTER(c_int64), "latency")),
            COMMETHOD([], HRESULT, "GetCurrentPadding", (["out"], POINTER(c_uint32), "frames")),
            COMMETHOD([], HRESULT, "IsFormatSupported", (["in"], DWORD, "mode"), (["in"], POINTER(WAVEFORMATEX), "fmt"),
                      (["out"], POINTER(POINTER(WAVEFORMATEX)), "closest")),
            COMMETHOD([], HRESULT, "GetMixFormat", (["out"], POINTER(POINTER(WAVEFORMATEX)), "fmt")),
            COMMETHOD([], HRESULT, "GetDevicePeriod", (["out"], POINTER(c_int64), "default"), (["out"], POINTER(c_int64), "minimum")),
            COMMETHOD([], HRESULT, "Start"),
            COMMETHOD([], HRESULT, "Stop"),
            COMMETHOD([], HRESULT, "Reset"),
            COMMETHOD([], HRESULT, "SetEventHandle", (["in"], HANDLE, "event")),
            COMMETHOD([], HRESULT, "GetService", (["in"], POINTER(GUID), "iid"), (["out"], POINTER(POINTER(IUnknown)), "service")),
        ]

    class IAudioCaptureClient(IUnknown):
        _iid_ = GUID("{C8ADBD64-E71E-48A0-A4DE-185C395CD317}")
        _methods_ = [
            COMMETHOD([], HRESULT, "GetBuffer", (["out"], POINTER(POINTER(c_ubyte)), "data"), (["out"], POINTER(c_uint32), "frames"),
                      (["out"], POINTER(DWORD), "flags"), (["out"], POINTER(c_uint64), "position"), (["out"], POINTER(c_uint64), "qpc")),
            COMMETHOD([], HRESULT, "ReleaseBuffer", (["in"], c_uint32, "frames")),
            COMMETHOD([], HRESULT, "GetNextPacketSize", (["out"], POINTER(c_uint32), "frames")),
        ]

    class IActivateAudioInterfaceAsyncOperation(IUnknown):
        _iid_ = GUID("{72A22D78-CDE4-431D-B8CC-843A71199B6D}")
        _methods_ = [COMMETHOD([], HRESULT, "GetActivateResult", (["out"], POINTER(c_int), "result"),
                               (["out"], POINTER(POINTER(IUnknown)), "iface"))]

    class IActivateAudioInterfaceCompletionHandler(IUnknown):
        _iid_ = GUID("{41D949AB-9862-444A-80F6-C261334DA5EB}")
        _methods_ = [COMMETHOD([], HRESULT, "ActivateCompleted", (["in"], POINTER(IActivateAudioInterfaceAsyncOperation), "op"))]

    class IAgileObject(IUnknown):  # tells Windows the handler may be called from any thread
        _iid_ = GUID("{94EA2B94-E9CC-49E0-C0FF-EE64CA8F5B90}")
        _methods_ = []

    class LoopbackParams(Structure):
        _fields_ = [("TargetProcessId", DWORD), ("ProcessLoopbackMode", c_int)]

    class ActivationParams(Structure):
        _fields_ = [("ActivationType", c_int), ("ProcessLoopbackParams", LoopbackParams)]

    class BLOB(Structure):
        _fields_ = [("cbSize", c_ulong), ("pBlobData", c_void_p)]

    class PROPVARIANT(Structure):  # just the VT_BLOB case
        _fields_ = [("vt", c_ushort), ("r1", c_ushort), ("r2", c_ushort), ("r3", c_ushort), ("blob", BLOB)]

    return {c.__name__: c for c in (WAVEFORMATEX, IAudioClient, IAudioCaptureClient, IActivateAudioInterfaceAsyncOperation,
                                    IActivateAudioInterfaceCompletionHandler, IAgileObject, LoopbackParams,
                                    ActivationParams, BLOB, PROPVARIANT)}


def _open_process(I, pid):
    """An audio client on one process tree's sound (Windows 11: ActivateAudioInterfaceAsync)."""
    from ctypes import POINTER, byref, c_void_p, cast, sizeof

    import comtypes
    from comtypes import COMObject

    done = threading.Event()

    class Handler(COMObject):
        _com_interfaces_ = [I["IActivateAudioInterfaceCompletionHandler"], I["IAgileObject"]]

        def ActivateCompleted(self, op):
            done.set()

    params = I["ActivationParams"](1, I["LoopbackParams"](pid, 0))  # PROCESS_LOOPBACK, INCLUDE_TARGET_PROCESS_TREE
    pv = I["PROPVARIANT"](65, 0, 0, 0, I["BLOB"](sizeof(params), cast(byref(params), c_void_p)))  # VT_BLOB
    op = POINTER(I["IActivateAudioInterfaceAsyncOperation"])()
    handler = Handler()
    fn = ctypes.windll.mmdevapi.ActivateAudioInterfaceAsync
    fn.argtypes = [ctypes.c_wchar_p, POINTER(comtypes.GUID), POINTER(I["PROPVARIANT"]),
                   POINTER(I["IActivateAudioInterfaceCompletionHandler"]), POINTER(POINTER(I["IActivateAudioInterfaceAsyncOperation"]))]
    hr = fn("VAD\\Process_Loopback", byref(I["IAudioClient"]._iid_), byref(pv),
            handler.QueryInterface(I["IActivateAudioInterfaceCompletionHandler"]), byref(op))
    if hr:
        raise OSError(f"ActivateAudioInterfaceAsync failed ({hr & 0xFFFFFFFF:#x})")
    if not done.wait(5):
        raise OSError("Windows didn't answer the audio request")
    result, iface = op.GetActivateResult()
    if result:
        raise OSError(f"Windows refused to share Discord's sound ({result & 0xFFFFFFFF:#x})")
    return iface.QueryInterface(I["IAudioClient"])


def _open_speakers(I):
    from comtypes import CLSCTX_ALL

    from .audio import _enumerator
    dev = _enumerator().GetDefaultAudioEndpoint(0, 0)  # render, console
    return dev.Activate(I["IAudioClient"]._iid_, CLSCTX_ALL, None).QueryInterface(I["IAudioClient"])


class Capture:
    """Discord's sound (or the speakers') as 16 kHz mono 16-bit, in read() calls."""

    def __init__(self, pid=None):
        import comtypes
        try:
            comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
        except OSError:
            pass  # this thread already has COM (the self-test's)
        I = _interfaces()
        self.client = _open_process(I, pid) if pid else _open_speakers(I)
        want = I["WAVEFORMATEX"](1, 1, RATE, RATE * 2, 2, 16, 0)  # PCM, mono, 16 kHz, 16-bit
        self.convert, self.block = None, 2
        try:
            self.client.Initialize(0, LOOPBACK | EVENTS | AUTOCONVERT | SRC_QUALITY, 2_000_000, 0, ctypes.byref(want), None)
        except Exception:
            if pid:
                raise
            mix = self.client.GetMixFormat()  # this device won't convert: take its own format and convert here
            f = mix.contents
            floats = f.wFormatTag == 3 or (f.wFormatTag == 0xFFFE and f.wBitsPerSample == 32)
            if not floats and f.wBitsPerSample != 16:
                raise OSError(f"the speakers use {f.wBitsPerSample}-bit sound, which this can't read")
            self.convert, self.block = (f.nChannels, f.nSamplesPerSec, floats), f.nBlockAlign
            self.client.Initialize(0, LOOPBACK | EVENTS, 2_000_000, 0, mix, None)
            ctypes.windll.ole32.CoTaskMemFree(mix)
        k32 = ctypes.windll.kernel32
        k32.CreateEventW.restype = ctypes.c_void_p
        self.event = k32.CreateEventW(None, False, False, None)  # Windows sets it when sound arrives
        self.client.SetEventHandle(self.event)
        self.cap = self.client.GetService(ctypes.byref(I["IAudioCaptureClient"]._iid_)).QueryInterface(I["IAudioCaptureClient"])
        self.client.Start()

    def read(self):
        """Whatever arrived since the last call (b'' if nothing), after waiting up to 20 ms
        for Windows to say there's more (read anyway when it doesn't)."""
        ctypes.windll.kernel32.WaitForSingleObject(ctypes.c_void_p(self.event), 20)
        out = []
        while self.cap.GetNextPacketSize():
            data, frames, flags, _, _ = self.cap.GetBuffer()
            n = frames * self.block
            raw = bytes(n) if flags & SILENT else ctypes.string_at(data, n)
            self.cap.ReleaseBuffer(frames)
            out.append(to_16k_mono(raw, *self.convert) if self.convert else raw)
        return b"".join(out)

    def close(self):
        try:
            self.client.Stop()
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(self.event))
        except Exception:
            pass


class DiscordListener(listen.Listener):
    """Like the always-on mic, but its frames come from Discord's sound. on_closed(why)
    is called if it stops by itself (Discord quit)."""

    def __init__(self, on_phrase, paused=lambda: False, on_closed=lambda why: None):
        super().__init__(on_phrase, paused)
        self.on_closed = on_closed
        self.whole_pc = False

    def start(self, mic=""):
        pid = discord_pid()
        if not pid:
            raise OSError("Discord isn't running")
        self.whole_pc = not process_loopback_ok()
        ready, failed = threading.Event(), []
        self.running = True
        threading.Thread(target=self._capture, args=(None if self.whole_pc else pid, pid, ready, failed),
                         daemon=True, name="discord-audio").start()
        ready.wait(8)
        if failed or not ready.is_set():
            self.running = False
            raise OSError(failed[0] if failed else "the audio didn't start")
        threading.Thread(target=self._loop, daemon=True, name="discord-listen").start()

    def _capture(self, target, pid, ready, failed):
        import psutil
        try:
            cap = Capture(target)
        except Exception as e:
            failed.append(str(e))
            ready.set()
            return
        ready.set()
        buf, checked = b"", time.time()
        try:
            while self.running:
                buf += cap.read()
                while len(buf) >= FRAME_BYTES:
                    try:
                        self.frames.put_nowait(buf[:FRAME_BYTES])
                    except Exception:
                        pass
                    buf = buf[FRAME_BYTES:]
                if time.time() - checked > 5:
                    checked = time.time()
                    if not psutil.pid_exists(pid):
                        self.running = False
                        self.on_closed("Discord closed")
        except Exception as e:
            self.running = False
            self.on_closed(f"Discord audio stopped: {e}")
        finally:
            cap.close()

    def stop(self):
        self.running = False
