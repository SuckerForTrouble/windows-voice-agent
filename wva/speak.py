"""Spoken answers with the voice built into Windows (SAPI): no download, no extra RAM
worth mentioning. One thread owns the voice; a new answer cuts off the old one."""
import queue
import threading

from . import config

_q = queue.Queue()


def _loop():
    try:
        import comtypes
        import comtypes.client
        comtypes.CoInitialize()
        voice = comtypes.client.CreateObject("SAPI.SpVoice")
        voice.Rate = 1
    except Exception:
        return
    while True:
        text = _q.get()
        try:
            voice.Speak(text, 1 | 2)  # SVSFlagsAsync | SVSFPurgeBeforeSpeak
        except Exception:
            pass


_thread = None


def say(text):
    global _thread
    if not config.get("voice_replies") or not text:
        return
    if _thread is None:
        _thread = threading.Thread(target=_loop, daemon=True, name="voice")
        _thread.start()
    _q.put(text)
