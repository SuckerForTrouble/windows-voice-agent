"""The voice guide: one page with every command and examples that are known to
work (they are the tests), what you said lately, and first-day tips. Opened by
"help", "what can I say", "help with spotify", or the tray. Regenerated each time,
so it always matches this version and your own history."""
import html
import json
import os
import re

from . import APP_NAME, __version__, config, history, hotkey, paths
from .engine import CTX, RULES

# icon, a few plain words (the guide is for skimming: say less)
GROUP_INFO = {
    "Open & search": ("🚀", "Open any app, game or website. Search anything."),
    "Files & folders": ("📁", "Your newest download, any file by name, deep folders."),
    "Close & switch apps": ("🪟", "Close apps, even the ones hiding behind your game."),
    "Spotify": ("🎵", "Control Spotify from anywhere."),
    "Discord": ("💬", "Mute, deafen, answer calls."),
    "Stremio & watching": ("🎬", "Say a movie or show, it opens."),
    "Reels & Shorts": ("📱", "Scroll reels without touching anything."),
    "YouTube": ("▶️", "When a YouTube video is open."),
    "Gaming": ("🎮", "Clip it, record it, show FPS."),
    "Sound & media": ("🔊", "Volume, pause, next song."),
    "App volume": ("🎚️", "Just one app louder or quieter."),
    "Browser": ("🌐", "Tabs, scrolling, zoom."),
    "Keyboard": ("⌨️", "Type words, press keys."),
    "Windows": ("🖥️", "Snap, resize, minimise windows."),
    "System": ("⚙️", "Screenshot, lock, sleep, Wi-Fi."),
    "Info": ("ℹ️", "Ask the time, weather, RAM."),
    "Timers": ("⏱️", "Set timers by voice."),
    "Voice agent": ("🧭", "Help, setup check, updates."),
}
# What's planned, shown folded at the bottom of the guide (keep README.md's list the same).
ROADMAP = [('🎵', 'Spotify without the one-second flick', 'playing a song silently needs Spotify Premium and a one-time login'),
           ('🗣️', 'Hindi voice commands', 'say commands in Hindi, not just type in it'),
           ('⚡', 'More speed tuning', "from your setup check's Speed line")]
