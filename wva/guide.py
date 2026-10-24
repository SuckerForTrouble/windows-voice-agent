"""The voice guide: one page with every command and examples that are known to
work (they are the tests), what you said lately, and first-day tips. Opened by
"help", "what can I say", "help with spotify", or the tray. Regenerated each time,
so it always matches this version and your own history."""
import html
import json
import os
import re

from . import APP_NAME, __version__, config, history, paths
from .engine import CTX, RULES

GROUP_INFO = {
    "Open & search": ("🚀", "Open anything by name, or search the web, YouTube, shops, maps."),
    "Close & switch apps": ("🪟", "Close an app even when it's behind your game, quit tray apps completely, jump between apps."),
    "Spotify": ("🎵", "Works while you're in another app or a game."),
    "Discord": ("💬", "Mute, deafen, calls, jump to a server or DM. For use inside games, see Setup tips."),
    "Stremio & watching": ("🎬", "Say a movie or show: its Stremio page opens with the streams to pick from."),
    "Reels & Shorts": ("📱", "Hands-free Instagram reels and YouTube Shorts."),
    "YouTube": ("▶️", "While a YouTube video is the window in front."),
    "Gaming": ("🎮", "Clips and recordings through the NVIDIA app (or Xbox Game Bar), FPS overlay."),
    "Sound & media": ("🔊", "Volume, mute, play/pause/next for whatever is playing."),
    "App volume": ("🎚️", "One app's volume without touching the rest."),
    "Browser": ("🌐", "Tabs, scrolling, zoom: sent to the window in front."),
    "Keyboard": ("⌨️", "Type text or press any key combination."),
    "Windows": ("🖥️", "Snap, resize, minimise, desktops, other monitor."),
    "System": ("⚙️", "Screenshots, lock, sleep, shutdown (with a 30 s warning), Wi-Fi, Bluetooth, brightness."),
    "Info": ("ℹ️", "Ask and it answers, on screen and out loud."),
    "Timers": ("⏱️", "As many as you like, by name."),
    "Voice agent": ("🧭", "Help, setup check, updates, teaching it your voice."),
}
ORDER = list(GROUP_INFO)


def _examples():
    from .examples import CASES
    out = {}
    for case in CASES:
        spoken, want = case[0], case[1]
        if len(want) != 1:
            continue
        lst = out.setdefault(want[0], [])
        t = spoken.rstrip(".?!")
        t = t[:1].upper() + t[1:]
        if t.lower() not in (x.lower() for x in lst):
            lst.append(t)
    return out


def groups():
    ex = _examples()
    by = {}
    for r in RULES:
        by.setdefault(r.group, []).append({"say": r.say, "desc": r.desc, "examples": ex.get(r.say, [])[:4]})
    names = [g for g in ORDER if g in by] + [g for g in by if g not in ORDER]
    return [{"name": g, "icon": GROUP_INFO.get(g, ("•", ""))[0], "intro": GROUP_INFO.get(g, ("", ""))[1],
             "rules": by[g]} for g in names]


def topic_ok(topic):
    t = topic.strip().lower()
    return any(t in g["name"].lower() or any(t in r["say"].lower() for r in g["rules"]) for g in groups())


def _recent():
    rows = history.rows(14)[-30:][::-1]
    return [{"t": e["t"][5:16].replace("T", " "), "heard": e.get("heard", ""), "ok": e.get("result") == "ran",
             "steps": e.get("steps") or []} for e in rows]


def render(topic=""):
    key = config.get("agent_key").upper()
    dkey = config.get("dictate_key").upper()
    data = {"groups": groups(), "recent": _recent(), "topic": topic or ""}
    page = TEMPLATE
    for k, v in {"APP": APP_NAME, "VERSION": __version__, "KEY": key, "DKEY": dkey}.items():
        page = page.replace("{{" + k + "}}", html.escape(v))
    return page.replace("{{DATA}}", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))


