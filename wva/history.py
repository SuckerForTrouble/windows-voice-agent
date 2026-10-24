"""Every agent-key utterance and what came of it, one JSON line each, kept only on
this PC (%LOCALAPPDATA%\\WindowsVoiceAgent\\history.jsonl, trimmed past 2 MB).
Dictation (the typing key) is never written. It feeds the voice guide's
"recent" list and the tune-me.txt export for an AI."""
import json
from datetime import datetime

from . import paths
from .engine import CTX


def record(**entry):
    if CTX.dry:
        return
    entry = {"t": datetime.now().isoformat(timespec="seconds"), **entry}
    try:
        paths.ensure()
        with open(paths.HISTORY, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        if paths.HISTORY.stat().st_size > 2_000_000:
            lines = paths.HISTORY.read_text(encoding="utf-8").splitlines(keepends=True)
            paths.HISTORY.write_text("".join(lines[len(lines) // 2:]), encoding="utf-8")
    except OSError:
        pass


def rows(days=30):
    since = datetime.now().timestamp() - days * 86400
    out = []
    try:
        for line in paths.HISTORY.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
                if datetime.fromisoformat(e["t"]).timestamp() >= since:
                    out.append(e)
            except (ValueError, KeyError):
                continue
    except OSError:
        pass
    return out


def clear():
    try:
        paths.HISTORY.unlink()
    except OSError:
        pass
