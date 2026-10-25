"""Speech to text: whisper.cpp's whisper-server, kept running with the model loaded
(in GPU memory with the Vulkan build, so the agent itself stays small in RAM).
The Vulkan build is tried first; if the GPU can't run it, the CPU build takes over."""
import io
import json
import logging
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import wave

from . import config, paths

WINDOWS = sys.platform == "win32"

log = logging.getLogger("wva.stt")
WHISPER_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{}.bin"
PARAKEET_URL = "https://huggingface.co/ggml-org/parakeet-GGUF/resolve/main/ggml-{}.bin"
PARAKEET = "parakeet-tdt-0.6b-v3-q8_0"


def model_url(mid):
    return (PARAKEET_URL if mid.startswith("parakeet") else WHISPER_URL).format(mid)
# What the tray offers: id -> (label, MB to download, understands Hindi, about MB of memory
# while loaded, how fast it is on a CPU). The memory is graphics memory (VRAM) on the GPU,
# RAM on the CPU; on top of it whisper-server itself takes ~100 MB of RAM. Rough numbers:
# the tray shows the real ones for the model in use.
MODELS = {
    # NVIDIA's Parakeet (through whisper.cpp): a tenth of a second per command even on a CPU.
    # English and 24 European languages, no Hindi; no prompt, so names lean on the ALIASES.
    PARAKEET: ("Parakeet: fastest, English", 669, False, 700, "quick"),  # 671 MB RAM measured on a CPU
    "large-v3-turbo-q5_0": ("Best: most accurate, Hindi too", 550, True, 900, "slow"),
    "small.en-q5_1": ("Balanced: good on weaker GPUs", 190, False, 400, "ok"),
    "base.en-q5_1": ("Fast: least accurate", 60, False, 200, "quick"),
}
CLOUD = {  # OpenAI-style transcription APIs: id -> (label, endpoint, model)
    "groq": ("Cloud: Groq (needs an API key, sends your audio to Groq)",
             "https://api.groq.com/openai/v1/audio/transcriptions", "whisper-large-v3-turbo"),
    "openai": ("Cloud: OpenAI (needs an API key, sends your audio to OpenAI)",
               "https://api.openai.com/v1/audio/transcriptions", "whisper-1"),
}


def downloaded():
    """{model id: MB on disk} for every model file in the models folder."""
    out = {}
    for f in paths.MODELS.glob("ggml-*.bin"):
        out[f.name[5:-4]] = f.stat().st_size // 1_000_000
    return out


def delete_unused():
    """Delete every downloaded model except the one in use. Returns MB freed."""
    keep, freed = config.get("model"), 0
    for f in list(paths.MODELS.glob("ggml-*.bin")) + list(paths.MODELS.glob("*.part")):
        if f.name != f"ggml-{keep}.bin":
            try:
                size = f.stat().st_size
                f.unlink()
                freed += size
            except OSError:
                pass
    return freed // 1_000_000


def speed_test(engine):
    """Time the loaded model on the bundled sample sentence: (seconds, text) or None."""
    import time
    import wave
    try:
        with wave.open(str(paths.SAMPLE)) as w:
            pcm = w.readframes(w.getnframes())
    except OSError:
        return None
    t0 = time.time()
    text = engine.transcribe(pcm)
    return round(time.time() - t0, 2), text


def make(on_progress=None):
    """The speech engine the settings ask for: a cloud API, Parakeet, or whisper-server here."""
    m = config.get("model")
    if m in CLOUD:
        return Cloud(m, on_progress)
    return Parakeet(on_progress) if m.startswith("parakeet") else Whisper(on_progress)


def _wav(pcm, rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _multipart(fields, wav):
    boundary = uuid.uuid4().hex
    body = b"".join(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
                    for k, v in fields.items())
    body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.wav\"\r\n"
             f"Content-Type: audio/wav\r\n\r\n").encode() + wav + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


# Whisper always encodes a 30 s window, even for a 2 s command. Telling it the real length
# (audio_ctx, 50 per second) is ~3x faster, measured 2026-10-25 on 8 spoken commands:
# Fast 0.53 -> 0.19 s, Best (CPU) 10.9 -> 3.5 s. Under ~10 s of window it started dropping
# words ("Close Discord…" -> "close"), so that's the floor; Best then sometimes says a short
# command twice ("Next song. Next song."), which _tidy folds back into one.
TRIM_FLOOR = 512


