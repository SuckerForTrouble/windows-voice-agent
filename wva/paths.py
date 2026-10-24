"""Where things live. Program files sit in the install folder and get replaced on
every update; everything the user owns (settings, history, tuning, the speech
model) lives in %LOCALAPPDATA%\\WindowsVoiceAgent and survives updates."""
import os
import sys
from pathlib import Path

from . import APP_ID

WINDOWS = sys.platform == "win32"
FROZEN = getattr(sys, "frozen", False)

if WINDOWS:
    DATA = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local") / APP_ID
else:  # developing / testing on Linux
    DATA = Path(os.environ.get("WVA_DATA") or Path.home() / ".local/share/windows-voice-agent-dev")

# The folder WindowsVoiceAgent.exe is in (or the repo root when run from source)
INSTALL = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent.parent

CONFIG = DATA / "config.json"
HISTORY = DATA / "history.jsonl"
TUNING = DATA / "tuning.txt"
TIMERS = DATA / "timers.json"
MODELS = DATA / "models"
LOGS = DATA / "logs"
APPS_CACHE = DATA / "start-apps.json"
GUIDE = DATA / "voice-guide.html"
WHISPER = INSTALL / "whisper"  # whisper/vulkan/whisper-server.exe, whisper/cpu/whisper-server.exe


def ensure():
    for d in (DATA, MODELS, LOGS):
        d.mkdir(parents=True, exist_ok=True)


def user_folder(name):
    """Desktop / Documents / Downloads… where Windows really keeps them (OneDrive moves them)."""
    guids = {
        "desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}", "documents": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
        "downloads": "{374DE290-123F-4565-9164-39C4925E467B}", "pictures": "{33E28130-4E1E-4676-835A-98395C3BC3BB}",
        "music": "{4BD8D571-6D19-48D3-BE97-422220080E43}", "videos": "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}",
    }
    if WINDOWS and name in guids:
        try:
            import ctypes
            import uuid
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                            ("Data4", ctypes.c_ubyte * 8)]

            u = uuid.UUID(guids[name])
            g = GUID(u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8)(*u.bytes[8:]))
            p = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(p)) == 0:
                path = p.value
                ctypes.windll.ole32.CoTaskMemFree(p)
                return Path(path)
        except Exception:
            pass
    return Path.home() / name.capitalize()