# The first things to try. Each one is checked by the tests (tests/test_routing.py).
STARTERS = [("🎵", "Open Spotify"), ("🪟", "Close Discord"), ("🔊", "Volume 30"), ("🎬", "Watch Interstellar"),
            ("⏱️", "Set a 10 minute timer"), ("⏭️", "Next song"), ("📸", "Take a screenshot"), ("🕒", "What time is it")]
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
    key = hotkey.label(config.get("agent_key"))
    dkey = hotkey.label(config.get("dictate_key"))
    data = {"groups": groups(), "recent": _recent(), "topic": topic or "", "starters": STARTERS, "roadmap": ROADMAP}
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
:root{--bg:#f4f5fa;--card:#fff;--ink:#161a24;--soft:#5d6577;--line:#e2e5ee;--accent:#4f5bd5;--accent2:#e8eaff;--ok:#1f8a4c;--bad:#c2410c;--chip:#eef0fb}
@media (prefers-color-scheme:dark){:root{--bg:#121419;--card:#1c1f28;--ink:#eef0f5;--soft:#a2a9b8;--line:#2b2f3a;--accent:#8b95ff;--accent2:#262a45;--ok:#4ade80;--bad:#fb923c;--chip:#262a39}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.5 "Segoe UI",system-ui,sans-serif}
main{max-width:880px;margin:auto;padding:28px 20px 60px}
h1{font-size:34px;margin:0}h2{font-size:21px;margin:0}.sub{color:var(--soft);margin:4px 0 22px}
kbd{display:inline-block;background:var(--card);border:2px solid var(--line);border-bottom-width:4px;border-radius:10px;padding:2px 12px;font:700 20px "Segoe UI",sans-serif}
.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.step{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px 16px;text-align:center}
.step .n{display:inline-grid;place-items:center;width:34px;height:34px;border-radius:50%;background:var(--accent);color:#fff;font-weight:700;margin-bottom:10px}
.step b{display:block;font-size:22px;margin:8px 0 2px}.step span{color:var(--soft);font-size:15px}
.also{color:var(--soft);text-align:center;margin:14px 0 30px;font-size:15px}.also kbd{font-size:14px;padding:0 8px;border-width:1px 1px 3px}
.try{display:flex;flex-wrap:wrap;gap:10px;margin:12px 0 30px}
.try span{background:var(--accent2);border-radius:999px;padding:9px 16px;font-size:17px;font-weight:600}
#q{position:sticky;top:10px;z-index:2;width:100%;padding:14px 18px;font-size:18px;border-radius:14px;border:2px solid var(--line);background:var(--card);color:var(--ink);margin:0 0 16px;box-shadow:0 4px 18px rgba(0,0,0,.06)}
#q:focus{outline:none;border-color:var(--accent)}
#groups{display:flex;flex-direction:column}
details{background:var(--card);border:1px solid var(--line);border-radius:16px;margin-bottom:10px}
summary{list-style:none;cursor:pointer;padding:16px 18px;display:flex;align-items:center;gap:14px}
summary::-webkit-details-marker{display:none}
summary .ic{font-size:26px;width:34px;text-align:center}summary .nm{font-weight:700;font-size:18px}
summary .ds{color:var(--soft);font-size:15px}summary .ct{margin-left:auto;color:var(--soft);font-size:14px;white-space:nowrap}
summary .ct::after{content:"  ▸";}details[open] summary .ct::after{content:"  ▾"}
.r{padding:12px 18px 12px 66px;border-top:1px solid var(--line)}
.say{font-size:19px;font-weight:600}.say::before{content:"“";color:var(--accent)}.say::after{content:"”";color:var(--accent)}
.d{color:var(--soft);font-size:15px}.alt{color:var(--soft);font-size:14px;margin-top:2px}
.k{float:right;font:600 12px Consolas,monospace;color:var(--soft);background:var(--chip);border-radius:6px;padding:2px 7px;margin-left:10px}
.stuck{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px 20px;margin:26px 0 12px}
.stuck div{padding:6px 0;font-size:17px}.stuck b{display:inline-block;min-width:190px}
.more summary .nm{font-size:16px}.more .r{padding-left:22px}.more .say::before,.more .say::after{content:none}
.recent li{list-style:none;padding:6px 18px;border-top:1px solid var(--line);font-size:15px}.recent ul{padding:0;margin:0}
.ok{color:var(--ok)}.bad{color:var(--bad)}.t{color:var(--soft);font-size:13px;margin-right:8px}
.hide{display:none}mark{background:var(--accent2);color:inherit;border-radius:4px}
footer{color:var(--soft);font-size:13px;text-align:center;margin-top:30px}
.credit{color:var(--soft);opacity:.6;font-size:11px;text-align:center;margin-top:6px}
@media (max-width:620px){.steps{grid-template-columns:1fr}.r{padding-left:18px}summary .ds{display:none}}
</style></head><body><main>
<h1>🎙️ Talk to your PC</h1>
<div class="sub">Three steps. That's all.</div>
<div class="steps">
 <div class="step"><div class="n">1</div><br><kbd>{{KEY}}</kbd><b>Hold it</b><span>a quick tap works too</span></div>
 <div class="step"><div class="n">2</div><br><span style="font-size:30px">🗣️</span><b>Say it</b><span>talk normally</span></div>
 <div class="step"><div class="n">3</div><br><span style="font-size:30px">✋</span><b>Let go</b><span>it does it</span></div>
</div>
<div class="also">Want it to <b>type</b> instead? Hold <kbd>{{DKEY}}</kbd>. Changed your mind? <kbd>Esc</kbd></div>

<h2>Try these first</h2>
<div class="try" id="try"></div>

<input id="q" placeholder="🔍  What do you want to do?  (spotify, close, volume, timer…)" autofocus>
<div id="groups"></div>

<div class="stuck"><h2>Stuck?</h2>
 <div><b>Nothing happens</b> say <i>“check my setup”</i></div>
 <div><b>It hears wrong words</b> tray icon → Teach it my voice</div>
 <div><b>Want a setting</b> click the tray icon by the clock</div>
</div>

<details class="more"><summary><span class="ic">🛠️</span><span class="nm">Setup tips</span><span class="ct">6 tips</span></summary>
<div class="r"><div class="say">Mute me on Discord</div><div class="d"><b>Equibop</b>: works inside games as it is. <b>Discord</b> (also with Vencord or Equicord): add the keybinds Toggle Mute = <b>Ctrl+Shift+Alt+M</b> and Toggle Deafen = <b>Ctrl+Shift+Alt+D</b> in Discord → Settings → Keybinds, then tray → More options → tick <b>Discord keybinds</b>. <b>Vesktop</b>: flicks to it and back (it has no mute command). The setup check says which one you have.</div></div>
<div class="r"><div class="say">Clip that</div><div class="d">Turn on Instant Replay: press <b>Alt+Z</b> in the NVIDIA app. Xbox Game Bar instead? Tray → More options → Clips with.</div></div>
<div class="r"><div class="say">Doesn't work in one game</div><div class="d">That game runs as admin. Right-click the Voice Agent shortcut → Run as administrator.</div></div>
<div class="r"><div class="say">Jarvis, open Spotify</div><div class="d">No key at all: tray → Always listening (pick the call word in Settings…). The mic stays on; anything that doesn't start with the call word is thrown away unseen.</div></div>
<div class="r"><div class="say">Other key, mouse button, faster model, your apps, Hindi</div><div class="d">Click the tray icon → Settings…. Everything extra is off until you turn it on.</div></div>
<div class="r"><div class="say">Hears me wrong</div><div class="d">Say “export my voice history”, paste the file into Gemini or ChatGPT, copy its answer, say “import the AI answer”.</div></div>
</details>
<details class="more"><summary><span class="ic">🗺️</span><span class="nm">Coming later</span><span class="ct" id="rmc"></span></summary>
<div id="roadmap"></div></details>
<details class="more" id="recentbox"><summary><span class="ic">🕘</span><span class="nm">What you said lately</span><span class="ct" id="rc"></span></summary>
<div class="recent"><ul id="recent"></ul></div></details>

<footer>{{APP}} {{VERSION}} · updates itself · vibe coded, use at your own risk</footer>
<div class="credit">made by profane for Billa Janta Party</div>
</main>
<script>
const D={{DATA}};const G=document.getElementById("groups"),Q=document.getElementById("q");
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const KEYS=/^(?:[A-Z][a-z]*\+)+\w+|^F\d+$|^(?:Ctrl|Alt|Win|Shift|Home|End|Page|F\d)/;
D.starters.forEach(([i,t])=>document.getElementById("try").insertAdjacentHTML("beforeend",`<span>${i} ${esc(t)}</span>`));
D.groups.forEach((g,gi)=>{
 const rows=g.rules.filter(r=>r.examples.length||r.desc).map(r=>{
  const ex=r.examples.length?r.examples:[r.say];const keyish=r.desc&&KEYS.test(r.desc)&&r.desc.length<40;
  return `<div class="r" data-t="${esc((r.say+" "+r.desc+" "+ex.join(" ")+" "+g.name).toLowerCase())}">`+
   (keyish?`<span class="k">${esc(r.desc)}</span>`:"")+`<div class="say">${esc(ex[0])}</div>`+
   (r.desc&&!keyish?`<div class="d">${esc(r.desc)}</div>`:"")+
   (ex.length>1?`<div class="alt">or: ${ex.slice(1,3).map(e=>"“"+esc(e)+"”").join(" · ")}</div>`:"")+`</div>`}).join("");
 G.insertAdjacentHTML("beforeend",`<details data-g="${esc(g.name.toLowerCase())}"><summary><span class="ic">${g.icon}</span>`+
  `<span><span class="nm">${esc(g.name)}</span><br><span class="ds">${esc(g.intro)}</span></span>`+
  `<span class="ct">${g.rules.length} things</span></summary>${rows}</details>`)});
document.getElementById("rmc").textContent=D.roadmap.length+" planned";
D.roadmap.forEach(([i,t,d])=>document.getElementById("roadmap").insertAdjacentHTML("beforeend",
 `<div class="r"><div style="font-weight:600;font-size:17px">${i} ${esc(t)}</div><div class="d">${esc(d)}</div></div>`));
const R=document.getElementById("recent");
if(!D.recent.length){document.getElementById("recentbox").classList.add("hide")}
document.getElementById("rc").textContent=D.recent.length+" lately";
D.recent.forEach(e=>R.insertAdjacentHTML("beforeend",`<li><span class="t">${esc(e.t)}</span><span class="${e.ok?"ok":"bad"}">${e.ok?"✓":"✗"}</span> “${esc(e.heard)}”</li>`));
function filter(){const q=Q.value.trim().toLowerCase();
 document.querySelectorAll("#groups details").forEach(s=>{let any=false;
  s.querySelectorAll(".r").forEach(r=>{const hit=!q||r.dataset.t.includes(q);r.classList.toggle("hide",!hit);any=any||hit});
  s.classList.toggle("hide",!any);s.open=!!q&&any;s.style.order=q&&s.dataset.g.includes(q)?0:1})}
Q.addEventListener("input",filter);if(D.topic){Q.value=D.topic;filter()}
</script></body></html>
"""
