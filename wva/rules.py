"""Every command: the group it shows under in the voice guide, how it is said
(several ways each), and what it does. First match wins, so app-specific rules
come before the general ones ("mute discord" is Discord's mic, "mute" the speakers)."""
import re

from . import actions as a
from . import extras as x
from . import system as s
from .engine import num, parse_duration, rule

R, YT, DC, SP, ST, G, C = ("Reels & Shorts", "YouTube", "Discord", "Spotify", "Stremio & watching", "Gaming",
                          "Close & switch apps")
H, B, K, W, S, AU, SY, I, T, A = ("Voice agent", "Browser", "Keyboard", "Windows", "Sound & media", "App volume",
                                  "System", "Info", "Timers", "Open & search")
THE = r"(?:the |this |that |my |a |an )?"
DIRECTIONS = ("left", "right", "up", "down")


def _later(name, *args):
    """Late-bound call into a module that would import us back (guide, tuning, the app)."""
    def fn(*more):
        import importlib
        mod, _, attr = name.rpartition(".")
        return getattr(importlib.import_module(f"wva.{mod}"), attr)(*args, *more)
    return fn


def _ui(handler):
    def fn():
        from . import ui
        h = ui.handlers.get(handler)
        if a.CTX.dry:
            return a.log(handler)
        if h:
            h()
    return fn


# Reels & Shorts (only while Instagram / YouTube is in front) ---------------------------
rule(R, "stop scrolling", "Stops the doom scroll",
     [r"(?:stop|enough|pause|halt)(?: (?:scrolling|it|that|the scroll(?:ing)?|doom ?scrolling))?", r"stop (?:the )?doom ?scroll(?:ing)?"],
     x.stop_scroll, guard=x.scrolling)
rule(R, "scroll instagram", "Opens Instagram reels and moves to the next one every few seconds",
     [r"(?:scroll|doom ?scroll|auto ?scroll) (?:on |through |the )?(?:instagram|reels|instagram reels|insta)(?: reels)?(?: every (\w+) seconds?)?",
      r"(?:open|start|watch) (?:instagram )?reels and (?:keep )?scroll(?:ing)?"],
     lambda secs=None: x.scroll_instagram(secs), wake=True)
rule(R, "doom scroll [every <n> seconds]", "With reels or Shorts in front: next one every 8 s until you say 'stop'",
     [r"(?:doom ?scroll|auto ?scroll|keep scrolling|start scrolling|scroll for me)(?: every (\w+) seconds?)?"],
     lambda secs=None: x.doomscroll(secs) if x.shorts_front() else x.scroll_instagram(secs), wake=True,
     guard=lambda secs=None: secs is None or num(secs) is not None)
rule(R, "next | previous reel / short", "Instagram reels or YouTube Shorts in front",
     [r"(next|previous|last) (?:reel|short|shorts|insta video)", r"(?:go |scroll )?(back|up) (?:a |one )?(?:reel|short)",
      r"(?:skip|scroll past) (?:this|the) (?:reel|short)"],
     lambda d="next": x.reel("previous" if d in ("previous", "last", "back", "up") else "next"), guard=lambda d="next": x.shorts_front())
rule(R, "next | back (Instagram in front)", "One word is enough while Instagram is in front",
     [r"(next|skip|previous|back|down|up)(?: one)?"],
     lambda d: x.reel("previous" if d in ("previous", "back", "up") else "next"), guard=lambda d: x.reels_front())
rule(R, "like (Instagram in front)", "Double-taps the reel",
     [r"(?:like|heart|double tap|love)(?: (?:this|it|that|the reel|this reel|the post|this post|the video))?"],
     x.reel_like, guard=x.reels_front)

# YouTube (the video in front) --------------------------------------------------------
rule(YT, "fullscreen the video", "F on YouTube (not the whole browser)",
     [r"(?:make (?:it |the video )?|go )?fullscreen(?: (?:the |this )?video| it| this)?", r"(?:exit|leave) fullscreen"],
     lambda: x.youtube("fullscreen"), guard=x.youtube_front)
rule(YT, "theater mode", "T on YouTube", [r"theat(?:er|re) mode", r"(?:toggle )?cinema mode", r"(?:make (?:the )?video )?wider"],
     lambda: x.youtube("theater"), guard=x.youtube_front)
rule(YT, "captions on | off", "C on YouTube",
     [r"(?:turn (?:on|off) |toggle |show |hide |enable |disable )?(?:the )?(?:captions|subtitles|subs|cc|closed captions)(?: on| off)?"],
     lambda: x.youtube("captions"), guard=x.youtube_front)
rule(YT, "speed up | slow down", "Playback speed on YouTube",
     [r"(speed (?:it |this |the video )?up|faster|play faster|increase (?:the )?speed)",
      r"(slow (?:it |this |the video )?down|slower|play slower|decrease (?:the )?speed)"],
     lambda w: x.youtube("faster" if "up" in w or "fast" in w or "increase" in w else "slower"), guard=lambda w: x.youtube_front())
rule(YT, "next | previous video", "Shift+N / Shift+P on YouTube",
     [r"(next|previous) video", r"skip (?:to the )?(next) video", r"play (?:the )?(next) video"],
     lambda d: x.youtube(d), guard=lambda d: x.youtube_front())
rule(YT, "mute the video", "M on YouTube", [r"(?:mute|unmute) (?:the |this )?video"], lambda: x.youtube("mute"), guard=x.youtube_front)
rule(YT, "mini player", "I on YouTube", [r"mini ?player(?: mode)?", r"(?:open|toggle) (?:the )?mini ?player"],
     lambda: x.youtube("miniplayer"), guard=x.youtube_front)

# Discord -----------------------------------------------------------------------------
rule(DC, "mute | unmute Discord sound", "Discord's sound only (not your mic)",
     [r"(mute|unmute|silence) (?:the )?discord (?:audio|sound|volume|voices|call sound)"],
     lambda st: a.app_mute(st, "discord"))
rule(DC, "mute me on Discord", "Your Discord mic on/off (Ctrl+Shift+M)",
     [r"(?:mute|unmute) (?:me|myself|my mic(?:rophone)?) (?:on|in) discord", r"discord (?:mute|unmute)(?: me| myself| my mic)?",
      r"(?:mute|unmute) discord(?: mic| microphone)?", r"(?:mute|unmute) (?:me|myself)", r"toggle (?:discord )?mute"],
     x.discord_mute)
rule(DC, "deafen | undeafen", "Discord deafen (Ctrl+Shift+D)",
     [r"(?:deafen|undeafen)(?: me| myself)?(?: (?:on|in) discord)?", r"discord (?:deafen|undeafen)", r"(?:deafen|undeafen) discord"],
     x.discord_deafen)
rule(DC, "answer the Discord call", "Ctrl+Enter in Discord",
     [r"(?:answer|accept|pick up|join) (?:the )?(?:discord )?call(?: on discord)?", r"(?:answer|pick up|accept) discord"],
     x.discord_answer)
rule(DC, "decline the Discord call", "Esc in Discord",
     [r"(?:decline|reject|ignore|dismiss) (?:the )?(?:discord )?call(?: on discord)?"], x.discord_decline)
rule(DC, "go to <server | channel | friend> on Discord", "Discord's quick switcher (Ctrl+K)",
     [r"(?:go to|open|switch to|jump to|show(?: me)?|find) (.+?) (?:on|in) discord",
      r"discord (?:go to|open|switch to|jump to|find) (.+)", r"(?:message|dm|text) (.+?) on discord"],
     x.discord_goto, wake=True, free=True)

