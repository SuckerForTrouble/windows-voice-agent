"""Volume through the Windows audio API (pycaw): the speakers, the mic, and one
app at a time ("spotify volume 30", "mute discord audio"). Also the sound devices:
"switch to headphones", "headphones volume 30", "list audio devices", and one app's
output ("spotify on the speakers")."""
import re
import threading
import time

from . import paths, ui
from .engine import CTX, num

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


# ----------------------------------------------------------------- sound devices
RENDER, CAPTURE = 0, 1
_FRIENDLY_NAME = ("{a45c254e-df1c-4efd-8020-67d146a850e0}", 14)
# Words that say "a sound device" (the routing tests have no devices to ask)
DEVICE_WORDS = {"headphones", "headphone", "headset", "earphones", "earphone", "earbuds", "buds", "airpods", "speakers",
                "speaker", "tv", "monitor", "hdmi", "bluetooth", "soundbar", "realtek", "dac", "laptop"}
# "switch to the second monitor" is about screens, not sound
SCREENS = {"second", "other", "left", "right", "main", "primary", "first", "next", "previous", "last", "window"}
FILLER = {"the", "my", "a", "audio", "sound", "output", "outputs", "device", "devices", "playback", "to", "on", "mic",
          "microphone", "input"}
# Other words Windows uses for what you said, and how sure that makes it (earbuds show up as
# "Headset Earphone (Galaxy Buds2)", the TV as "LG TV (NVIDIA High Definition Audio)")
_HEAD = {"headphones": 0.95, "headset": 0.95, "earphone": 0.9, "earphones": 0.9, "hands": 0.85}
_BUDS = {"buds": 0.95, "airpods": 0.95, "earphone": 0.95, "earphones": 0.95, "hands": 0.9, "headset": 0.9, "headphones": 0.85}
_TV = {"tv": 0.95, "hdmi": 0.95, "display": 0.9, "monitor": 0.95, "nvidia": 0.9, "amd": 0.9, "intel": 0.9}
SAME = {**dict.fromkeys(("headphones", "headphone", "headset"), _HEAD),
        **dict.fromkeys(("earbuds", "buds", "airpods", "earphones", "earphone"), _BUDS),
        **dict.fromkeys(("tv", "monitor", "hdmi", "screen"), _TV),
        **dict.fromkeys(("speakers", "speaker"), {"speakers": 0.95, "speaker": 0.95}),
        "laptop": {"speakers": 0.9, "realtek": 0.9, "internal": 0.9},
        "webcam": {"webcam": 0.95, "camera": 0.95, "cam": 0.9, "usb": 0.8}, "camera": {"webcam": 0.95, "camera": 0.95, "cam": 0.9}}
_known = {"t": 0.0, "words": set()}


def _enumerator():
    _com()
    import comtypes
    from pycaw.api.mmdeviceapi import IMMDeviceEnumerator
    from pycaw.constants import CLSID_MMDeviceEnumerator
    return comtypes.CoCreateInstance(CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, comtypes.CLSCTX_INPROC_SERVER)


def _name(dev):
    from comtypes import GUID
    from pycaw.api.mmdeviceapi import PROPERTYKEY
    k = PROPERTYKEY()
    k.fmtid, k.pid = GUID(_FRIENDLY_NAME[0]), _FRIENDLY_NAME[1]
    pv = dev.OpenPropertyStore(0).GetValue(k)
    try:
        return pv.GetValue() or "Unnamed device"
    finally:
        pv.clear()


def devices(flow=RENDER):
    """[(id, name, is_default)] of the plugged-in outputs (flow=CAPTURE: mics)."""
    en = _enumerator()
    try:
        default = en.GetDefaultAudioEndpoint(flow, 1).GetId()
    except Exception:  # nothing plugged in
        default = None
    col = en.EnumAudioEndpoints(flow, 1)  # DEVICE_STATE_ACTIVE
    out = []
    for i in range(col.GetCount()):
        d = col.Item(i)
        out.append((d.GetId(), _name(d), d.GetId() == default))
    return out


def set_default(dev_id):
    """Windows' default device for everything: music and games, and calls (Discord, Teams)."""
    _com()
    import comtypes
    from pycaw.api.policyconfig import IPolicyConfig
    from pycaw.constants import CLSID_CPolicyConfigClient
    pc = comtypes.CoCreateInstance(CLSID_CPolicyConfigClient, IPolicyConfig, comtypes.CLSCTX_ALL)
    for role in (0, 1, 2):  # console, multimedia, communications
        pc.SetDefaultEndpoint(dev_id, role)


def _device_volume(dev_id):
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import IAudioEndpointVolume
    iface = _enumerator().GetDevice(dev_id).Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return iface.QueryInterface(IAudioEndpointVolume)


