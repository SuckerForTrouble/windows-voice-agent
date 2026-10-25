"""Updates from GitHub Releases. A release carries WindowsVoiceAgent-Setup.exe; the
agent downloads it, quits, and the installer runs silently and starts the new
version (settings, history, tuning and the speech model are kept)."""
import json
import logging
import os
import re
import subprocess
import tempfile
import urllib.request

from . import REPO, __version__, paths

log = logging.getLogger("wva.update")
API = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET = "WindowsVoiceAgent-Setup.exe"


def _v(s):
    return tuple(int(x) for x in re.findall(r"\d+", s or "")[:3]) or (0,)


def newer(a, b):
    return _v(a) > _v(b)


def _latest():
    req = urllib.request.Request(API, headers={"User-Agent": "WindowsVoiceAgent", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def latest_version():
    try:
        return _latest().get("tag_name", "").lstrip("v")
    except Exception:
        return None


def check(notify, before_install=None, progress=None):
    """-> 'none' | 'updating' | 'error: …' | 'source' (running from a checkout: nothing to install).
    progress(percent) is called every 10% of the download."""
    try:
        rel = _latest()
    except Exception as e:
        return f"error: {e}"
    tag = rel.get("tag_name", "").lstrip("v")
    if not newer(tag, __version__):
        return "none"
    asset = next((x for x in rel.get("assets", []) if x.get("name") == ASSET), None)
    if not asset:
        return "error: the release has no installer yet"
    if not paths.FROZEN:
        notify(f"Version {tag} is out (running from source: git pull to update)")
        return "source"
    notify(f"Updating to {tag}: downloading…")
    dest = os.path.join(tempfile.gettempdir(), f"WindowsVoiceAgent-Setup-{tag}.exe")
    try:
        req = urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": "WindowsVoiceAgent"})
        size, done, shown = asset.get("size") or 0, 0, 0
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress and size and done * 100 // size >= shown + 10:
                    shown = done * 100 // size // 10 * 10
                    progress(min(shown, 100))
        if size and os.path.getsize(dest) != size:
            return f"error: the download stopped early ({os.path.getsize(dest)} of {size} bytes)"
    except Exception as e:
        return f"error: download failed: {e}"
    notify(f"Installing {tag}: back in a few seconds")
    if before_install:
        before_install()
    # Wait until this process is gone, then install silently; the installer starts the new version.
    # (ping is the wait: `timeout` refuses to run without a console.)
    cmd = f'ping -n 4 127.0.0.1 >nul & "{dest}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-'
    try:  # out of any job we might be in, so it outlives us
        subprocess.Popen(["cmd", "/c", cmd], creationflags=0x08000000 | 0x01000000, close_fds=True)
    except OSError:
        subprocess.Popen(["cmd", "/c", cmd], creationflags=0x08000000, close_fds=True)
    log.info("installer started for %s", tag)
    os._exit(0)