# Spotify -----------------------------------------------------------------------------
rule(SP, "play <song | artist> on Spotify", "Opens Spotify's search for it (click the top result)",
     [r"(?:play|search(?: for)?|find|look for|put on|listen to) (.+?) (?:on|in) spotify",
      r"spotify (?:play|search(?: for)?|find) (.+)", r"search spotify for (.+)"],
     x.spotify_search, wake=True, free=True)
rule(SP, "pause | play | next on Spotify", "Spotify only, even when something else plays too",
     [r"(pause|play|resume|stop|next|previous|skip|continue)(?: the)?(?: song| track| music)?(?: on| in)? spotify",
      r"spotify (pause|play|resume|next|previous|skip|stop)", r"(?:play )?(?:the )?(next|previous) (?:song|track) on spotify"],
     lambda act: a.media({"stop": "pause", "continue": "play"}.get(act, act), app="spotify"))
rule(SP, "like this song", "Adds it to your Liked Songs (Alt+Shift+B)",
     [r"(?:like|save|heart|love) (?:this |the |that |current )?(?:song|track)(?: on spotify)?",
      r"add (?:this |the |that )?(?:song|track) to (?:my )?liked songs", r"(?:like|save) (?:it|this) on spotify"],
     x.spotify_like)
rule(SP, "shuffle", "Spotify shuffle on/off (Alt+S)",
     [r"(?:toggle |turn (?:on|off) |enable |disable )?shuffle(?: mode)?(?: on| off)?(?: (?:on|in) spotify)?",
      r"spotify shuffle(?: on| off)?", r"shuffle (?:my |the )?(?:songs|music|playlist)"], x.spotify_shuffle)
rule(SP, "repeat", "Spotify repeat (Alt+R)",
     [r"(?:toggle |turn (?:on|off) |enable |disable )?repeat(?: mode)?(?: on| off)?(?: (?:on|in) spotify)?",
      r"(?:put|play) (?:this|it|the song) on repeat", r"repeat (?:this|the) song"], x.spotify_repeat)
rule(SP, "open my liked songs | library | playlists", "Spotify pages",
     [r"(?:open|show|play|go to|show me) (?:my )?(liked) songs(?: on spotify)?",
      r"(?:open|show|go to|show me) (?:my )?(?:spotify )?(library|playlists|podcasts)(?: on spotify)?"],
     x.spotify_open)
rule(SP, "what's playing on Spotify", "Song and artist from Spotify",
     [r"what(?:'s| is) playing on spotify", r"what song is (?:this|playing) on spotify"], lambda: a.now_playing("spotify"))

# Stremio & watching ------------------------------------------------------------------
rule(ST, "watch <movie | show> on Netflix | Prime", "Search there",
     [r"(?:watch|stream|find|search(?: for)?|look up|play) (.+?) on (netflix|prime video|amazon prime|prime|twitch)"],
     lambda q, svc: a.web(q, {"prime": "prime video", "amazon prime": "prime video"}.get(svc, svc)), wake=True, free=True)
rule(ST, "watch <movie | show> on Stremio", "Opens its page in Stremio with the streams: 'watch interstellar', "
     "'stremio breaking bad season 2 episode 3'",
     [r"(?:watch|stream|play|find|search(?: for)?|look up|open|put on) (.+?) (?:on|in) stremio",
      r"stremio (?:play |watch |search(?: for)? |find |open |look up )?(.+)",
      r"(?:watch|stream) (?:the )?(?:movie |film |show |series )?(.+)"],
     x.stremio_find, wake=True, free=True, guard=lambda q: not re.fullmatch(r"(?:it|this|that|something|a movie|a show)", q))

# Gaming ------------------------------------------------------------------------------
rule(G, "clip that", "Saves the last moments: NVIDIA Instant Replay (Alt+F10) or Xbox Game Bar",
     [r"(?:clip|save|record) (?:that|this|it)", r"clip it", r"(?:take a )?clip",
      r"(?:save|clip) (?:the )?(?:replay|instant replay|last (?:\w+ )?(?:seconds|minutes))"],
     lambda: x.game_capture("clip"))
rule(G, "start | stop recording", "NVIDIA (Alt+F9) or Xbox Game Bar recording",
     [r"(?:start|stop|toggle|end) (?:the )?recording", r"(?:start|stop) record(?:ing)? (?:the )?(?:game|screen|gameplay)",
      r"record (?:the )?(?:game|screen|gameplay)"], lambda: x.game_capture("record"))
rule(G, "game screenshot", "NVIDIA (Alt+F1) or Xbox Game Bar screenshot",
     [r"(?:take )?(?:a )?(?:game|in game) screenshot", r"screenshot (?:the |this )?game"], lambda: x.game_capture("screenshot"))
rule(G, "show fps", "NVIDIA performance overlay (Alt+R)",
     [r"(?:show|hide|toggle|turn on|turn off) (?:the |my )?(?:fps|frame ?rate|frames|performance overlay|stats overlay)",
      r"(?:fps|frame ?rate) (?:counter|overlay)"], lambda: x.game_capture("fps"))
rule(G, "nvidia overlay | game bar", "Alt+Z / Win+G",
     [r"(?:open |show )?(?:the )?(nvidia|geforce) overlay", r"(?:open |show )?(?:the )?(?:xbox )?(game bar)"],
     lambda which: x.game_capture("overlay") if which in ("nvidia", "geforce") else a.keys("win+g"))

# Close & switch apps -----------------------------------------------------------------
rule(C, "close the game", "The game you're playing (it gets 4 s to close by itself)",
     [r"(?:close|quit|exit|kill|end|stop) (?:the |this |my )?game", r"(?:force )?(?:close|quit) (?:the )?game (?:now|completely)"],
     lambda: a.close_game(), wake="strict")
rule(C, "quit <app> completely", "Closes it from the tray too: 'quit discord', 'close spotify from the tray', 'kill steam'",
     [r"(?:quit|exit|kill|end|force (?:close|quit)|terminate) " + THE + r"(.+?)(?: app| completely| fully| for good| from the tray| in the tray| entirely)?",
      r"close " + THE + r"(.+?) (?:completely|fully|from the tray|in the tray|for good|entirely|from the background)",
      r"(?:close|shut down|turn off) " + THE + r"(.+?) (?:in|from) the background"],
     a.quit_app, wake="strict", guard=lambda n: a.app_known(n))
rule(C, "close everything", "A polite close to every app window (unsaved work still asks)",
     [r"close (?:everything|all (?:the )?(?:apps|windows|programs)|all of it)", r"close all"], a.close_everything, wake="strict")
rule(C, "close <app>", "Its windows, even behind others; if it's only in the tray it is quit. "
     "A browser tab by name works too: 'close youtube'",
     [r"close " + THE + r"(.+?)(?: app| window| windows)?", r"(?:shut|turn off) " + THE + r"(.+?)(?: app)?"],
     a.close_app, guard=lambda n: n not in a.WINDOW_WORDS and a.app_known(n))
rule(C, "minimize everything else", "Only the window in front stays",
     [r"minimi[sz]e (?:everything|all(?: the)?(?: other)?(?: windows| apps)?) (?:else|except (?:this|this one|this window|the one in front))",
      r"minimi[sz]e (?:the )?other windows"], a.minimize_others)
