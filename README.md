> [!CAUTION]
> # ⚠️ THIS APP IS COMPLETELY VIBE CODED
> **An AI wrote it, and only a very small part of it has been reviewed by a human.**
> It runs on your PC and can close apps, press keys, type, and shut down or restart
> Windows when asked. Automated tests check that commands are understood, not that
> everything is safe or works on your PC.
>
> **Install and use it entirely at your own risk.**

# 🎙️ Windows Voice Agent

Talk to your PC. **Hold F9, say what you want, let go.**

"Open Spotify" · "close discord" (even behind your game) · "quit steam from the tray" ·
"watch interstellar" (opens it in Stremio) · "mute me on discord" · "clip that" ·
"scroll instagram for me" · "set a 10 minute timer" · "what's using my RAM" · "brave, search cats" ·
"answer the phone" · and about 170 more.

Speech recognition runs **on your own PC**, on your NVIDIA graphics card, so it's fast and
your voice never leaves the computer.

---

## Install (2 minutes)

1. **[Download WindowsVoiceAgent-Setup.exe](https://github.com/SuckerForTrouble/windows-voice-agent/releases/latest/download/WindowsVoiceAgent-Setup.exe)**
2. Run it. If Windows says **"Windows protected your PC"**, click **More info → Run anyway**.
   (The app isn't signed with a paid certificate; that's all the warning means.)
3. Click **Install**. It starts by itself.
4. A **welcome window** opens: pick your talk key (a mouse side button works too), the speech
   model (**Parakeet** is the fastest), the pill style and your music / movie / browser apps.
   Or just click **Start**.
5. It downloads the speech model you picked, once. A small bar at the top of the screen shows how far along it is.
6. Two pages open when it's ready:
   - **Setup check**: everything with a ✗ or ! says exactly what to do. It also times the model on your PC.
   - **Voice guide**: everything you can say, with examples.

That's it. It starts with Windows and **updates itself**.

## Using it

| | |
|---|---|
| **Hold F9**, talk, let go | runs the command |
| **Tap F9**, talk, tap F9 again | same, hands free |
| **Esc** while it's listening | cancel |
| **Hold F10** and talk | types what you say where your cursor is (start with "computer …" to run a command instead) |
| Say **"what can I say"** | opens the voice guide |
| Say **"check my setup"** | tests everything again |

The **tray icon** (by the clock, maybe behind the **^** arrow) shows what it's doing:
🔵 ready · 🔴 listening · 🟠 thinking · ⚪ loading.

## Settings: click the tray icon

Click the icon (left or right) and a small **panel** opens above it, Windows 11 style:
what it's doing and what it uses, switches for **Always listening**, **Pause**, **Spoken answers**
and **Beeps**, the **pill style**, your **microphone**, the **speech model**, and buttons for
*What can I say?*, *Settings…* and *Check setup*. Click anywhere else (or Esc) to close it.
**More options…** at the bottom opens the full menu:

Out of the box it's the light setup: push-to-talk, the pill at the top of the screen, and beeps.
Everything else is off until you tick it.

| Menu | What's there |
|---|---|
| **Settings…** | The same window as on the first start: talk keys (or a mouse side button), speech model, pill style, **your apps** (what "play …" uses: Spotify, YouTube Music or YouTube; what "watch …" uses: Stremio, Netflix or Prime Video; which browser "open browser" opens), always listening and its call word, and the extras. |
| **Pause for now** | Keys and mic off until you untick it (a competitive game that wants F9, a meeting). |
| **Always listening** | No key: say your **call word** first ("Angel, open Spotify"). Several work, with commas: "Angel, Jarvis". The mic stays on, and anything that doesn't start with a call word is thrown away unseen (needs a model on your PC, not cloud). |
| **Pill on screen** | Off, Minimal, Advanced (mic meter and timing) or Funky. |
| **Speech model** | **Parakeet** (fastest: about a tenth of a second per command, even without a GPU; English) and **Best / Balanced / Fast** (Whisper; Best also does Hindi typing), each with its memory use and download size. The top line shows what the one in use *really* uses on your PC, and how long your last command took. Also **cloud** speech (Groq or OpenAI, your own API key, stored encrypted; your recordings go to them), and **Delete unused models**. |
| **Microphone** | Pick which mic it listens to. |
| **More options** | Push-to-talk keys, call words, typing language (**Hindi**), spoken answers, beeps, timing in the pill, **free the GPU while a game runs** (on: the model steps out of graphics memory while a game runs and loads back while you talk), Discord keybinds, clips with NVIDIA or Xbox, start with Windows, update by itself, and **commands from Discord audio** (dangerous, see below). |
| **Help** | Check my setup, teach it your voice (the AI trick below), check for updates, logs. |

Talk normally. "Can you open YouTube and search for lofi beats please" works. So does
chaining: "new tab, type hello, press enter".

## Make it understand *you* better

It learns by itself as you use it:

- **Say it again.** When it doesn't get something and you say it differently within 10 seconds,
  it remembers what you meant: straight away when the two sound alike ("open spotty" → "open
  Spotify"), otherwise the second time it happens. The pill says **"Learned: … means …"**. Say
  **"forget that"** right after to undo it.
- **"No, that's wrong"** right after a command it got wrong, then say it again: that's learned too
  (the second time, so one slip can't change a command that works).
- **"Did you mean?"**: when nothing fits, it shows the closest commands. Say **"the first one"**
  (that's learned on the spot). When one is very close it just runs it, and the pill says
  "Took it as …". It never guesses its way into shutting down, restarting or quitting apps.
- **Names heard a little wrong** still work: "open vesk top", "launch dead lock", "close spottify".
- With a Whisper model it listens a second time, more carefully, before saying it didn't
  understand, and it's told your call words, your games and the commands you use most.

Everything it learns goes into your tuning file (tray → Help → Teach it my voice → Open my
tuning file), where you can also delete a line by hand.

For a bigger clean-up, any free AI can go through everything it didn't understand. The agent
keeps that list on your PC only:

1. Say **"export my voice history"** (or tray → Teach it my voice → 1). A file called
   `tune-me.txt` opens. It's also on your Desktop.
2. Select all of it (Ctrl+A), copy, and paste it into **Gemini**, **ChatGPT** or any AI chat. Send.
3. Copy the AI's whole answer.
4. Say **"import the AI answer"** (or tray → Teach it my voice → 2).

Each fix is checked before it's used, so a bad answer can't break anything. Do it again
every week or two.

## Some setup for the best experience

- **Discord inside games** ("mute me on Discord", "deafen"): it depends which Discord you use.
  The setup check tells you which one it found.
  - **Equibop**: works straight away, even in games: it takes a mute command from outside.
  - **Discord** (also with **Vencord** or **Equicord**): Discord → Settings → Keybinds → add
    **Toggle Mute** = `Ctrl+Shift+Alt+M` and **Toggle Deafen** = `Ctrl+Shift+Alt+D`, then tray →
    More options → tick **Discord keybinds**. Without that, the agent flicks to Discord and back,
    which can pull you out of a fullscreen game.
  - **Vesktop**: it can only flick to it and back (no global keybinds or mute command on Windows).
    For in-game mute, Equibop is a Vesktop fork that has one.
- **Spotify** (free accounts too): "play blinding lights" flicks to Spotify for a second, runs its
  quick search (Ctrl+K) and plays the top result, then comes back. Pause / play / next / previous
  go through Windows' media controls and never pop it up.
- **"Clip that"**: turn on Instant Replay in the NVIDIA app (press `Alt+Z` → Instant Replay).
  Using Xbox Game Bar instead? Tray → More options → Clips with → Xbox Game Bar.
- **Typing in Hindi**: tray → More options → Typing language → Hindi (needs the **Best**
  model or cloud). Commands stay English, but Hinglish works through the AI trick:
  `say: spotify kholo -> open spotify`.
- **Stremio**: install the [Stremio app](https://www.stremio.com/downloads). Without it, movies open on web.stremio.com.
- **Files by name** ("find the file budget", "open my chemistry assignment"): misspelled, shortened
  or sound-alike names still work ("budjet", "assgnmt", "fizzics"). It looks in your own folders,
  the files you opened lately (any drive) and Windows' search index. When a few fit about as well,
  the pill lists them: say **"the second one"**. It remembers that pick next time.
- **Headphones and speakers**: "switch to my headphones", "headphones volume 30", "list audio
  devices" (then "the second one"), "which output am I using". **"Spotify on the speakers"**
  sends just one app's sound to one device. That last one uses an undocumented part of Windows
  (the one EarTrumpet uses), so a big Windows update may break it. The setup check says if it works.
- **Bluetooth**: "connect my earbuds" opens Windows' Bluetooth list, and you tap the device (connecting
  by voice alone isn't reliable on Windows). "Earbuds battery" reads the battery level of connected
  headphones and controllers that report one.
- **A browser by name**: say it first and the rest happens in that browser: "brave, search cats",
  "in edge open youtube", "chrome new tab", "firefox, go back". At the end works for opening things:
  "open youtube in brave", "open spotify in firefox" (its web player). "Brave settings" opens the browser's
  own settings page. Chrome, Edge, Firefox, Brave, Opera / Opera GX, Zen and Vivaldi.
- **Phone calls from the PC (Phone Link)**: set up Windows' **Phone Link** app with your phone once,
  including **Calls** (it pairs over Bluetooth, so the PC becomes your phone's hands-free set and the
  call's sound comes out of the PC). Then: "answer the phone", "decline the call", "hang up",
  "mute the call", "move the call to my phone", "call 98765 43210", "call mom", "text rahul",
  "open my phone's messages / photos", "mirror my phone", "clear my phone notifications".
  What to know:
  - Windows lets no app answer calls directly, so the agent presses Phone Link's own **Accept** /
    **Decline** buttons (through Windows' accessibility interface; it looks at button names only and
    keeps nothing). "Hang up" and "mute the call" use Phone Link's own keys (Ctrl+Shift+H, Ctrl+Shift+M).
  - While a phone call rings, "answer the call" means it; otherwise it means Discord's call.
  - "Call 98765…" sends the number to Phone Link. The first time, Windows may ask which app should
    make calls: pick **Phone Link** and tick **Always**.
  - "Call mom" and "text rahul" type the name into **Phone Link's** search, and you press call or
    write the message. The agent never reads your contacts, messages, photos or call history.
  - Answering by voice hasn't been tried with a real phone yet: if it says no call is ringing while one
    is, click Accept yourself and send the log to whoever gave you this.
- **The pill over games**: it shows over games in borderless or windowed mode, and over "fullscreen"
  games that Windows runs with fullscreen optimizations, which is most of them on Windows 10 and 11.
  A game in true **exclusive fullscreen** owns the screen: nothing can be drawn over it without hooking
  into the game itself, which anti-cheat treats as cheating, so the agent never does that. It notices
  when that happens: answers are then **said out loud** (even with spoken answers off), and a command
  it didn't understand beeps. Want the pill? Switch the game to borderless in its video settings.

## ⚠️ Commands from Discord audio (dangerous, off by default)

Tray → More options → **Commands from Discord audio**. While it's on, what your Discord call plays is
listened to like Always listening: when someone in the call says the call word ("Angel, open
Spotify"), **the command runs on your PC**. A window explains the risk first, and you have to tick a
box before the red button works.

- **Anyone in the call can do anything you can by voice**: close your game, type, press keys, open
  websites, shut down or restart the PC. **Nothing is blocked or filtered.** A troll, a soundboard or
  a video someone streams can do it too. Use it only with people you trust completely.
- It **turns off whenever the agent restarts** and is never saved. Untick it in the tray to stop sooner.
  It also stops when Discord closes or you pause the agent.
- The pill marks those commands **FROM DISCORD**, so you know it wasn't you.
- On **Windows 11** it hears Discord only. On **Windows 10** Windows can't separate one app's sound, so
  it hears everything the PC plays (games, videos, music) and a video saying the call word counts too.
- It needs a speech model on your PC: your friends' voices are never sent to a cloud model.

## When something's off

- **Nothing happens when I press F9**: say or click "check my setup". If another app uses F9:
  tray → Push-to-talk keys → click it, and press another key (or pick a mouse side button).
- **"Open Instagram" opens the website**: it opens the Instagram app if one is installed from the
  Microsoft Store (same for Netflix, ChatGPT…). "Scroll Instagram" uses the website's Reels page;
  in the app, open Reels yourself and say "doom scroll".
- **It hears the wrong words**: say "check my setup" and look at the **Microphone** line: it records
  the room for 3 seconds and says if your voice comes through too quiet, distorted or under a lot of
  noise, and what to do. Laptop mics (a "Microphone Array") hear the fans and keyboard: a headset mic
  is far better. With an **NVIDIA RTX** card, the free **NVIDIA Broadcast** app removes background
  noise: install it, then tray → Microphone → "Microphone (NVIDIA Broadcast)". Also check the right
  mic is picked (tray → Microphone), and do the AI trick above.
- **It cuts off my last word**: it already keeps listening 0.3 s after you let go. Let go a moment later.
- **Commands do nothing inside one particular game**: that game runs as administrator. Right-click
  the Windows Voice Agent shortcut → Run as administrator.
- **Slow** (the setup check's **Speed** line): it times the model on a sample sentence three times
  and shows the first and the best try. A slow first try is the graphics card getting ready; that now
  happens while the agent starts. If the GPU is still slow, the check also times the CPU and switches
  to it when that's faster (it says so). Laptops: plug in, because on battery the GPU slows right
  down. Also update the NVIDIA driver, and close heavy apps. Still slow? Tray → Speech model →
  **Parakeet** (the fastest), or send the logs folder: it lists the graphics cards and every command's
  timing. A laptop with two graphics chips can be pointed at one by its number in `logs\parakeet.log`
  (`ggml_vulkan: 0 = …`): put `"gpu_device": "1"` in the settings file (tray → Help → Open the settings file).
- **The first command in a game takes a few seconds**: that's the model loading back after it
  stepped out of graphics memory for the game. Rather keep it loaded? Tray → More
  options → untick "Free the GPU while a game runs".
- **Antivirus complains**: apps built with Python sometimes get flagged by mistake. Allow it.
- **Send a log to whoever gave you this**: tray → More → Open data folder → `logs`.

**Uninstall**: Windows Settings → Apps → Windows Voice Agent → Uninstall. Your settings,
history and the speech model stay in `%LOCALAPPDATA%\WindowsVoiceAgent`. Delete that folder
to remove them too.

## Coming later

- 🎵 **Spotify without the one-second flick**: playing a song silently needs Spotify Premium and a one-time login
- 🗣️ **Hindi voice commands**: say commands in Hindi, not just type in it
- ⚡ **More speed tuning**: from your setup check's Speed line

## Privacy

- What you say is turned into text **on your PC**. No audio is ever uploaded.
- The mic is only open while you hold (or have tapped) the key, unless you turn on
  **Always listening**. Then it stays open, but a phrase that doesn't start with your call word is
  dropped on the spot: never shown, saved or logged. **Commands from Discord audio** work the same way
  with what Discord plays, and never with a cloud model.
- Phone Link: the agent never reads your contacts, messages, photos or call history. To answer a call
  it looks for the Accept button by name, and nothing it sees is kept.
- The voice history stays on your PC. It only goes anywhere if *you* export it and paste it into an AI.
- The app goes online only to download the speech model, check GitHub for updates, get the
  weather (wttr.in), look up movie names for Stremio (Stremio's own catalog), and open what you ask for.

---

## For the maintainer

**Ship an update to everyone** (from Linux, no Windows needed):

```bash
./release.sh
```

That runs the tests, bumps the version, tags and pushes. GitHub Actions builds the Windows
app on a Windows machine, compiles whisper.cpp for the GPU (Vulkan), runs a self-test
(every example phrase routes, and the built app transcribes `tests/data/open_spotify.wav`),
builds the installer and publishes the release. Updates are checked 20 s after the app starts and then every 6 hours. Installed copies update themselves.
`./release.sh minor` for a bigger bump. Test build without releasing: Actions → Build &
release → Run workflow (the installer is attached to the run).

**Work on commands** (Linux is fine, nothing here needs Windows):

```bash
python3 tests/test_routing.py              # every example in wva/examples.py must route
python3 -m wva --try "close discord"       # what a phrase would do (nothing runs)
python3 -m wva --list                      # every command
```

| File | What's in it |
|---|---|
| `wva/engine.py` | transcript → commands: mishearing fixes, filler stripping, chains, matching |
| `wva/rules.py` | every command: phrasings → action, in priority order |
| `wva/examples.py` | example phrases: the tests and the voice guide both use them |
| `wva/actions.py`, `extras.py`, `system.py` | what commands do on Windows (Spotify, Discord, Stremio… in `extras`) |
| `wva/apps.py` | open/close by name: Start menu, Store apps, Steam/Epic games, sites, process names, a browser by name |
| `wva/phone.py` | Phone Link: answer / decline / hang up (UI Automation + its own keys), call, text, its pages |
| `wva/listen.py`, `loopback.py` | always listening and call words; commands from Discord audio (WASAPI loopback) |
| `wva/learn.py` | learning from retries, "did you mean?", "no, that's wrong", "forget that" |
| `wva/app.py` | the running agent: tray, keys, mic → whisper → commands |
| `wva/stt.py` | speech models: whisper-server and our parakeet-server (`native/`, both GPU via Vulkan with a CPU fallback), cloud, model downloads |
| `wva/guide.py`, `checkup.py`, `tuning.py` | voice guide, setup check, AI tuning export/import |
| `wva/updater.py`, `installer/wva.iss` | self-update from GitHub releases, the installer |

<p align="center"><sub>made by profane for Billa Janta Party</sub></p>