def audio_ctx(seconds):
    if not config.get("whisper_trim") or seconds > 28:
        return 0
    return min(1500, max(TRIM_FLOOR, int((seconds + 1) * 50)))


def _collapse(text):
    """'Next song. Next song.' / 'Open YouTube, open YouTube,' / 'Open Spotify… Open Spotify… Open'
    -> said once: the first part repeated, maybe ending in a cut-off start of it again."""
    key = lambda p: re.sub(r"[^\w']+", " ", p).strip().lower()  # noqa: E731
    for sep in (r"(?<=[.?!])\s+", r",\s*"):
        parts = [p for p in re.split(sep, text.strip()) if p.strip()]
        if len(parts) > 1 and key(parts[1]) == key(parts[0]) and \
                all(key(p) == key(parts[0]) or key(parts[0]).startswith(key(p)) for p in parts[2:]):
            return parts[0].strip().rstrip(",")
    return text


def _tidy(text):
    text = _collapse(re.sub(r"\s+", " ", text or "").strip())
    if PROMPT.lower() in text.lower():  # whisper sometimes repeats its prompt on silence
        return ""
    return "" if JUNK.match(text) else text
# Names the recogniser should expect; whisper spells them right when it has seen them.
PROMPT = "Computer, open Spotify. Discord, Stremio, YouTube, Instagram, Steam, Chrome. Next tab, volume up."
# What whisper "hears" in silence or noise.
JUNK = re.compile(r"^\W*(?:\[[^\]]*\]|\([^)]*\)|thank you\.?|thanks for watching!?|you|bye\.?|\.+|"
                  r"subtitles by.*|please subscribe.*)\W*$", re.I)