rule(C, "minimize <app>", "Every window of that app",
     [r"(?:minimi[sz]e|hide) " + THE + r"(.+?)(?: app| window| windows)?"], a.minimize_app,
     guard=lambda n: n not in a.WINDOW_WORDS + ("everything",) and a.app_known(n))
rule(C, "switch to <app>", "Brings it to the front (opens it if it isn't running)",
     [r"(?:switch to|focus(?: on)?|show me|bring back|bring up|go back to|jump to|take me to|show) " + THE + r"(.+?)(?: app| window)?"],
     a.focus_app, guard=lambda n: n not in DIRECTIONS and n not in a.WINDOW_WORDS and (a.app_known(n) or a.can_open(n)),
     after=0.6)
rule(C, "what's open", "Lists the open apps",
     [r"what(?:'s| is| apps are| windows are) (?:open|running)", r"(?:list|show) (?:the )?(?:open|running) (?:apps|windows|programs)",
      r"which apps are (?:open|running)"], a.list_open, wake=True)

# Voice agent -------------------------------------------------------------------------
rule(H, "help | what can I say", "Opens the voice guide (every command, with examples)",
     [r"(?:help|list commands|show commands|what can you do|what can i say|show (?:me )?(?:the )?commands|"
      r"(?:open |show )?(?:the )?voice (?:guide|help)|how do i use (?:this|you|the voice agent))",
      r"(?:helps?|health|hell|halp|help me|commands)"], _later("guide.open_guide"), wake=True)
rule(H, "help with <topic>", "The guide at that part: 'help with spotify', 'what can I say for discord'",
     [r"(?:help|commands|what can i say|what can you do) (?:with|for|about|in) (.+)", r"how do i (?:use|control) (.+?)(?: with (?:my )?voice)?"],
     lambda t: _later("guide.open_guide")(t), wake=True, guard=lambda t: _later("guide.topic_ok")(t))
rule(H, "export my voice history for AI", "Writes tune-me.txt: paste it into Gemini / ChatGPT, then 'import the AI answer'",
     [r"(?:export|save|make|create) (?:my |the )?(?:voice )?(?:history|tuning file|tune file)(?: for (?:the )?(?:ai|gemini|chatgpt))?",
      r"(?:improve|tune|train) (?:the |my )?(?:voice agent|recognition|commands|yourself)"],
     _later("tuning.export_for_ai"), wake=True)
rule(H, "import the AI answer", "Reads the AI's reply from the clipboard into your tuning file",
     [r"import (?:the )?(?:ai(?:'s)? |gemini(?:'s)? |chatgpt(?:'s)? )?(?:answer|reply|tuning|fixes)(?: from (?:the )?clipboard)?",
      r"(?:load|apply) (?:the )?(?:ai(?:'s)? )?(?:tuning|fixes|answer)"], _later("tuning.import_from_clipboard"), wake=True)
rule(H, "check for updates", "Updates the voice agent if there's a new version",
     [r"(?:check for|install|get|look for) (?:new )?updates?(?: for (?:the )?voice agent)?", r"update (?:the )?voice agent",
      r"update yourself"], _ui("update"), wake=True)
rule(H, "check my setup", "Tests the mic, GPU, Spotify, Discord, Stremio, clips… and says how to fix what's missing",
     [r"(?:check|test|diagnose) (?:my |the )?(?:setup|install(?:ation)?|voice agent|everything|commands|integrations?)",
      r"(?:run )?(?:the |a )?setup (?:check|test)", r"does everything work", r"test (?:all )?(?:the |my )?(?:voice )?commands"],
     _later("checkup.run_and_open"), wake=True)
rule(H, "voice replies on | off", "Spoken answers; 'stop talking' / 'talk to me'",
     [r"(?:turn |switch )?(on|off) (?:the )?(?:voice|spoken|talking|audio) (?:replies|answers|responses|feedback)",
      r"(?:turn |switch )?(?:the )?(?:voice|spoken|talking) (?:replies|answers|responses|feedback) (on|off)",
      r"(?:stop|quit) (talking|speaking)(?: to me)?", r"be (quiet)", r"(?:start )?(talk|speak)(?:ing)? (?:to me|back|again|out loud)"],
     lambda st: s.voice_replies("off" if st in ("off", "talking", "speaking", "quiet") else "on"))
rule(H, "never mind", "Do nothing (started talking by mistake)",
     [r"never ?mind(?: that)?", r"forget (?:it|that|about it)", r"cancel(?: that| it)?", r"ignore (?:that|it|me)",
      r"scratch that", r"nothing", r"no(?:thing)?,? never ?mind", r"oops"], s.never_mind, wake=True)

# Browser (keystrokes into the window in front) ---------------------------------------
rule(B, "new tab", "Ctrl+T", [r"(?:open |make |create |launch |start |give me )?(?:a |another )?new tab"], lambda: a.keys("ctrl+t"), after=0.5)
rule(B, "close tab", "Ctrl+W", [r"close " + THE + r"(?:current )?tab"], lambda: a.keys("ctrl+w"))
rule(B, "reopen tab", "Ctrl+Shift+T",
     [r"(?:reopen|restore|bring back|undo close|undo closing|open again) " + THE + r"(?:last |closed |previous )*tab"],
     lambda: a.keys("ctrl+shift+t"))
rule(B, "next | previous tab", "Ctrl+Tab / Ctrl+Shift+Tab",
     [r"(next|previous|last) tab", r"(?:switch to|go to) (?:the )?(next|previous|last) tab", r"tab (right|left)"],
     lambda d: a.keys("ctrl+tab" if d in ("next", "right") else "ctrl+shift+tab"))
rule(B, "tab <1-9>", "Jump to a tab", [r"(?:go to |switch to )?(?:the )?tab (?:number )?(.+)", r"(?:the )?(\w+) tab"],
     lambda n: a.keys(f"ctrl+{9 if n == 'last' else num(n)}"), guard=lambda n: n == "last" or (num(n) or 0) in range(1, 10))
rule(B, "new window | private window", "Ctrl+N / private (Ctrl+Shift+N, Firefox Ctrl+Shift+P)",
     [r"(?:open |make )?(?:a )?(new|private) (?:browser )?window"],
     lambda k: a.keys("ctrl+n" if k == "new" else "ctrl+shift+p" if a.fg_title_has("firefox") else "ctrl+shift+n"), after=0.8)
rule(B, "go back | forward", "Alt+Left / Alt+Right",
     [r"(?:go |page )?(back)", r"(?:go |page )?(forward)", r"(?:go to )?(?:the )?(previous|next) page"],
     lambda d: a.keys("alt+left" if d in ("back", "previous") else "alt+right"))
rule(B, "reload page", "F5", [r"(?:reload|refresh)(?: " + THE + r"(?:page|tab|site|website))?"], lambda: a.keys("f5"))
rule(B, "scroll up | down", "Page Up / Page Down",
     [r"scroll (up|down)(?: (?:the )?page)?", r"page (up|down)", r"(?:go )?(up|down) (?:a )?page"],
     lambda d: a.keys("pageup" if d == "up" else "pagedown"))
rule(B, "scroll up | down a bit", "Three arrow-key steps",
     [r"scroll (up|down) (?:a (?:little )?bit|a little|slightly)", r"scroll (?:a )?(?:little|tiny|bit)(?: bit)?(?: (up|down))?"],
     lambda d="down": a.keys("up" if d == "up" else "down", 3))
