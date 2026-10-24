"""What the running app knows about itself, for the setup check and the tray."""
stt = None          # stt.Whisper once started
hotkeys = {}        # "agent" / "dictate" -> True if Windows gave us the key
mic = ""            # the microphone in use
status = "Starting…"
usage = {}          # the loaded model's measured {"ram": MB, "vram": MB}
timings = []        # recent commands: {"stt": s, "total": s, "audio": s}
gaming = ""         # the game running, while the model is unloaded for it
listening = False   # always listening is on and the mic is open