def _app_policy():
    """The factory behind Settings → Volume mixer → an app's output device: undocumented, the
    same one EarTrumpet uses. Its layout has changed once (Windows 11 21H2) and could again."""
    import ctypes
    import sys
    from ctypes import POINTER, byref, c_void_p

    from comtypes import GUID
    _com()
    combase = ctypes.windll.combase
    combase.WindowsCreateString.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, POINTER(c_void_p)]
    combase.WindowsDeleteString.argtypes = [c_void_p]
    combase.RoGetActivationFactory.argtypes = [c_void_p, POINTER(GUID), POINTER(c_void_p)]
    cls, factory = c_void_p(), c_void_p()
    name = "Windows.Media.Internal.AudioPolicyConfig"
    combase.WindowsCreateString(name, len(name), byref(cls))
    iid = GUID("{ab3d4648-e242-459f-b02f-541c70306324}" if sys.getwindowsversion().build >= 21390
               else "{2a59116d-6c4f-45e0-a74f-707e3fef9258}")
    hr = combase.RoGetActivationFactory(cls, byref(iid), byref(factory))
    combase.WindowsDeleteString(cls)
    if hr or not factory:
        raise OSError(f"this Windows version doesn't offer it (0x{hr & 0xFFFFFFFF:08x})")
    return combase, factory


def app_routing_ok():
    """Whether per-app output can work here (asks for the factory, changes nothing)."""
    import ctypes
    _, f = _app_policy()
    vtbl = ctypes.cast(f, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])(f)  # Release
    return True


def set_app_output(pids, dev_id, flow=RENDER):
    """Send these processes' sound to one device (dev_id None: back to the default)."""
    import ctypes
    from ctypes import HRESULT, POINTER, WINFUNCTYPE, byref, c_int, c_uint, c_void_p
    combase, f = _app_policy()
    vtbl = ctypes.cast(f, POINTER(POINTER(c_void_p))).contents
    # IUnknown (3) + IInspectable (3) + 19 slots EarTrumpet leaves undeclared -> SetPersistedDefaultAudioEndpoint
    set_persisted = WINFUNCTYPE(HRESULT, c_void_p, c_uint, c_int, c_int, c_void_p)(vtbl[25])
    target = c_void_p()
    if dev_id:
        full = "\\\\?\\SWD#MMDEVAPI#" + dev_id + ("#{e6327cad-dcec-4949-ae8a-991e976a79d2}" if flow == RENDER
                                                   else "#{2eef81be-33fa-4800-9670-1cd474972c3f}")
        combase.WindowsCreateString(full, len(full), byref(target))
    try:
        for pid in pids:
            for role in (1, 0):  # multimedia, console
                set_persisted(f, pid, flow, role, target)
    finally:
        if dev_id:
            combase.WindowsDeleteString(target)
        WINFUNCTYPE(ctypes.c_ulong, c_void_p)(vtbl[2])(f)


def _said(text):
    from .files import words
    ws = [w for w in words(text) if w not in FILLER]
    return ws or words(text)


def _known_words():
    """Words of the plugged-in outputs' names ("hyperx", "galaxy"), asked at most once a minute."""
    if paths.WINDOWS and time.time() - _known["t"] > 60:
        _known["t"] = time.time()
        try:
            from .files import words
            _known["words"] = {w for _, n, _ in devices(RENDER) for w in words(n) if len(w) > 2 and not w.isdigit()} - {
                "audio", "high", "definition", "device", "digital", "output", "the", "for", "and", "wireless"}
        except Exception:
            pass
    return _known["words"]


def device_like(text):
    """Does this name a sound output? ("headphones", "the tv", "my hyperx")"""
    ws = _said(text or "")
    return bool(ws) and len(ws) <= 4 and not SCREENS & set(ws) and any(w in DEVICE_WORDS or w in _known_words() for w in ws)


def best(text, devs):
    """The device a spoken name fits best (another one than the current on a tie), or None."""
    from .files import word_match, words
    said = _said(text)

    def fit(name):
        nw = words(name)
        toks = nw + [a + b for a, b in zip(nw, nw[1:])]
        return sum(max(word_match(alt, t) * (1 if alt == w else sure) for alt, sure in {**SAME.get(w, {}), w: 1}.items()
                       for t in toks) for w in said) / len(said)
    ranked = sorted(((fit(n), not dflt, -i) for i, (_, n, dflt) in enumerate(devs)), reverse=True)
    return devs[-ranked[0][2]] if ranked and ranked[0][0] >= 0.6 else None


def _short(name):
    return name if len(name) <= 48 else name[:46] + "…"


def _flow_word(flow):
    return "output" if flow == RENDER else "mic"


def switch(name, flow=RENDER):
    """'switch to headphones' / 'use the webcam mic'."""
    if CTX.dry:
        return CTX.log(f"  default {_flow_word(flow)} -> the one like {name!r}")
    try:
        devs = devices(flow)
        dev = best(name, devs)
        if not dev:
            ui.notify(f"No {_flow_word(flow)} like “{name}”. You have: " + ", ".join(_short(n) for _, n, _ in devs))
            return
        set_default(dev[0])
    except Exception as e:
        ui.notify(f"Couldn't switch the {_flow_word(flow)}: {e}")
        return
    ui.notify(f"{'Sound' if flow == RENDER else 'Mic'} → {_short(dev[1])}")