rule(B, "up | down (one word)", "One word scrolls a page", [r"(up|down)"],
     lambda d: a.keys("pageup" if d == "up" else "pagedown"), wake=True)
rule(B, "top | bottom of page", "Home / End",
     [r"(?:go to |scroll to |jump to )?(?:the )?(top|bottom)(?: of (?:the )?page)?"],
     lambda d: a.keys("home" if d == "top" else "end"))
rule(B, "zoom in | out | reset", "Ctrl + / Ctrl - / Ctrl 0",
     [r"zoom (in|out|reset)", r"(?:make )?(?:the )?(?:text|font|page|everything|website|site|words) (bigger|smaller)",
      r"(?:reset|normal) zoom"],
     lambda d="reset": a.keys({"in": "ctrl+plus", "bigger": "ctrl+plus", "out": "ctrl+minus",
                               "smaller": "ctrl+minus"}.get(d, "ctrl+0")))
rule(B, "address bar", "Ctrl+L", [r"(?:go to |focus |click |select )?(?:the )?(?:address|url|search|location) bar"],
     lambda: a.keys("ctrl+l"))
rule(B, "bookmark page", "Ctrl+D", [r"(?:bookmark|star) " + THE + r"(?:page|site|tab)?", r"add (?:a )?bookmark"],
     lambda: a.keys("ctrl+d"))
rule(B, "downloads | history page", "Ctrl+J / Ctrl+H",
     [r"(?:open |show )?(?:the |my )?(downloads|history) (?:page|tab|list)", r"(?:show|open) (?:my )?browser (downloads|history)"],
     lambda which: a.keys("ctrl+j" if which == "downloads" else "ctrl+h"))
rule(B, "find <text> on page", "Ctrl+F, then type it",
     [r"(?:find|search(?: for)?|look for) (.+?) (?:on|in) (?:this |the )?page", r"find on page (.+)"],
     lambda q: (a.keys("ctrl+f"), a.type_text(q)), wake=True, free=True)

# Keyboard ----------------------------------------------------------------------------
rule(K, "type <text>", "Types it into the window in front",
     [r"(?:type|write|type out|enter text|dictate) (.+)"], a.type_text, wake=True, free=True)
rule(K, "press <key>", "enter / escape / tab / control shift t / alt f4 / down 3 times …",
     [r"(?:press|hit|tap|push) (?:the )?(.+?)(?: key)?(?: button)?"], a.press, guard=a.press_ok)
rule(K, "enter | escape | tab | backspace (one word)", "", [r"(enter|escape|tab|backspace|delete|space ?bar)"],
     a.press, wake=True)
rule(K, "copy | paste | cut", "Ctrl+C / Ctrl+V / Ctrl+X",
     [r"(copy|paste|cut)(?: (?:that|this|it|the text|the selection|here))?"],
     lambda k: a.keys({"copy": "ctrl+c", "paste": "ctrl+v", "cut": "ctrl+x"}[k]))
rule(K, "undo | redo", "Ctrl+Z / Ctrl+Y", [r"(undo|redo)(?: (?:that|it|this|the last (?:thing|change)))?"],
     lambda k: a.keys("ctrl+z" if k == "undo" else "ctrl+y"))
rule(K, "select all", "Ctrl+A", [r"select (?:all|everything)(?: (?:the )?text)?"], lambda: a.keys("ctrl+a"))
rule(K, "save", "Ctrl+S", [r"save (?:it|this|that|the file|my work|changes|the document)"], lambda: a.keys("ctrl+s"))

# Windows -----------------------------------------------------------------------------
WIN = r"(?:(?:the |this |that |my |current )?(?:window|app|application|program)|it|this|that)"
TOO = {"big": "smaller", "small": "bigger", "wide": "narrower", "narrow": "wider", "tall": "shorter", "short": "taller"}
rule(W, "show desktop", "Win+D (say it again to bring everything back)",
     [r"(?:show|go to|take me to) (?:the )?desktop", r"minimi[sz]e (?:everything|all(?: the)?(?: windows| apps)?)",
      r"hide (?:everything|all (?:the )?windows)"], lambda: a.keys("win+d"))
rule(W, "task view", "Win+Tab: every window and desktop",
     [r"(?:open |show )?(?:the )?task view", r"show (?:me )?all (?:the |my )?windows"], lambda: a.keys("win+tab"))
rule(W, "desktop <1-10>", "Virtual desktops",
     [r"(?:go to |switch to |jump to |move to |take me to )?(?:the )?(?:virtual )?(?:desktop|workspace) (?:number )?(.+)"],
     a.desktop, guard=lambda n: (num(n) or 0) in range(1, 11))
rule(W, "next | previous desktop", "Ctrl+Win+Right / Left",
     [r"(?:go to |switch to )?(?:the )?(next|previous|last) (?:virtual )?(?:desktop|workspace)", r"(?:desktop|workspace) (right|left)"],
     lambda d: a.keys("ctrl+win+right" if d in ("next", "right") else "ctrl+win+left"))
rule(W, "new | close desktop", "Ctrl+Win+D / Ctrl+Win+F4",
     [r"(new|close) (?:virtual )?desktop", r"(?:make|create|add) (?:a )?(new) (?:virtual )?desktop"],
     lambda k: a.keys("ctrl+win+d" if k == "new" else "ctrl+win+f4"))
rule(W, "move window to the other screen", "Win+Shift+Arrow",
     [r"(?:move|send|throw|put) (?:this |the |it )?(?:window )?(?:to )?(?:the )?(other|next|second|left|right) (?:monitor|screen|display)"],
     lambda d: a.keys("win+shift+left" if d == "left" else "win+shift+right"))
rule(W, "close window", "Closes the window in front",
     [r"close (?:this |the |that |current )?(?:window|app|application|program)", r"close (?:it|this|that)",
      r"get rid of (?:this|it|this window)"], a.close_window)
rule(W, "fullscreen", "Any app: browsers and Explorer use their own (F11), games Alt+Enter, other apps fill "
     "the whole screen without borders. Say it again to undo",
     [r"(?:toggle |go |make (?:it |this |the window |this window )?)?fullscreen(?: (?:this |the )?(?:window|app)| it| this)?",
      r"(?:exit|leave|undo) fullscreen", r"(?:make (?:it |this )?)?cover the (?:whole )?screen"], a.fullscreen)
rule(W, "maximize | restore", "Maximise or back to normal size",
     [r"(?:un)?maximi[sz]e(?: (?:this |the )?window| it| this)?", r"(?:make (?:it|this|the window) )?(?:as big as possible|full size|max size)",
      r"(?:restore|unmax) (?:the )?(?:window )?size"], a.maximize)
rule(W, "center window", "Middle of the screen", [r"cent(?:er|re) (?:this |the |it|the window|this window|window)?"],
     lambda: a.place("centre"))
rule(W, "always on top", "Keep this window above the others (say it again to stop)",
     [r"(?:un)?pin (?:this |the |it|the window|this window|window)?", r"(?:keep|put|make) (?:it |this |the window )?(?:on top|always on top)",
      r"always on top"], a.topmost)
