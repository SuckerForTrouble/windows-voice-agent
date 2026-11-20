/*
 * Voice Agent bridge: lets Windows Voice Agent send messages (like Jockie Music's "m!skip") to a
 * Discord channel while Vesktop stays in the background. It sends them as you, through Discord's
 * own send function, the same one used when you press Enter.
 *
 * Only messages the agent asks for, only to the channels listed in this plugin's settings
 * (empty = any channel), at most 2 a second.
 */
import { definePluginSettings } from "@api/Settings";
import { sendMessage } from "@utils/discord";
import definePlugin, { OptionType, PluginNative } from "@utils/types";

const Native = VencordNative.pluginHelpers.VoiceAgentBridge as PluginNative<typeof import("./native")>;

const settings = definePluginSettings({
    channels: {
        type: OptionType.STRING,
        description: "Channel IDs it may send to, comma-separated (empty: any)",
        default: "1275456963358232634",
    },
});

let generation = 0; // each start() begins a new loop; an older one stops at its next turn
let sentAt: number[] = [];

async function loop(mine: number) {
    while (mine === generation) {
        let jobs: { channel: string; text: string; }[] = [];
        try {
            jobs = await Native.next();
        } catch {
            await new Promise(r => setTimeout(r, 2000));
            continue;
        }
        const allowed = settings.store.channels.split(",").map(s => s.trim()).filter(Boolean);
        for (const job of jobs) {
            if (mine !== generation) return;
            if (allowed.length && !allowed.includes(job.channel)) continue;
            const now = Date.now();
            sentAt = sentAt.filter(t => now - t < 1000);
            if (sentAt.length >= 2) await new Promise(r => setTimeout(r, 1000));
            sentAt.push(Date.now());
            try {
                Promise.resolve(sendMessage(job.channel, { content: job.text }))
                    .catch(e => console.error("[VoiceAgentBridge] Discord didn't send it", e));
            } catch (e) {
                console.error("[VoiceAgentBridge] couldn't send", e);
            }
        }
    }
}

export default definePlugin({
    name: "VoiceAgentBridge",
    description: "Lets Windows Voice Agent send bot commands (Jockie Music's m!play…) to a channel while Vesktop stays in the background",
    authors: [{ name: "profane", id: 0n }],
    settings,
    start() {
        loop(++generation);
    },
    stop() {
        generation++;
    },
});