class Whisper:
    def __init__(self, on_progress=None):
        self.model = config.get("model")
        self.backend = None      # "vulkan" | "cpu"
        self.device = ""         # the GPU name from whisper's log
        self.ready = False
        self.error = ""
        self.progress = ""
        self.port = None
        self.proc = None
        self._job = None
        self._log = None
        self.on_progress = on_progress or (lambda msg: None)

    # ------------------------------------------------------------- model
    @property
    def model_path(self):
        return paths.MODELS / f"ggml-{self.model}.bin"

    def ensure_model(self):
        p = self.model_path
        if p.exists() and p.stat().st_size > 30_000_000:
            return True
        paths.ensure()
        part = p.with_suffix(".part")
        for attempt in range(3):
            try:
                req = urllib.request.Request(model_url(self.model), headers={"User-Agent": "WindowsVoiceAgent"})
                with urllib.request.urlopen(req, timeout=30) as r, open(part, "wb") as f:
                    total = int(r.headers.get("Content-Length") or 0)
                    got, last = 0, -1
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                        got += len(chunk)
                        pct = int(got * 100 / total) if total else 0
                        if pct != last:
                            last = pct
                            self.progress = f"Downloading the speech model: {pct}% of {total // 1_000_000} MB"
                            self.on_progress(self.progress)
                if total and got < total:
                    raise OSError(f"download stopped at {got} of {total} bytes")
                os.replace(part, p)
                return True
            except Exception as e:
                log.warning("model download failed (%s): %s", attempt + 1, e)
                self.progress = f"Download failed, retrying ({e})"
                self.on_progress(self.progress)
                time.sleep(3 * (attempt + 1))
        self.error = "Couldn't download the speech model. Check the internet connection and restart the app."
        return False

    # ------------------------------------------------------------- server
    def _exe(self, backend):
        return paths.WHISPER / backend / "whisper-server.exe"

    def start(self):
        paths.ensure()
        if not self.ensure_model():
            return False
        want = config.get("backend")
        order = {"vulkan": ["vulkan"], "cpu": ["cpu"]}.get(want, ["vulkan", "cpu"])
        for backend in order:
            if not self._exe(backend).exists():
                continue
            self.progress = "Loading the speech model" + (" on the GPU…" if backend == "vulkan" else " on the CPU…")
            self.on_progress(self.progress)
            if self._launch(backend):
                # the Vulkan build without a usable GPU quietly runs on the CPU
                self.backend = backend if backend != "vulkan" or self.device else "cpu"
                self.ready, self.progress = True, ""
                self._warm_up()
                self.on_progress("")
                return True
        self.error = self.error or "The speech model couldn't start (see logs/whisper.log)."
        return False

    def _launch(self, backend):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        self.port = s.getsockname()[1]
        s.close()
        threads = str(max(2, min(8, (os.cpu_count() or 4) // 2)))
        argv = [str(self._exe(backend)), "-m", str(self.model_path), "--host", "127.0.0.1", "--port", str(self.port),
                "-t", threads, "-l", config.get("language") or "en", "-nt"]
        logf = paths.LOGS / "whisper.log"
        self._log = open(logf, "w", encoding="utf-8", errors="replace")
        log.info("starting %s", argv)
        self.proc = subprocess.Popen(argv, stdout=self._log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                     cwd=str(self._exe(backend).parent), creationflags=0x08000000 if WINDOWS else 0)
        if WINDOWS:
            from . import win
            self._job = win.kill_with_me(self.proc)
        deadline = time.time() + 180  # a big model on a slow disk takes a while
        while time.time() < deadline:
            if self.proc.poll() is not None:
                log.warning("whisper-server (%s) exited with %s", backend, self.proc.returncode)
                return False
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.5):
                    pass
                self._read_device()
                if backend == "vulkan" and not self.device:
                    log.info("vulkan build found no GPU, it runs on the CPU")
                return True
            except OSError:
                time.sleep(0.4)
        self.stop()
        return False

    def _warm_up(self):
        """One throwaway run on near-silence: the GPU's first run is the slow one, so it
        happens now and not on your first command."""
        t0 = time.time()
        self.transcribe(b"\x01\x00" * 16000)
        log.info("warm-up took %.2fs", time.time() - t0)

    def _read_device(self):
        try:
            text = (paths.LOGS / "whisper.log").read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        m = re.search(r"ggml_vulkan: \d+ = (.+?) \(", text) or re.search(r"using (?:Vulkan|CUDA)\d* backend.*?: (.+)", text)
        self.device = m.group(1).strip() if m else ""

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
        self.ready = False

    # ------------------------------------------------------------- transcribe
    def transcribe(self, pcm, language=None):
        """16-bit mono 16 kHz PCM -> text ('' when nothing was said)."""
        if not self.ready:
            return ""
        fields = {"temperature": "0.0", "temperature_inc": "0.2", "response_format": "json",
                  "language": language or config.get("language") or "en", "prompt": PROMPT}
        ctx = audio_ctx(len(pcm) / 32000)
        if ctx:
            fields["audio_ctx"] = str(ctx)
        body, ctype = _multipart(fields, _wav(pcm))
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/inference", body, {"Content-Type": ctype})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                text = json.load(r).get("text", "")
        except Exception as e:
            log.warning("transcribe failed: %s", e)
            if self.proc and self.proc.poll() is not None:  # the server died: bring it back once
                threading.Thread(target=self.start, daemon=True).start()
            return ""
        return _tidy(text)


class Parakeet(Whisper):
    """NVIDIA's Parakeet through our parakeet-server (native/parakeet-server): the model
    stays loaded and audio goes over a pipe, no HTTP. Same GPU (Vulkan) / CPU fallback."""
    EXE = "parakeet-server"
    LOG = "parakeet.log"

    def _exe(self, backend):
        d = paths.WHISPER / backend
        return d / f"{self.EXE}.exe" if (d / f"{self.EXE}.exe").exists() or WINDOWS else d / self.EXE

    def _launch(self, backend):
        import queue
        threads = str(max(2, min(8, (os.cpu_count() or 4) // 2)))
        argv = [str(self._exe(backend)), "-m", str(self.model_path), "-t", threads, "-v"]
        if backend == "cpu":
            argv.append("-ng")
        self._log = open(paths.LOGS / self.LOG, "w", encoding="utf-8", errors="replace")
        log.info("starting %s", argv)
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._log,
                                     cwd=str(self._exe(backend).parent), creationflags=0x08000000 if WINDOWS else 0)
        if WINDOWS:
            from . import win
            self._job = win.kill_with_me(self.proc)
        self._lines = queue.Queue()
        self._lock = threading.Lock()

        def read(out, q):
            for line in out:
                q.put(line.decode("utf-8", "replace").rstrip("\r\n"))
            q.put(None)  # it exited
        threading.Thread(target=read, args=(self.proc.stdout, self._lines), daemon=True).start()
        try:
            first = self._lines.get(timeout=180)
        except queue.Empty:
            first = None
        if not first or not first.startswith("READY"):
            log.warning("parakeet-server (%s) didn't start: %r, exit %s", backend, first, self.proc.poll())
            self.stop()
            return False
        self._read_device()
        return True

    def _read_device(self):
        try:
            text = (paths.LOGS / self.LOG).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        m = re.search(r"ggml_vulkan: \d+ = (.+?) \(", text)
        self.device = m.group(1).strip() if m else ""

    def transcribe(self, pcm, language=None):
        import queue
        import struct
        if not self.ready or not self.proc or self.proc.poll() is not None:
            if self.proc and self.proc.poll() is not None and self.ready:  # it died: bring it back once
                self.ready = False
                threading.Thread(target=self.start, daemon=True).start()
            return ""
        with self._lock:
            try:
                self.proc.stdin.write(struct.pack("<I", len(pcm) // 2) + pcm)
                self.proc.stdin.flush()
                line = self._lines.get(timeout=30)
            except (OSError, queue.Empty) as e:
                log.warning("parakeet transcribe failed: %s", e)
                return ""
        if line is None:
            return ""
        _, _, text = line.partition("\t")
        return _tidy(text)

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.close()  # lets it exit by itself
                self.proc.wait(2)
            except Exception:
                self.proc.kill()
        self.ready = False


class Cloud:
    """Speech to text over the internet (opt-in): no model download, no GPU memory, but
    every recording goes to the provider. The API key is kept encrypted for this
    Windows user (DPAPI)."""

    def __init__(self, provider, on_progress=None):
        self.provider = provider
        self.model = provider
        self.backend = "cloud"
        self.device = CLOUD[provider][0].split(" (")[0].replace("Cloud: ", "")
        self.ready = False
        self.error = ""
        self.progress = ""
        self.on_progress = on_progress or (lambda msg: None)

    def start(self):
        if not api_key(self.provider):
            self.error = f"No {self.device} API key yet: tray → Speech model → Set cloud API key."
            return False
        self.ready, self.error = True, ""
        return True

    def stop(self):
        self.ready = False

    def transcribe(self, pcm, language=None):
        if not self.ready:
            return ""
        _, url, model = CLOUD[self.provider]
        fields = {"model": model, "response_format": "json", "temperature": "0", "prompt": PROMPT,
                  "language": language or config.get("language") or "en"}
        body, ctype = _multipart(fields, _wav(pcm))
        req = urllib.request.Request(url, body, {"Content-Type": ctype, "User-Agent": "WindowsVoiceAgent",
                                                 "Authorization": f"Bearer {api_key(self.provider)}"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return _tidy(json.load(r).get("text", ""))
        except urllib.error.HTTPError as e:
            msg = {401: "the API key was refused", 429: "too many requests / out of credit"}.get(e.code, f"HTTP {e.code}")
            log.warning("cloud transcribe failed: %s", msg)
            from . import ui
            ui.notify(f"{self.device}: {msg}")
        except Exception as e:
            log.warning("cloud transcribe failed: %s", e)
        return ""


def api_key(provider):
    from . import win
    enc = (config.get("cloud_keys") or {}).get(provider)
    if not enc:
        return ""
    try:
        import base64
        return win.unprotect(base64.b64decode(enc)).decode()
    except Exception:
        return ""


def set_api_key(provider, key):
    import base64

    from . import win
    keys = dict(config.get("cloud_keys") or {})
    keys[provider] = base64.b64encode(win.protect(key.strip().encode())).decode() if key.strip() else ""
    config.set("cloud_keys", keys)