SIZE = a.SIZE_WORDS
rule(W, "shrink | grow [a bit | a lot | by <n> percent]", "10% (a bit 5, a lot 25), about its centre",
     [rf"({SIZE}) {WIN}(?: {a.AMOUNT})?", rf"make {WIN} (?:{a.AMOUNT} )?({SIZE})(?: {a.AMOUNT})?",
      rf"({SIZE}) (?:the )?(?:window )?size(?: of {WIN})?(?: {a.AMOUNT})?",
      rf"(?:resize|size) {WIN} (?:to be )?(?:{a.AMOUNT} )?({SIZE})",
      rf"(?:the |this )?window (?:needs to be|should be|is too|is) (?:{a.AMOUNT} )?({SIZE}|big|small|wide|narrow|tall|short)"],
     lambda *w: a.resize_cmd(*[TOO.get(v, v) for v in w]), guard=lambda *w: a.size_ok(*[TOO.get(v, v) for v in w]))
rule(W, "smaller | bigger (one word)", "'smaller', 'a bit bigger', 'it's too wide'",
     [rf"({SIZE})(?: {a.AMOUNT})?", rf"{a.AMOUNT} ({SIZE})",
      rf"(?:it|this|that)(?:'s| is) (?:{a.AMOUNT} )?too (big|small|wide|narrow|tall|short)"],
     lambda *w: a.resize_cmd(*[TOO.get(v, v) for v in w]), guard=lambda *w: a.size_ok(*[TOO.get(v, v) for v in w]), wake=True)
rule(W, "snap left | right", "Windows snap (Win+Left / Win+Right)",
     [r"snap (?:it |this |the window )?(left|right)", r"(?:snap|move|put|send|throw) (?:it |this |the window )?(?:to )?(?:the )?(left|right)"],
     lambda d: a.keys(f"win+{d}"))
rule(W, "halves, corners, middle", "'put it in the top right corner', 'bottom half'",
     [rf"(?:snap|move|put|send|throw|tile|place|dock) (?:{WIN} )?(?:to |on |in |into )?(?:the )?(left|right|top|bottom|upper|lower) half(?: of the screen)?",
      rf"(?:snap|move|put|send|throw|place) (?:{WIN} )?(?:to |in |into )?(?:the )?((?:top|bottom|upper|lower) (?:left|right))(?: corner)?",
      rf"(?:snap|move|put|place) (?:{WIN} )?(?:to |in |into )?(?:the )?(cent(?:er|re)|middle) of (?:the )?screen"],
     a.place)
rule(W, "previous window", "Alt+Tab: back to the window you were just in",
     [r"(?:go to |switch to |cycle to |focus )?(?:the )?(?:next|other|previous|last) window", r"(?:cycle|alt tab|switch) windows?",
      r"(?:go |switch )?back to (?:the )?(?:last|previous|other) (?:window|app)"], lambda: a.keys("alt+tab"))
rule(W, "minimize", "The window in front",
     [r"(?:minimi[sz]e|hide) " + WIN, r"(?:send|put) " + WIN + r" (?:away|to the background)", r"(?:get|put) (?:it|this) out of the way",
      r"minimi[sz]e"], a.minimize)
rule(W, "restore window", "The last minimised one ('all' brings them all back)",
     [r"(?:restore|unminimi[sz]e|bring back|show|unhide|get back) (?:the |my )?(?:minimi[sz]ed|hidden|last) (?:window|app|windows|apps)",
      r"unminimi[sz]e(?: (?:the )?window)?", r"(?:restore|bring back|unminimi[sz]e) (all|everything)(?: (?:the )?(?:minimi[sz]ed |hidden )?(?:windows|apps))?",
      r"where(?:'s| is| did) (?:my )?(?:window|app) go"],
     lambda al=None: a.restore_minimized(al is not None))
rule(W, "force quit window", "Ends the app in front", [r"(?:force (?:close|quit)|kill) " + WIN],
     lambda: a.quit_app(a.fg().app) if a.fg() else a.log("force quit the app in front"), wake="strict")

# Sound & media -----------------------------------------------------------------------
rule(S, "volume up | down", "5% steps",
     [r"volume (up|down)", r"(?:turn|crank|bump|pump|jack) (?:the )?(?:volume|sound|music|it) (up|down)",
      r"(?:pump|bump|jack|crank) (up|down) (?:the )?(?:volume|sound|music|it)",
      r"(?:turn|crank) (up|down) (?:the )?(?:volume|sound|music)"], a.volume_step)
rule(S, "louder | quieter", "Natural forms, 5%",
     [r"(?:make it |turn it )?(?:a (?:little )?bit |a little |slightly )?(louder|quieter|softer)",
      r"(increase|raise|decrease|lower|reduce) (?:the )?(?:volume|sound)"],
     lambda w: a.volume_step("up" if w in ("louder", "increase", "raise") else "down"))
rule(S, "much louder | quieter", "20% steps",
     [r"(?:much|a lot|way) (louder|quieter|softer)", r"(louder|quieter|softer) a lot",
      r"(increase|raise|decrease|lower|reduce) (?:the )?(?:volume|sound) a lot",
      r"(?:turn|crank|pump) (?:the )?(?:volume|sound|it) (up|down) a lot"],
     lambda w: a.volume_step("up" if w in ("louder", "increase", "raise", "up") else "down", "20"))
rule(S, "volume to <0-100>", "'turn the volume up to 30', 'set the volume to 40 percent'",
     [r"(?:turn (?:up|down)|turn|increase|decrease|raise|lower|reduce|change|set|put|bring|adjust|drop|make) (?:the )?(?:volume|sound)"
      r"(?: (?:up|down))? (?:to|at) (.+?)(?: percent)?",
      r"(?:turn|bring|put) (?:the )?(?:volume|sound) (?:up|down) to (.+?)(?: percent)?"],
     a.volume_set, guard=a.vol_ok)
rule(S, "volume up | down by <n>", "Bigger steps",
     [r"(?:turn )?(?:the )?volume (up|down) (?:by )?(?!to\b)(.+?)(?: percent)?",
      r"(?:turn|crank) (?:it|the volume) (up|down) by (.+?)(?: percent)?",
      r"(?:turn|crank) (up|down) (?:the )?volume (?:by )?(?!to\b)(.+?)(?: percent)?",
      r"(increase|raise|decrease|lower|reduce) (?:the )?volume (?:by )?(?!to\b)(.+?)(?: percent)?"],
     lambda d, n: a.volume_step("up" if d in ("up", "increase", "raise") else "down", n),
     guard=lambda d, n: num(n) is not None and 0 < num(n) <= 100)
rule(S, "volume <0-100>", "Set volume",
     [r"(?:set |turn |change |put )?(?:the )?(?:volume|sound) (?:to |at )?(.+?)(?: percent)?"], a.volume_set, guard=a.vol_ok)
MEDIA = (r"(?:the |my |our |this |that |some )?(?:music|songs?|tracks?|playback|videos?|audio|media(?: players?)?|"
         r"(?:tv )?shows?|movies?|podcasts?|items?|player|episodes?)")
rule(S, "mute | unmute", "Speakers",
     [r"(mute|unmute)(?: (?:the |my |our |this )?(?:sound|volume|audio|speakers?|computer|pc|everything|it))?",
      r"(mute|unmute) " + MEDIA, r"(?:turn|switch) (?:the )?sound (off|on)", r"(?:turn|switch) (off|on) (?:the )?sound",
      r"(silence)(?: (?:the )?computer)?"],
     lambda st: a.mute_sound({"mute": True, "off": True, "silence": True, "unmute": False, "on": False}[st]))