def switch_next():
    """'switch audio output': with two outputs, the other one; with more, a short list to pick from."""
    if CTX.dry:
        return CTX.log("  the other output (a list when there are more than two)")
    try:
        devs = devices(RENDER)
    except Exception:
        devs = []
    if len(devs) < 2:
        from . import actions
        actions.keys("ctrl+win+v")  # Windows' own output picker
        return
    if len(devs) > 2:
        return list_devices(RENDER)
    other = next(d for d in devs if not d[2])
    set_default(other[0])
    ui.notify(f"Sound → {_short(other[1])}")


def list_devices(flow=RENDER):
    """'list audio devices': a numbered list; 'the second one' switches to it."""
    if CTX.dry:
        return CTX.log(f"  list the {_flow_word(flow)}s; picking one makes it the default")
    from . import choices
    try:
        devs = devices(flow)
    except Exception as e:
        ui.notify(f"Couldn't read the sound devices: {e}")
        return
    if not devs:
        ui.notify("No speakers or headphones found" if flow == RENDER else "No microphone found")
        return

    def use(dev):
        set_default(dev[0])
        ui.notify(f"{'Sound' if flow == RENDER else 'Mic'} → {_short(dev[1])}")
    choices.offer("Sound outputs" if flow == RENDER else "Microphones",
                  [(_short(dev[1]), "in use" if dev[2] else "", dev) for dev in devs], use,
                  "Say “the second one” to switch")


def current():
    """'which output am I using?'"""
    if CTX.dry:
        return CTX.log("  say the output and mic in use")
    try:
        out = next((n for _, n, d in devices(RENDER) if d), None)
        mic = next((n for _, n, d in devices(CAPTURE) if d), None)
        vol = get_volume() if out else None
    except Exception as e:
        ui.notify(f"Couldn't read the sound devices: {e}")
        return
    if not out:
        ui.tell("No speakers or headphones found")
        return
    ui.tell(f"Sound: {_short(out)} ({vol}%)" + (f"  ·  Mic: {_short(mic)}" if mic else ""),
            f"Sound is on {out.split(' (')[0]}" + (f", the mic is {mic.split(' (')[0]}" if mic else ""))


def _spec(spec):
    spec = {"louder": "up", "quieter": "down", "softer": "down"}.get(spec, spec)
    return spec if spec in ("up", "down") else num(spec)


def device_volume(name, spec):
    """'headphones volume 30' / 'turn the speakers down': one output, even when it isn't the one in use."""
    spec = _spec(spec)
    if CTX.dry:
        return CTX.log(f"  volume {spec} on the output like {name!r}")
    try:
        dev = best(name, devices(RENDER))
        if not dev:
            return ui.notify(f"No output like “{name}”")
        ev = _device_volume(dev[0])
        cur = ev.GetMasterVolumeLevelScalar() * 100
        new = max(0, min(100, cur + 10 if spec == "up" else cur - 10 if spec == "down" else spec))
        ev.SetMasterVolumeLevelScalar(new / 100, None)
        if new > 0:
            ev.SetMute(0, None)
    except Exception as e:
        return ui.notify(f"Couldn't change that volume: {e}")
    ui.notify(f"{_short(dev[1])}: {round(new)}%")


def device_mute(state, name):
    on = state in ("mute", "silence")
    if CTX.dry:
        return CTX.log(f"  {'mute' if on else 'unmute'} the output like {name!r}")
    try:
        dev = best(name, devices(RENDER))
        if not dev:
            return ui.notify(f"No output like “{name}”")
        _device_volume(dev[0]).SetMute(1 if on else 0, None)
    except Exception as e:
        return ui.notify(f"Couldn't {state} it: {e}")
    ui.notify(f"{_short(dev[1])}: {'muted' if on else 'sound on'}")


def app_output(app, exes, name):
    """'spotify on the speakers': one app's sound to one device (Windows remembers it for that app).
    name 'default' puts it back. Uses an undocumented part of Windows: it may stop working
    after a big Windows update, and then says so."""
    reset = bool(re.fullmatch(r"(?:the )?(?:default|normal|usual)(?: output| device| one)?", name))
    if CTX.dry:
        return CTX.log(f"  {app}'s sound -> {'the default output' if reset else f'the output like {name!r}'}")
    import psutil
    try:
        dev = None if reset else best(name, devices(RENDER))
        if not reset and not dev:
            return ui.notify(f"No output like “{name}”")
        pids = {s.ProcessId for s in _sessions(exes)}
        pids |= {p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() in exes}
        if not pids:
            return ui.notify(f"Open {app.capitalize()} first, then say it again")
        set_app_output(sorted(pids), dev[0] if dev else None)
    except Exception as e:
        return ui.notify(f"Couldn't move {app}'s sound: {e}. Per-app output uses a part of Windows that "
                         "changes between versions; Settings → Sound → Volume mixer does the same by hand.")
    ui.notify(f"{app.capitalize()} → {'the default output' if reset else _short(dev[1])}")