def open_guide(topic=None):
    if CTX.dry:
        return CTX.log(f"  open the voice guide{f' at {topic}' if topic else ''}")
    paths.ensure()
    paths.GUIDE.write_text(render(re.sub(r"^(?:the|my) ", "", (topic or "").strip())), encoding="utf-8")
    os.startfile(str(paths.GUIDE))


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Voice guide</title>
<style>
:root{--bg:#f6f7fb;--card:#fff;--ink:#1d2230;--soft:#5d6577;--line:#e3e6ee;--accent:#4f5bd5;--ok:#1f8a4c;--bad:#c2410c;--chip:#eef0fb}
@media (prefers-color-scheme:dark){:root{--bg:#14161c;--card:#1d2029;--ink:#e8eaf0;--soft:#a2a9b8;--line:#2c303b;--accent:#8b95ff;--ok:#4ade80;--bad:#fb923c;--chip:#262a39}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 "Segoe UI",system-ui,sans-serif}
header{padding:28px 20px 8px;max-width:1100px;margin:auto}h1{margin:0 0 4px;font-size:26px}
.sub{color:var(--soft)}main{max-width:1100px;margin:auto;padding:0 20px 60px}
.how{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin:18px 0}
.how div{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}
.how b{display:block;margin-bottom:4px}kbd{background:var(--chip);border:1px solid var(--line);border-bottom-width:2px;border-radius:6px;padding:1px 7px;font:600 13px Consolas,monospace}
#q{width:100%;padding:12px 14px;font-size:16px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--ink);margin:6px 0 18px}
nav{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px}nav a{background:var(--chip);color:var(--ink);text-decoration:none;padding:4px 10px;border-radius:999px;font-size:13px}
section{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin-bottom:14px}
section h2{margin:0;font-size:18px}section p.i{margin:2px 0 10px;color:var(--soft);font-size:14px}
.r{padding:8px 0;border-top:1px solid var(--line)}.r:first-of-type{border-top:0}.say{font-weight:600}.d{color:var(--soft);font-size:13.5px}
.ex{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}.ex span{background:var(--chip);border-radius:8px;padding:2px 9px;font-size:13.5px}
.ex span::before{content:"“"}.ex span::after{content:"”"}
.recent li{list-style:none;padding:4px 0;border-top:1px solid var(--line)}.recent ul{padding:0;margin:0}
.ok{color:var(--ok)}.bad{color:var(--bad)}.t{color:var(--soft);font-size:12.5px;margin-right:8px}
.hide{display:none}footer{color:var(--soft);font-size:13px;text-align:center;margin-top:30px}
.credit{color:var(--soft);opacity:.6;font-size:11px;text-align:center;margin-top:6px}
</style></head><body>
<header><h1>🎙️ {{APP}}: what you can say</h1>
<div class="sub">Version {{VERSION}} · everything here is checked to work · type below to filter</div></header>
<main>
<div class="how">
 <div><b>1. Hold <kbd>{{KEY}}</kbd> and talk</b>Let go and it runs. A quick tap starts listening, a second tap stops. <kbd>Esc</kbd> cancels.</div>
 <div><b>2. Talk normally</b>"Can you open Spotify please" works. Chain things: "open YouTube and search lofi".</div>
 <div><b>3. Typing instead: <kbd>{{DKEY}}</kbd></b>Hold it and speak: your words are typed where the cursor is. Start with "computer …" to run a command.</div>
 <div><b>Didn't work?</b>Say <i>"check my setup"</i>. To teach it how you talk: <i>"export my voice history"</i>, paste the file into Gemini or ChatGPT, copy the answer, say <i>"import the AI answer"</i>.</div>
</div>
<input id="q" placeholder="Search commands… (spotify, discord, close, timer, volume)" autofocus>
<nav id="nav"></nav><div id="groups"></div>
<section id="recentbox"><h2>🕘 What you said lately</h2><p class="i">✓ ran · ✗ not understood (those are what "export my voice history" sends to the AI)</p><div class="recent"><ul id="recent"></ul></div></section>
<section><h2>🛠️ Setup tips</h2>
<div class="r"><div class="say">Discord inside games</div><div class="d">Discord's own shortcuts only work while Discord is in front, so the agent flicks to Discord and back, which can kick you out of a fullscreen game. Fix: Discord → Settings → Keybinds → add <b>Toggle Mute</b> = <kbd>Ctrl+Shift+Alt+M</kbd> and <b>Toggle Deafen</b> = <kbd>Ctrl+Shift+Alt+D</kbd>, then in the tray menu tick <b>Discord keybinds</b>.</div></div>
<div class="r"><div class="say">"Clip that"</div><div class="d">Needs Instant Replay on: NVIDIA app → Alt+Z → Instant Replay → On. (Using Xbox Game Bar instead? Switch it in the tray menu.)</div></div>
<div class="r"><div class="say">Doesn't react inside a game</div><div class="d">Some games run as administrator, and Windows blocks normal apps from sending keys to them. Right-click the Voice Agent shortcut → Run as administrator.</div></div>
<div class="r"><div class="say">Hears the wrong words</div><div class="d">Use the export-for-AI steps above. Or speak a little slower and closer to the mic, and pick the right mic in the tray menu.</div></div>
</section>
<footer>{{APP}} {{VERSION}} · it updates itself · tray icon → Check for updates</footer>
<div class="credit">made by profane for Billa Janta Party</div>
</main>
<script>
const D={{DATA}};const G=document.getElementById("groups"),N=document.getElementById("nav"),Q=document.getElementById("q");
const esc=s=>s.replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
D.groups.forEach((g,i)=>{const id="g"+i;N.insertAdjacentHTML("beforeend",`<a href="#${id}">${g.icon} ${esc(g.name)}</a>`);
 G.insertAdjacentHTML("beforeend",`<section id="${id}" data-g="${esc(g.name.toLowerCase())}"><h2>${g.icon} ${esc(g.name)}</h2><p class="i">${esc(g.intro)}</p>`+
 g.rules.filter(r=>r.desc||r.examples.length).map(r=>`<div class="r" data-t="${esc((r.say+" "+r.desc+" "+r.examples.join(" ")).toLowerCase())}"><div class="say">${esc(r.say)}</div>`+
 (r.desc?`<div class="d">${esc(r.desc)}</div>`:"")+(r.examples.length?`<div class="ex">${r.examples.map(e=>`<span>${esc(e)}</span>`).join("")}</div>`:"")+`</div>`).join("")+`</section>`)});
const R=document.getElementById("recent");
if(!D.recent.length){document.getElementById("recentbox").classList.add("hide")}
D.recent.forEach(e=>R.insertAdjacentHTML("beforeend",`<li><span class="t">${esc(e.t)}</span><span class="${e.ok?"ok":"bad"}">${e.ok?"✓":"✗"}</span> “${esc(e.heard)}”${e.steps.length?` <span class="t">→ ${esc(e.steps.join(", "))}</span>`:""}</li>`));
function filter(){const q=Q.value.trim().toLowerCase();document.querySelectorAll("#groups section").forEach(s=>{let any=false;
 s.querySelectorAll(".r").forEach(r=>{const hit=!q||r.dataset.t.includes(q)||s.dataset.g.includes(q);r.classList.toggle("hide",!hit);any=any||hit});
 s.classList.toggle("hide",!any)})}
Q.addEventListener("input",filter);if(D.topic){Q.value=D.topic;filter()}
</script></body></html>
"""