rule(S, "mute mic", "Your microphone, for every app",
     [r"(?:mute|unmute|toggle) (?:the |my )?(?:mic|microphone)(?: everywhere)?"], a.mute_mic)
rule(S, "switch audio output", "Win+Ctrl+V: pick speakers / headphones",
     [r"(?:switch|change|pick|choose) (?:the )?(?:audio|sound)(?: output)?(?: device)?", r"(?:switch|change) (?:the )?output(?: device)?",
      r"(?:switch|change) to (?:my )?(?:headphones|speakers|headset|earbuds)"], lambda: a.keys("ctrl+win+v"))
rule(S, "pause | play | stop music", "Whatever is playing (Spotify, the browser, Stremio…)",
     [r"(pause|play|resume|stop|continue|unpause|start)(?: playing)? " + MEDIA,
      r"(pause|stop) (?:it|this|that)", r"(?:keep|carry on) (playing)", r"(play)(?: some)? music", r"(stop) playing"],
     lambda act: a.media({"continue": "resume", "unpause": "resume", "start": "play", "playing": "play", "stop": "pause"}.get(act, act)))
rule(S, "next | previous track", "Skip track",
     [r"(next|previous|last) (?:track|song|one|item)", r"(?:play )?(?:the )?(next|previous) (?:song|track|item)",
      r"(skip)(?: (?:this|the|that) (?:song|track|item|one))?", r"(skip) (?:song|track|item|this|that|it)",
      r"skip (?:to )?(?:the )?(next)(?: (?:song|track|item|one))?", r"(change|switch) (?:the )?song",
      r"go (back) (?:a|one) (?:song|track)", r"(?:go )?(back) to (?:the )?(?:previous|last) (?:song|track|item|one)",
      r"(?:replay|play) (?:the )?(previous|last)(?: (?:song|track|item|one))?(?: again)?"],
     lambda w: a.media("next" if w in ("next", "skip", "change", "switch") else "previous"))
rule(S, "skip ahead | rewind <n> seconds", "In the video / song playing",
     [r"(?:skip|jump|go|fast) (forward|ahead) (?:by )?(.+?) (seconds?|minutes?)", r"(rewind|back) (?:by )?(.+?) (seconds?|minutes?)",
      r"(?:go|jump|skip) (back) (?:by )?(.+?) (seconds?|minutes?)"],
     lambda d, n, u: a.seek("forward" if d in ("forward", "ahead") else "back", n, u), guard=lambda d, n, u: num(n) is not None)
rule(S, "what's playing", "Title and artist",
     [r"what(?:'s| is) (?:this )?(?:song|playing|this)", r"(?:which|what) song is (?:this|playing)", r"now playing",
      r"who (?:is )?sings? this"], a.now_playing)
rule(S, "pause | play | next | previous", "Short forms", [r"(pause|play|resume|stop|next|previous|unpause|skip)"],
     lambda act: a.media({"unpause": "resume", "skip": "next", "stop": "pause"}.get(act, act)), wake=True)
rule(S, "go to <n> minutes [<n>]", "'go to 1 minute 30', 'skip to 90 seconds'",
     [r"(?:go|skip|jump|seek|fast forward) to (.+?) (minutes?|seconds?)(?: (?:and )?(.+?)(?: seconds?)?)?"],
     a.seek_abs, guard=lambda n, u, e=None: num(n) is not None and (e is None or num(e) is not None))

# App volume --------------------------------------------------------------------------
rule(AU, "<app> volume <n> | up | down", "One app only: 'spotify volume 30', 'turn discord down', 'game volume 50'",
     [r"(?:set |turn |change |put )?(?:the )?(.+?)(?:'s)? volume (?:to |at )?(.+?)(?: percent)?",
      r"(?:turn|make) (?:the )?(.+?) (up|down|louder|quieter|softer)"],
     a.app_volume, guard=lambda n, sp: a.sound_app(n) is not None and (sp in ("up", "down", "louder", "quieter", "softer")
                                                                      or (num(sp) if num(sp) is not None else -1) in range(0, 101)))
rule(AU, "mute | unmute <app>", "One app's sound: 'mute spotify', 'mute the browser', 'mute the game'",
     [r"(mute|unmute|silence) (?:the |my )?(.+?)(?:'s)?(?: sound| audio)?"], a.app_mute,
     guard=lambda st, n: a.sound_app(n) is not None)

# System ------------------------------------------------------------------------------
rule(SY, "screenshot", "Region (Win+Shift+S)",
     [r"(?:take |grab |capture |snap )?(?:a )?screenshot(?: of (?:a |the )?(?:region|area|part))?", r"screen capture",
      r"(?:open |start )?(?:the )?snipping tool"], s.screenshot, wake=True)
rule(SY, "screenshot screen | window", "Whole screen (saved) or the window in front (copied)",
     [r"(?:take |grab |capture |snap )?(?:a )?screenshot (?:of )?(?:the )?(?:whole |entire |full )?(screen|fullscreen|everything|window|this window)"],
     lambda k: s.screenshot("window" if "window" in k else "full"), wake=True)
rule(SY, "lock", "Lock the PC", [r"lock (?:the |my )?(?:screen|computer|pc|desktop|laptop|it)"], s.lock)
rule(SY, "sleep", "Sleep the PC",
     [r"(?:go to )?sleep", r"put (?:the )?(?:computer|pc|laptop) to sleep", r"sleep (?:the )?(?:computer|pc|laptop)"],
     s.sleep_pc, wake="strict")
rule(SY, "shut down [in <n> minutes]", "30 s warning; 'cancel shutdown' stops it",
     [r"shutdown(?: (?:the )?(?:computer|pc|laptop|system))?(?: in (.+?) minutes?)?",
      r"(?:turn|power|switch) off (?:the )?(?:computer|pc|laptop|system)(?: in (.+?) minutes?)?"],
     lambda m=None: s.shutdown("shutdown", num(m) if m else None), wake="strict", guard=lambda m=None: m is None or num(m) is not None)
rule(SY, "restart [in <n> minutes]", "30 s warning; 'cancel shutdown' stops it",
     [r"(?:restart|reboot) (?:the )?(?:computer|pc|laptop|system|windows)(?: in (.+?) minutes?)?", r"reboot"],
     lambda m=None: s.shutdown("restart", num(m) if m else None), wake="strict", guard=lambda m=None: m is None or num(m) is not None)
rule(SY, "cancel shutdown", "", [r"(?:cancel|stop|abort) (?:the )?(?:shutdown|restart|reboot)", r"don't (?:shutdown|restart)"],
     s.cancel_shutdown)
rule(SY, "sign out", "Log out of Windows", [r"(?:sign|log) (?:me )?out(?: of windows)?"], s.sign_out, wake="strict")
rule(SY, "fix the taskbar", "Restarts Windows Explorer (taskbar / Start menu stuck)",
     [r"(?:restart|fix|reload|reset) (?:the )?(?:windows )?(?:explorer|taskbar|start menu)", r"(?:the )?taskbar is (?:stuck|frozen|broken)"],
     s.restart_explorer, wake=True)
