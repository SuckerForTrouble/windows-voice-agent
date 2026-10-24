"""Settings in %LOCALAPPDATA%\\WindowsVoiceAgent\\config.json. Missing keys get the
defaults below, so an update can add settings without touching anyone's file.
The defaults are the light setup; every extra is opt-in from the tray."""
import json

from . import paths

DEFAULTS = {
    # Hold the key and talk, let go to run it. A quick tap toggles instead (tap, talk, tap).
    "agent_key": "f9",       # commands
    "dictate_key": "f10",    # types what you say into the focused app ("computer …" still runs commands)
    "model": "large-v3-turbo-q5_0",  # tray → Speech model: base.en-q5_1 | small.en-q5_1 | large-v3-turbo-q5_0 | groq | openai
    "backend": "auto",       # auto (GPU via Vulkan, CPU if that fails) | vulkan | cpu
    "language": "en",        # what commands are spoken in (they're English phrases)
    "dictate_language": "en",  # what the typing key types: en | hi (Hindi) | auto
    "cloud_keys": {},        # API keys for the cloud models, encrypted for this Windows user
    "mic": "",               # part of the microphone's name; empty = the Windows default mic
    "sounds": True,          # start/stop beeps
    "osd": True,             # the little "heard: …" pill at the top of the screen
    "osd_style": "minimal",  # minimal | advanced | funky (tray → Optional features → Pill style)
    "voice_replies": False,  # answers (time, weather…) read out loud as well as shown (opt-in)
    "show_timing": False,    # the pill says how long each command took (opt-in)
    "unload_in_games": True,  # a game starts: the speech model leaves graphics memory until you press the key
    "auto_update": True,
    "start_with_windows": True,
    "weather_place": "",     # empty = found by IP, or e.g. "Ludhiana"
    # Discord's own shortcuts only work while Discord is focused, so by default the agent
    # flicks to Discord and back. In a game that alt-tabs you out: set these in Discord
    # (Settings > Keybinds) and turn on "discord_keybinds" (tray menu) to send them blind.
    "discord_keybinds": False,
    "discord_mute_keys": "ctrl+shift+alt+m",
    "discord_deafen_keys": "ctrl+shift+alt+d",
    "clips": "nvidia",       # "clip that" = NVIDIA Instant Replay (Alt+F10) | "xbox" (Win+Alt+G)
    "doomscroll_seconds": 8,
}

_cache = None


def load():
    global _cache
    data = {}
    try:
        data = json.loads(paths.CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    _cache = {**DEFAULTS, **{k: v for k, v in data.items() if k in DEFAULTS}}
    return _cache


def get(key):
    if _cache is None:
        load()
    return _cache.get(key, DEFAULTS.get(key))


def set(key, value):  # noqa: A001 - mirrors get()
    if _cache is None:
        load()
    _cache[key] = value
    save()


def save():
    """Only what differs from the defaults is written, so a changed default reaches
    everyone who never touched that setting."""
    paths.ensure()
    changed = {k: v for k, v in _cache.items() if DEFAULTS.get(k) != v}
    paths.CONFIG.write_text(json.dumps(changed, indent=2), encoding="utf-8")
