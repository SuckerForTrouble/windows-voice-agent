"""Volume through the Windows audio API (pycaw): the speakers, the mic, and one
app at a time ("spotify volume 30", "mute discord audio")."""
import threading

_local = threading.local()


def _com():
    if not getattr(_local, "com", False):
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass
        _local.com = True


def _endpoint(mic=False):
    _com()
    from ctypes import POINTER, cast

    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    dev = AudioUtilities.GetMicrophone() if mic else AudioUtilities.GetSpeakers()
    ev = getattr(dev, "EndpointVolume", None)  # newer pycaw wraps the device
    if ev is not None:
        return ev
    iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(iface, POINTER(IAudioEndpointVolume))


def get_volume():
    return round(_endpoint().GetMasterVolumeLevelScalar() * 100)


def set_volume(pct):
    ev = _endpoint()
    ev.SetMasterVolumeLevelScalar(max(0.0, min(1.0, pct / 100)), None)
    if pct > 0:
        ev.SetMute(0, None)


def set_mute(state):
    """state: True / False / None (toggle). Returns the new state."""
    ev = _endpoint()
    new = (not ev.GetMute()) if state is None else state
    ev.SetMute(1 if new else 0, None)
    return new


def toggle_mic_mute():
    ev = _endpoint(mic=True)
    new = not ev.GetMute()
    ev.SetMute(1 if new else 0, None)
    return new


def _sessions(exes):
    _com()
    from pycaw.pycaw import AudioUtilities
    out = []
    for s in AudioUtilities.GetAllSessions():
        try:
            if s.Process and s.Process.name().lower() in exes:
                out.append(s)
        except Exception:
            continue
    return out


def app_volume(exes, spec):
    """spec: number 0-100, or 'up' / 'down'. Returns the new level, or None when the app makes no sound."""
    ss = _sessions(exes)
    if not ss:
        return None
    level = None
    for s in ss:
        v = s.SimpleAudioVolume
        cur = v.GetMasterVolume() * 100
        new = cur + 10 if spec == "up" else cur - 10 if spec == "down" else float(spec)
        new = max(0.0, min(100.0, new))
        v.SetMasterVolume(new / 100, None)
        if new > 0:
            v.SetMute(0, None)
        level = round(new)
    return level


def app_mute(exes, state):
    ss = _sessions(exes)
    for s in ss:
        s.SimpleAudioVolume.SetMute(1 if state else 0, None)
    return bool(ss)