rule(SY, "brightness up | down | <0-100>", "Laptop screens",
     [r"brightness (up|down)", r"(?:turn|make) (?:the )?(?:brightness|screen) (up|down)",
      r"(?:make (?:the )?screen |screen )?(brighter|dimmer|darker)", r"(increase|raise|decrease|lower|reduce) (?:the )?brightness",
      r"(?:set |turn |change |put )?(?:the )?(?:screen )?brightness (?:to |at )?(.+?)(?: percent)?"],
     lambda d: s.brightness("up" if d in ("up", "brighter", "increase", "raise") else
                            "down" if d in ("down", "dimmer", "darker", "decrease", "lower", "reduce") else d),
     guard=lambda d: d in ("up", "down", "brighter", "dimmer", "darker", "increase", "raise", "decrease", "lower", "reduce")
     or (num(d) if num(d) is not None else -1) in range(0, 101))
rule(SY, "wifi | bluetooth on | off", "Windows' radio switches",
     [r"(?:turn |switch )?(on|off|enable|disable) (?:the )?(wifi|bluetooth)", r"(?:turn |switch )?(?:the )?(wifi|bluetooth) (on|off)"],
     lambda p, q: s.radio(*((q, p) if p in ("on", "off", "enable", "disable") else (p, q))))
rule(SY, "clipboard history | emoji | notifications | quick settings", "Win+V / Win+. / Win+N / Win+A",
     [r"(?:open |show )?(?:the |my )?(clipboard)(?: history)?", r"(?:open |show )?(?:the )?(emoji)(?:s| panel| picker| keyboard)?",
      r"(?:open |show )?(?:the |my )?(notifications)(?: cent(?:er|re)| panel)?",
      r"(?:open |show )?(?:the )?(quick settings|action cent(?:er|re)|control cent(?:er|re))", r"(?:open )?(?:the )?(run) (?:box|dialog)",
      r"(?:open |show )?(?:the )?(start) menu"],
     lambda w: a.keys({"clipboard": "win+v", "emoji": "win+period", "notifications": "win+n", "run": "win+r",
                       "start": "win"}.get(w, "win+a")))
rule(SY, "search my PC for <text>", "Windows search",
     [r"search (?:windows|my (?:pc|computer|laptop)|the (?:computer|pc)) for (.+)",
      r"(?:find|search for|look for) (.+?) on (?:my |this |the )?(?:pc|computer|laptop)"], a.windows_search, wake=True, free=True)

# Info --------------------------------------------------------------------------------
rule(I, "time", "", [r"(?:what(?:'s| is) )?(?:the )?(?:current )?time(?: (?:is it|now|right now|please))?", r"what time is it(?: now| right now)?",
                     r"tell me (?:the )?(?:current )?time", r"(?:do you )?(?:know|have) the time", r"time (?:check|please)"], s.clock, wake=True)
rule(I, "date", "", [r"(?:what(?:'s| is) )?(?:the |today's )?(?:current )?date(?: today)?", r"tell me (?:the |today's )?(?:current )?date(?: today)?",
                     r"what day is (?:it|today)(?: today)?", r"what's today", r"what(?:'s| is) the day today", r"which day is (?:it|today)"],
     s.date_today, wake=True)
rule(I, "weather [tomorrow | rain]", "'what's the weather', 'will it rain', 'weather tomorrow'",
     [r"(?:what(?:'s| is) )?(?:the )?weather(?: like)?(?: (?:today|now|right now|outside|out there))?",
      r"(?:tell me|give me) (?:the )?weather(?: like)?", r"how(?:'s| is) (?:the )?weather(?: (?:today|outside|out there))?(?: like)?",
      r"how (?:hot|cold|warm) is it(?: outside| today| out there)?", r"(?:what(?:'s| is) )?the temperature outside",
      r"(?:what(?:'s| is) )?the (?:weather|forecast) (?:for )?(tomorrow)", r"(?:what(?:'s| is) )?(tomorrow)'s weather",
      r"weather (tomorrow)", r"(?:is it|will it|is it going to|it's going to|is there going to be) (rain)(?:ing)?(?: today)?",
      r"(?:will it|is it going to) (rain) (tomorrow)", r"forecast(?: for)? (tomorrow)", r"(?:what(?:'s| is) )?the forecast"],
     lambda p=None, q=None: s.weather(f"{p} {q}" if q else p), wake=True)
rule(I, "status", "RAM, CPU, GPU and disk in one answer",
     [r"(?:system |pc |computer |my )?status(?: report| check)?", r"(?:how(?:'s| is) )(?:my |the )?(?:pc|computer|system|laptop)(?: doing)?",
      r"system check", r"(?:give me )?(?:a )?(?:quick )?(?:system )?(?:summary|overview)"], s.status_info, wake=True)
rule(I, "ram", "RAM used / total",
     [r"(?:how much |what(?:'s| is) (?:the |my )?)?(?:the |my )?(?:ram|memory)(?: usage| used| left| free)?", r"memory usage"],
     s.ram, wake=True)
rule(I, "what is using RAM", "Top 5 apps by RAM",
     [r"what(?:'s| is)(?: all)? using (?:the |my |so much |all the )?(?:ram|memory)", r"top (?:memory|ram)",
      r"what(?:'s| is) eating (?:my |the )?(?:ram|memory)", r"(?:which|what) apps? (?:is |are )?using (?:the |my )?(?:most )?(?:ram|memory)",
      r"(?:ram|memory) (?:hogs?|users?|by app)", r"who(?:'s| is) using (?:the |my )?(?:ram|memory)"], s.top_ram, wake=True)
rule(I, "gpu", "NVIDIA temperature, load and VRAM",
     [r"(?:what(?:'s| is) (?:the |my )?)?(?:gpu|graphics card|video card|vram)(?: temp(?:erature)?s?| usage| load| memory)?",
      r"how hot is (?:the |my )?(?:gpu|graphics card)"], s.gpu_info, wake=True)
rule(I, "cpu", "CPU load", [r"(?:what(?:'s| is) (?:the |my )?)?(?:cpu|processor)(?: usage| load)?"], s.cpu_info, wake=True)
rule(I, "disk space", "Free space on C:", [r"(?:disk|storage|ssd|hard drive)(?: space| usage| left| free)?", r"how much (?:disk |storage )?space(?: is left| do i have)?"],
     s.disk_info, wake=True)
rule(I, "battery", "Laptop battery", [r"(?:what(?:'s| is) (?:the |my )?)?battery(?: level| percentage| left)?", r"how much battery(?: (?:is )?left| do i have)?"],
     s.battery, wake=True)
rule(I, "uptime", "Time since start-up", [r"uptime", r"how long (?:has it|have i|has the (?:pc|computer) been) (?:up|on|running)"], s.uptime_info, wake=True)
rule(I, "ip address", "Local IP", [r"(?:what(?:'s| is) )?(?:my )?ip(?: address)?"], s.ip_info, wake=True)

# Timers ------------------------------------------------------------------------------
SET = r"(?:set|start|create|make|put on|give me|begin|run|add)"
rule(T, "timer <n> minutes [called …]", "'set a 10 minute timer', 'remind me in 10 minutes to stretch'",
     [rf"(?:{SET} )?(?:a |an |the |my )?(.+?) (?:timer|countdown)(?: (?:named|called|for) (.+))?",
      rf"(?:{SET} )?(?:a |an |the |my )?(?:timer|countdown) (?:for |of )?(.+?)(?: (?:named|called) (.+))?",
      r"remind me (?:in|after) (.+?)(?: (?:to|that|about) (.+))?", r"count ?down (?:from )?(.+)", r"wake me(?: up)? (?:in|after) (.+)"],
     lambda dur, label=None: s.timer_start(dur, label), wake=True, free=True,
     guard=lambda dur, label=None: parse_duration(dur) is not None)
