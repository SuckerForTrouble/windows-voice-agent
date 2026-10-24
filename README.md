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
🔵 ready · 🔴 listening · 🟠 thinking · ⚪ loading. Right-click it for every setting:
microphone, spoken answers, beeps, Discord keybinds, clips, start with Windows.

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
  `Ctrl+Shift+Alt+D`, then tray → Settings → tick **Discord keybinds**.
- **"Clip that"**: turn on Instant Replay in the NVIDIA app (press `Alt+Z` → Instant Replay).
  Using Xbox Game Bar instead? Tray → Settings → Clips with Xbox Game Bar.
- **Stremio**: install the [Stremio app](https://www.stremio.com/downloads). Without it, movies open on web.stremio.com.

## When something's off

- **Nothing happens when I press F9**: say or click "check my setup". If another app uses F9,
  tray → Settings → Open the settings file, change `"agent_key": "f9"` to e.g. `"f8"` or
  `"ctrl+alt+space"`, save, then tray → Restart.
- **It hears the wrong words**: do the AI trick above, and check the right mic is picked (tray → Microphone).
- **Commands do nothing inside one particular game**: that game runs as administrator. Right-click
  the Windows Voice Agent shortcut → Run as administrator.
- **Slow, or "running on the CPU" in the setup check**: update your NVIDIA driver and restart
  the agent. Still slow? Tray → Settings → Open the settings file → change `"model"` to
  `"small.en-q5_1"`, save, restart (smaller and faster, a bit less accurate).
- **Antivirus complains**: apps built with Python sometimes get flagged by mistake. Allow it.
- **Send a log to whoever gave you this**: tray → Open data folder → `logs`.

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
builds the installer and publishes the release. Installed copies update themselves.
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
| `wva/stt.py` | whisper-server (Vulkan GPU build, CPU fallback), model download |
| `wva/guide.py`, `checkup.py`, `tuning.py` | voice guide, setup check, AI tuning export/import |
| `wva/updater.py`, `installer/wva.iss` | self-update from GitHub releases, the installer |
