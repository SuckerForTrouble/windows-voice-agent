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
4. The first start downloads the speech model (**about 550 MB**). A small bar at the top of
   the screen shows how far along it is.
5. Two pages open when it's ready:
   - **Setup check**: everything with a ✗ or ! says exactly what to do.
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

## Settings: right-click the tray icon

Out of the box it's the light setup: push-to-talk, the pill at the top of the screen, and beeps.
Everything else is off until you tick it.

| Menu | What's there |
|---|---|
| **Push-to-talk keys** | Click one, press the key you want (F8, Pause, Ctrl+Alt+Space…), or pick a **mouse side button** (back / forward). Works straight away. |
| **Speech model** | **Fast / Balanced / Best** (Whisper) and **Parakeet** (fastest: about a tenth of a second per command even without a GPU; English, no Hindi), each with its memory use and download size. The top line shows what the one in use *really* uses on your PC, and how long your last command took. Also **cloud** speech (Groq or OpenAI, your own API key, stored encrypted; your recordings go to them), and **Delete unused models**. |
| **Microphone** | Pick which mic it listens to. |
| **Optional features** | Spoken answers · the pill and its **style** (Minimal, Advanced with a mic meter and timing, or Funky) · beeps · how long each command took · **free the GPU while a game runs** (on: the model leaves graphics memory when a game starts, and loads back while you talk when you press the key) · typing language (**Hindi**) · Discord keybinds · clips with NVIDIA or Xbox. |
| **Teach it my voice** | The AI trick below. |

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

- **Discord inside games**: Discord's shortcuts only work while Discord is in front, so the
  agent flicks to Discord and back, which can pull you out of a fullscreen game. Fix: Discord →
  Settings → Keybinds → add **Toggle Mute** = `Ctrl+Shift+Alt+M` and **Toggle Deafen** =
  `Ctrl+Shift+Alt+D`, then tray → Optional features → tick **Discord keybinds**.
- **"Clip that"**: turn on Instant Replay in the NVIDIA app (press `Alt+Z` → Instant Replay).
  Using Xbox Game Bar instead? Tray → Optional features → Clips with → Xbox Game Bar.
- **Typing in Hindi**: tray → Optional features → Typing language → Hindi (needs the **Best**
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
  stepped out of graphics memory for the game. Rather keep it loaded? Tray → Optional
  features → untick "Free the GPU while a game runs".
- **Antivirus complains**: apps built with Python sometimes get flagged by mistake. Allow it.
- **Send a log to whoever gave you this**: tray → More → Open data folder → `logs`.

**Uninstall**: Windows Settings → Apps → Windows Voice Agent → Uninstall. Your settings,
history and the speech model stay in `%LOCALAPPDATA%\WindowsVoiceAgent`. Delete that folder
to remove them too.

## Privacy

- What you say is turned into text **on your PC**. No audio is ever uploaded.
- The mic is only open while you hold (or have tapped) the key.
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
