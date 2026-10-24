"""What the speech model costs on this PC (measured, for the tray and the setup
check) and whether a game is running (to free its graphics memory)."""
import logging
import subprocess

from . import state

log = logging.getLogger("wva.usage")


def measure(pid):
    """{'ram': MB, 'vram': MB or None} of one process. RAM from Windows directly;
    graphics memory from the GPU performance counters (a second or so: run it off
    the UI thread)."""
    out = {"ram": None, "vram": None}
    try:
        import psutil
        out["ram"] = psutil.Process(pid).memory_info().rss // 1_000_000
    except Exception:
        pass
    try:
        ps = (f'$s = (Get-Counter "\\GPU Process Memory(pid_{pid}_*)\\Dedicated Usage" -ErrorAction Stop).CounterSamples;'
              ' [int](($s | Measure-Object CookedValue -Sum).Sum / 1MB)')
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                           capture_output=True, text=True, timeout=15, creationflags=0x08000000)
        v = int((r.stdout or "").strip().splitlines()[-1])
        out["vram"] = v if v > 0 else None
    except Exception as e:  # counters missing, or named differently on a non-English Windows
        log.info("no VRAM counter: %s", e)
    return out


def refresh(stt):
    """Measure the running model once it's loaded; the tray shows the result."""
    proc = getattr(stt, "proc", None)
    state.usage = measure(proc.pid) if proc and proc.poll() is None else {}


def game_running():
    """Name of a running game (from a Steam / Epic library folder, or a known one), else ''."""
    from .actions import _game_procs
    try:
        procs = _game_procs()
    except Exception:
        return ""
    for p in procs:
        try:
            return p.name().removesuffix(".exe")
        except Exception:
            continue
    return ""