rule(T, "timer called <name> for <n>", "'set a timer called pizza for 20 minutes', 'remind me to stretch in 10 minutes'",
     [rf"{SET} (?:a |an |the |my )?timer (?:named|called) (.+?) for (.+)", r"remind me (?:to |about )?(.+?) in (.+)"],
     lambda label, dur: s.timer_start(dur, label), wake=True, free=True, guard=lambda label, dur: parse_duration(dur) is not None)
TSPEC = r"(?:the |my |that |this )?(.*?) ?timers?(?: (?:for|of|called|named) (.+))?"
TSPEC_BY = r"(?:the |my |that |this )?(.*?) ?timers?(?: (?:for|of|called|named) (.+?))?"
rule(T, "timer status", "'how long is left', 'what timers are running'",
     [r"(?:how much time|how long|time)(?: is| do i have)? (?:left|remaining)(?: (?:on|for|in) " + TSPEC + ")?",
      r"(?:what(?:'s| is) the )?(?:timers?) status", TSPEC + r" status", r"status of " + TSPEC, r"(?:check|show|list) " + TSPEC,
      r"how(?:'s| is) " + TSPEC + r"(?: doing| going)?", r"what timers? (?:do i have|are (?:running|set|on|there))",
      r"when (?:does|will|is) " + TSPEC_BY + r" (?:end|go off|finish|ring|done)", r"(?:are there|do i have) (?:any )?timers?(?: running)?"],
     lambda *sp: s.timer_status(*sp), wake=True)
rule(T, "cancel all timers", "", [r"(?:cancel|stop|delete|remove|end|clear|kill|turn off) all (?:of )?(?:the |my )?timers"],
     lambda: s.timer_cancel(all_=True), wake=True)
rule(T, "cancel timer", "'cancel the timer', 'stop the pizza timer'",
     [r"(?:cancel|stop|delete|remove|end|kill|turn off|clear|dismiss|abort) " + TSPEC], lambda *sp: s.timer_cancel(*sp), wake=True)
rule(T, "add time to timer", "'add 5 minutes to my timer'",
     [r"(?:add|put) (.+?) (?:to|on|onto) " + TSPEC], lambda d, *sp: s.timer_adjust(d, 1, *sp), wake=True,
     guard=lambda d, *sp: parse_duration(d) is not None)
rule(T, "add time to timer (by)", "", [r"(?:increase|extend|lengthen) " + TSPEC_BY + r" by (.+)"],
     lambda *p: s.timer_adjust(p[-1], 1, *p[:-1]), wake=True, guard=lambda *p: parse_duration(p[-1]) is not None)
rule(T, "take time off timer", "'take 2 minutes off the timer'",
     [r"(?:take|remove|subtract|take away|knock|cut) (.+?) (?:off|from|off of) " + TSPEC],
     lambda d, *sp: s.timer_adjust(d, -1, *sp), wake=True, guard=lambda d, *sp: parse_duration(d) is not None)
rule(T, "take time off timer (by)", "", [r"(?:decrease|reduce|shorten|cut) " + TSPEC_BY + r" by (.+)"],
     lambda *p: s.timer_adjust(p[-1], -1, *p[:-1]), wake=True, guard=lambda *p: parse_duration(p[-1]) is not None)
rule(T, "pause | resume timer", "'pause the timer', 'resume my pizza timer'",
     [r"(pause|hold|freeze|resume|unpause|continue|restart|unfreeze) " + TSPEC],
     lambda verb, *sp: s.timer_pause(verb not in ("pause", "hold", "freeze"), *sp), wake=True)

# Open & search -----------------------------------------------------------------------
rule(A, "open <app | game | site | folder | settings page>", "Anything in the Start menu, Steam/Epic games, sites, "
     "'downloads', 'sound settings', 'something dot com'",
     [r"(?:open|launch|start|run|bring up|pull up|fire up|load) (?:up )?(.+)", r"go to (.+)"],
     a.open_app, guard=a.can_open, after=1.6)
rule(A, "youtube <text>", "Search YouTube",
     [r"(?:search )?youtube (?:for )?(.+)", r"(?:search|look up|look for|find|play|watch) (.+?) on youtube", r"search youtube for (.+)"],
     lambda q: a.web(q, "youtube"), wake=True, free=True, after=1.6)
rule(A, "wikipedia <text>", "", [r"(?:search )?wikipedia (?:for )?(.+)", r"(?:look up|search|find) (.+?) on wikipedia"],
     lambda q: a.web(q, "wikipedia"), wake=True, free=True, after=1.6)
rule(A, "amazon | flipkart <text>", "Shopping search",
     [r"(?:search )?(amazon|flipkart) (?:for )?(.+)", r"(?:search|find|look for|buy) (.+?) on (amazon|flipkart)"],
     lambda p, q: a.web(q, p) if p in ("amazon", "flipkart") else a.web(p, q), wake=True, free=True, after=1.6)
rule(A, "steam <game>", "Steam store search", [r"(?:search )?(?:the )?steam (?:store )?for (.+)", r"(?:search|find|look for|buy) (.+?) on steam"],
     lambda q: a.web(q, "steam"), wake=True, free=True, after=1.6)
rule(A, "reddit | github <text>", "", [r"(?:search )?(reddit|github) (?:for )?(.+)", r"(?:search|find|look for) (.+?) on (reddit|github)"],
     lambda p, q: a.web(q, p) if p in ("reddit", "github") else a.web(p, q), wake=True, free=True, after=1.6)
rule(A, "maps <place>", "Google Maps",
     [r"maps? (?:for )?(.+)", r"(?:where is|directions to|show me|find) (.+?) on (?:the )?maps?", r"where is (.+)"],
     lambda q: a.web(q, "maps"), wake=True, free=True, after=1.6, guard=lambda q: not re.match(r"(?:the )?(?:sound|audio)\b", q))
rule(A, "images of <text>", "Google Images", [r"(?:show me |search |find )?(?:images|pictures|photos) of (.+)"],
     lambda q: a.web(q, "images"), wake=True, free=True)
rule(A, "ask chatgpt | perplexity <question>", "Opens it with your question",
     [r"ask (chatgpt|perplexity) (?:about |for )?(.+)"], lambda p, q: a.web(q, p), wake=True, free=True)
rule(A, "google <text>", "Google search",
     [r"(?:google|ask google|search google for|search google|google search|google it) (.+)", r"(.+?) on google"],
     lambda q: a.web(q, "google"), wake=True, free=True, after=1.6)
rule(A, "play <song | artist>", "No player named: Spotify's search for it",
     [r"play (.+)", r"(?:listen to|i wanna hear|play me) (.+)"], x.spotify_search, wake=True, free=True, late=True,
     guard=lambda q: not re.fullmatch(r"(?:it|this|that|something|some music|music|the music|again|a song|songs)", q))
rule(A, "search <text>", "Google (right after 'open stremio' / 'open youtube' it searches there)",
     [r"(?:search for|search the web for|search online for|search|look up|look for|find out|"
      r"what is|what are|who is|who was|how do i|how to|how does) (.+)"],
     a.web, wake=True, free=True, after=1.6, late=True)
rule(A, "<app name>", "Just the name: switches to it, or opens it",
     [r"(.+)"], a.focus_app, wake=True, late=True,
     guard=lambda n: len(n) > 2 and n not in a.WINDOW_WORDS and (a.app_known(n) or a.can_open(n)), after=0.8)
