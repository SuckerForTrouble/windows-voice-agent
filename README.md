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
"scroll instagram for me" · "set a 10 minute timer" · "what's using my RAM" · and about 150 more.

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
| **Always listening** | No key: say your **call word** first ("Jarvis, open Spotify"). The mic stays on, and anything that doesn't start with the call word is thrown away unseen (needs a model on your PC, not cloud). |
| **Pill on screen** | Off, Minimal, Advanced (mic meter and timing) or Funky. |
| **Speech model** | **Parakeet** (fastest: about a tenth of a second per command, even without a GPU; English) and **Best / Balanced / Fast** (Whisper; Best also does Hindi typing), each with its memory use and download size. The top line shows what the one in use *really* uses on your PC, and how long your last command took. Also **cloud** speech (Groq or OpenAI, your own API key, stored encrypted; your recordings go to them), and **Delete unused models**. |
| **Microphone** | Pick which mic it listens to. |
| **More options** | Push-to-talk keys, call word, typing language (**Hindi**), spoken answers, beeps, timing in the pill, **free the GPU while a game runs** (on: the model steps out of graphics memory while a game runs and loads back while you talk), Discord keybinds, clips with NVIDIA or Xbox, start with Windows, update by itself. |
| **Help** | Check my setup, teach it your voice (the AI trick below), check for updates, logs. |

Talk normally. "Can you open YouTube and search for lofi beats please" works. So does
chaining: "new tab, type hello, press enter".

## Make it understand *you* better

Everyone's accent is different. The agent keeps a list (on your PC only) of what it
didn't understand. Any free AI can turn that into fixes:

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

## When something's off

- **Nothing happens when I press F9**: say or click "check my setup". If another app uses F9:
  tray → Push-to-talk keys → click it, and press another key (or pick a mouse side button).
- **"Open Instagram" opens the website**: it opens the Instagram app if one is installed from the
  Microsoft Store (same for Netflix, ChatGPT…). "Scroll Instagram" uses the website's Reels page;
  in the app, open Reels yourself and say "doom scroll".
- **It hears the wrong words**: do the AI trick above, and check the right mic is picked (tray → Microphone).
- **Commands do nothing inside one particular game**: that game runs as administrator. Right-click
  the Windows Voice Agent shortcut → Run as administrator.
- **Slow, or "running on the CPU" in the setup check**: update your NVIDIA driver and restart
  the agent. The setup check's **Speed** line shows how long commands take. Still slow?
  Tray → Speech model → **Parakeet** (the fastest), or **Balanced** / **Fast**.
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
  dropped on the spot: never shown, saved or logged.
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
| `wva/apps.py` | open/close by name: Start menu, Store apps, Steam/Epic games, sites, process names |
| `wva/app.py` | the running agent: tray, keys, mic → whisper → commands |
| `wva/stt.py` | speech models: whisper-server and our parakeet-server (`native/`, both GPU via Vulkan with a CPU fallback), cloud, model downloads |
| `wva/guide.py`, `checkup.py`, `tuning.py` | voice guide, setup check, AI tuning export/import |
| `wva/updater.py`, `installer/wva.iss` | self-update from GitHub releases, the installer |

<p align="center"><sub>made by profane for Billa Janta Party</sub></p>
