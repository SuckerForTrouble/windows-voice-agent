# Voice Agent bridge for Vesktop

Lets Windows Voice Agent send music bot commands ("bot play kesariya" → `m!play kesariya`) to
your bot channel **while Vesktop stays in the background**: no flick to Discord, your game keeps
focus. Without it, the agent still works: it brings Discord forward for a moment, types the
command into the channel that's open, and goes back.

> [!WARNING]
> Client mods like Vencord (inside Vesktop) and sending messages automatically from your own
> account are both against Discord's terms. Bans for this are rare, and these are a few
> messages you ask for by voice, but the risk isn't zero. It's your account.

What it does, and nothing else:
- listens on your own PC only (127.0.0.1), on a random port, with a secret key written to
  `%LOCALAPPDATA%\WindowsVoiceAgent\discord-bridge.json` for the agent to find;
- sends only what the agent asks for, as you, to the channels in its settings
  (default: `1275456963358232634`), at most 2 messages a second.

## Install (once per PC, about 10 minutes)

Vencord's plugin list doesn't take add-ons like this, so Vencord is built once with it and
Vesktop is pointed at that build.

1. Install **Git** (git-scm.com) and **Node.js LTS** (nodejs.org). Then, in PowerShell:
   ```
   npm install -g pnpm
   ```
2. Get Vencord and its parts:
   ```
   git clone https://github.com/Vendicated/Vencord
   cd Vencord
   pnpm install --frozen-lockfile
   ```
3. Copy this folder, `voiceAgentBridge`, into `Vencord\src\userplugins\` (make `userplugins` if
   it isn't there), so you have `Vencord\src\userplugins\voiceAgentBridge\index.ts`.
4. Build it:
   ```
   pnpm build
   ```
5. In **Vesktop**: Settings → **Vesktop Settings** → find **Vencord Location** (under the
   developer options) → pick the `Vencord\dist` folder. Restart Vesktop.
6. Settings → **Vencord → Plugins** → turn on **VoiceAgentBridge**, restart Vesktop when it asks.
7. Check: the file `%LOCALAPPDATA%\WindowsVoiceAgent\discord-bridge.json` is there while Vesktop
   runs. Say "bot skip": Jockie should skip with Vesktop still in the background.

## Later

- **Another channel**: Vesktop → Settings → Vencord → Plugins → VoiceAgentBridge → the channel
  IDs it may send to; and the same ID in the agent's Settings → Your apps → Bot channel ID.
- **Updating Vencord**: with your own build, Vesktop doesn't update Vencord by itself. Now and then:
  `cd Vencord`, `git pull`, `pnpm install --frozen-lockfile`, `pnpm build`, restart Vesktop.
- **Turning it off**: untick the plugin, or reset Vencord Location in Vesktop's settings.
