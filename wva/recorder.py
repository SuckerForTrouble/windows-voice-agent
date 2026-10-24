"""The microphone, opened only while a key is held (so Windows' "mic in use" icon
shows only while you talk). 16 kHz mono, which is what whisper wants."""
import array
import threading
import time

RATE = 16000
MAX_SECONDS = 30


def input_devices():
    import sounddevice as sd
    seen, out = set(), []
    for d in sd.query_devices():
        if d["max_input_channels"] > 0 and d["name"] not in seen and "mapper" not in d["name"].lower():
            seen.add(d["name"])
            out.append(d["name"])
    return out


class Recorder:
    def __init__(self):
        self.stream = None
        self.frames = []
        self.started = 0.0
        self.level = 0.0  # 0-1, the last 0.1 s of sound
        self.lock = threading.Lock()

    def start(self, mic=""):
        import sounddevice as sd
        dev = None
        if mic:
            for i, d in enumerate(sd.query_devices()):
                if d["max_input_channels"] > 0 and mic.lower() in d["name"].lower():
                    dev = i
                    break
        self.frames = []
        self.started = time.time()

        def cb(data, n, t, status):
            chunk = bytes(data)
            a = array.array("h", chunk)
            self.level = min(1.0, max((abs(v) for v in a[::8]), default=0) / 12000)  # for the pill's meter
            with self.lock:
                if time.time() - self.started < MAX_SECONDS:
                    self.frames.append(chunk)
        self.stream = sd.RawInputStream(samplerate=RATE, channels=1, dtype="int16", device=dev, callback=cb, blocksize=1600)
        self.stream.start()

    def stop(self):
        """-> (pcm bytes, seconds, peak level 0-32767)"""
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        self.level = 0.0
        with self.lock:
            pcm = b"".join(self.frames)
        a = array.array("h", pcm)
        peak = max((abs(v) for v in a[::4]), default=0)
        return pcm, len(a) / RATE, peak

    @property
    def active(self):
        return self.stream is not None
