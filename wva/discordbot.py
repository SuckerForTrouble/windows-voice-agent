"""Music bot commands in a Discord channel: "bot play blinding lights" sends "m!play blinding
lights" (Jockie Music's prefix; Settings → Your apps changes it) to the bot channel.

Two ways it gets there:
  in the background  with the VoiceAgentBridge plugin in Vesktop (vesktop-plugin/): the
                     plugin sends it as you while you stay in your game or app
  the quick flick    otherwise: Discord comes to the front for a moment, it's typed into the
                     channel that's open there, and you're back where you were

The commands are typed by you (your account), not a bot, so Jockie (which ignores bots)
answers them like anything you type."""
import json
import re
import time
import urllib.request

from . import config, paths, ui
from .actions import CTX, keys, log, type_text

# What each spoken command sends after the prefix ("{}" is what you said: the song, the volume).
# Jockie Music's names; another bot's can go in config.json as "bot_commands".
COMMANDS = {
    "play": "play {}", "skip": "skip", "pause": "pause", "resume": "resume", "stop": "leave", "queue": "queue",
    "now": "nowplaying", "previous": "previous", "shuffle": "shuffle", "loop song": "repeat current",
    "loop queue": "repeat queue", "loop off": "repeat disable", "volume": "volume {}", "lyrics": "lyrics",
    "join": "join", "autoplay": "autoplay", "remove": "remove {}", "skip to": "skip to {}",
}
_told = {"flick": False}


def command(what, arg=""):
    """'play', 'blinding lights' -> 'm!play blinding lights'."""
    table = {**COMMANDS, **(config.get("bot_commands") or {})}
    tpl = table.get(what, what)
    body = tpl.format(arg.strip()) if "{}" in tpl else tpl
    return (config.get("bot_prefix") or "m!") + body.strip()


def _bridge():
    """The plugin's address and secret ({port, token}), when Vesktop with the plugin is running."""
    try:
        return json.loads((paths.DATA / "discord-bridge.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def through_plugin(channel, text):
    """Hand it to the Vesktop plugin: True if it took it (it sends straight away)."""
    b = _bridge()
    if not b or not b.get("port") or not b.get("token"):
        return False
    req = urllib.request.Request(f"http://127.0.0.1:{int(b['port'])}/send",
                                 json.dumps({"channel": channel, "text": text}).encode(),
                                 {"Content-Type": "application/json", "X-Token": str(b["token"])})
    try:
        with urllib.request.urlopen(req, timeout=1.5) as r:
            return r.status in (200, 202)
    except Exception:
        return False


def by_flick(text):
    """Discord to the front, type it into the open channel, Enter, back to where you were."""
    from .extras import send_to_app

    def typed():
        if not CTX.dry:
            time.sleep(0.15)
        keys("escape")       # out of any search or popup, into the message box
        type_text(text)
        if not CTX.dry:
            time.sleep(0.15)
        keys("enter")
    return send_to_app("discord", None, "Discord", back=True, then=typed)


def send(text):
    channel = re.sub(r"\D", "", str(config.get("bot_channel") or ""))
    if CTX.dry:
        return log(f"to Discord channel {channel or '(the open one)'}: {text!r} "
                   "(the Vesktop plugin in the background, else a flick to Discord)")
    if channel and through_plugin(channel, text):
        return ui.notify(f"Sent “{text}”") if config.get("bot_confirm") else None
    if by_flick(text) and not _told["flick"]:
        _told["flick"] = True
        ui.notify(f"Sent “{text}” in the Discord channel that was open. With the Vesktop plugin it goes to "
                  "the bot channel in the background (see the README)")


def bot(what, arg=""):
    send(command(what, arg))


def volume_ok(n):
    from .engine import num
    v = num(n)
    return v is not None and 0 <= v <= 200
