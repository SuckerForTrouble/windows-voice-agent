"""Play / pause / next / what's playing through Windows' media controls (the same
thing the volume flyout shows). Spotify, browsers, Stremio and most players
report there. Without it (or when it fails) the media keys do the job."""
import asyncio
import threading

try:
    from winrt.windows.media.control import \
        GlobalSystemMediaTransportControlsSessionManager as _Manager
    AVAILABLE = True
except Exception:  # not Windows, or the winrt package is missing
    _Manager = None
    AVAILABLE = False

PLAYING, PAUSED = 4, 5
_paused_by_us = []  # source ids "pause" stopped, so "play" resumes exactly those
_lock = threading.Lock()


def _run(coro):
    return asyncio.run(coro)


async def _all():
    mgr = await _Manager.request_async()
    return mgr, list(mgr.get_sessions())


def _status(s):
    try:
        return int(s.get_playback_info().playback_status)
    except Exception:
        return 0


def sessions(app=None):
    """[(source_id, status)] — app: part of the source id, e.g. 'spotify'."""
    async def go():
        _, ss = await _all()
        return [(s.source_app_user_model_id, _status(s)) for s in ss
                if not app or app in s.source_app_user_model_id.lower()]
    return _run(go())


def control(action, app=None):
    """action: pause | play | toggle | next | previous | stop.
    pause: everything that plays (remembered); play: what we paused, else the current one.
    Returns a short description of what it acted on, or None if there was nothing."""
    async def go():
        mgr, ss = await _all()
        if app:
            ss = [s for s in ss if app in s.source_app_user_model_id.lower()]
        playing = [s for s in ss if _status(s) == PLAYING]
        current = mgr.get_current_session()
        if app and current and app not in current.source_app_user_model_id.lower():
            current = None
        if action == "pause":
            if not playing:
                return None
            with _lock:
                _paused_by_us[:] = [s.source_app_user_model_id for s in playing]
            for s in playing:
                await s.try_pause_async()
            return ", ".join(s.source_app_user_model_id for s in playing)
        if action == "play":
            with _lock:
                ids = list(_paused_by_us)
                _paused_by_us.clear()
            targets = [s for s in ss if s.source_app_user_model_id in ids and _status(s) == PAUSED]
            if not targets:
                paused = [s for s in ss if _status(s) == PAUSED]
                targets = ([current] if current and _status(current) == PAUSED else paused[:1])
            for s in targets:
                await s.try_play_async()
            return ", ".join(s.source_app_user_model_id for s in targets) or None
        target = playing[0] if playing else current or (ss[0] if ss else None)
        if not target:
            return None
        fn = {"next": target.try_skip_next_async, "previous": target.try_skip_previous_async,
              "stop": target.try_stop_async, "toggle": target.try_toggle_play_pause_async}[action]
        await fn()
        return target.source_app_user_model_id
    return _run(go())


def seek(delta=None, absolute=None, app=None):
    """Move the playhead by delta seconds (or to absolute seconds). True if the player took it."""
    async def go():
        mgr, ss = await _all()
        if app:
            ss = [s for s in ss if app in s.source_app_user_model_id.lower()]
        playing = [s for s in ss if _status(s) == PLAYING]
        s = playing[0] if playing else mgr.get_current_session()
        if not s:
            return False
        pos = s.get_timeline_properties().position.total_seconds()
        new = absolute if absolute is not None else max(0.0, pos + delta)
        return bool(await s.try_change_playback_position_async(int(new * 10_000_000)))
    return _run(go())


def now_playing(app=None):
    """(title, artist, source, playing) or None."""
    async def go():
        mgr, ss = await _all()
        if app:
            ss = [s for s in ss if app in s.source_app_user_model_id.lower()]
        order = sorted(ss, key=lambda s: _status(s) != PLAYING)
        cur = mgr.get_current_session()
        cur_id = cur.source_app_user_model_id if cur else None
        if cur_id and not any(_status(s) == PLAYING for s in ss):  # nothing plays: the one Windows shows first
            order.sort(key=lambda s: s.source_app_user_model_id != cur_id)
        for s in order:
            p = await s.try_get_media_properties_async()
            if p and p.title:
                return p.title, p.artist or "", s.source_app_user_model_id, _status(s) == PLAYING
        return None
    return _run(go())
