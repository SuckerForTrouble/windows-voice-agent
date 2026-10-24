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
import threading
import time
import urllib.request
import uuid
import wave

from . import config, paths

log = logging.getLogger("wva.stt")
MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{}.bin"
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
                req = urllib.request.Request(MODEL_URL.format(self.model), headers={"User-Agent": "WindowsVoiceAgent"})
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
                                     cwd=str(self._exe(backend).parent), creationflags=0x08000000)
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
    def transcribe(self, pcm, rate=16000):
        """16-bit mono PCM -> text ('' when nothing was said)."""
        if not self.ready:
            return ""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(pcm)
        boundary = uuid.uuid4().hex
        fields = {"temperature": "0.0", "temperature_inc": "0.2", "response_format": "json",
                  "language": config.get("language") or "en", "prompt": PROMPT}
        body = b"".join(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
                        for k, v in fields.items())
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.wav\"\r\n"
                 f"Content-Type: audio/wav\r\n\r\n").encode() + buf.getvalue() + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/inference", body,
                                     {"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                text = json.load(r).get("text", "")
        except Exception as e:
            log.warning("transcribe failed: %s", e)
            if self.proc and self.proc.poll() is not None:  # the server died: bring it back once
                threading.Thread(target=self.start, daemon=True).start()
            return ""
        text = re.sub(r"\s+", " ", text).strip()
        if PROMPT.lower() in text.lower():  # whisper sometimes repeats its prompt on silence
            text = ""
        return "" if JUNK.match(text) else text
