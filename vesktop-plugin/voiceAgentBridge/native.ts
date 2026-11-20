/*
 * Voice Agent bridge, the part that runs in Vesktop's main process.
 *
 * Listens on 127.0.0.1 only (a random port), for one thing: "send this text to this channel".
 * Each request must carry the secret token; the port and token are written to
 * %LOCALAPPDATA%\WindowsVoiceAgent\discord-bridge.json, which only your Windows user can read,
 * and that is where the voice agent finds them. Nothing else on the network can reach it.
 */
import { randomBytes } from "crypto";
import { mkdirSync, unlinkSync, writeFileSync } from "fs";
import { createServer, IncomingMessage, Server, ServerResponse } from "http";
import { join } from "path";

type Job = { channel: string; text: string; };

const token = randomBytes(24).toString("hex");
const folder = join(process.env.LOCALAPPDATA || process.env.HOME || ".", "WindowsVoiceAgent");
const file = join(folder, "discord-bridge.json");
let queue: Job[] = [];
let waiter: ((jobs: Job[]) => void) | null = null;
let lastSeen = 0;
let server: Server | null = null;

function reply(res: ServerResponse, code: number, body: object) {
    res.writeHead(code, { "Content-Type": "application/json" });
    res.end(JSON.stringify(body));
}

function handle(req: IncomingMessage, res: ServerResponse) {
    if (req.method !== "POST" || req.url !== "/send" || req.headers["x-token"] !== token)
        return reply(res, 403, { ok: false, error: "no" });
    let body = "";
    req.on("data", chunk => {
        body += chunk;
        if (body.length > 8192) req.destroy();
    });
    req.on("end", () => {
        let job: Job;
        try {
            job = JSON.parse(body);
        } catch {
            return reply(res, 400, { ok: false, error: "bad json" });
        }
        if (typeof job.channel !== "string" || !/^\d{5,25}$/.test(job.channel) ||
            typeof job.text !== "string" || !job.text.trim() || job.text.length > 2000)
            return reply(res, 400, { ok: false, error: "bad message" });
        // Discord is open and listening (it asked for work in the last 30 s), or the agent flicks instead
        if (!waiter && Date.now() - lastSeen > 30_000)
            return reply(res, 503, { ok: false, error: "Vesktop isn't ready" });
        queue.push({ channel: job.channel, text: job.text });
        if (waiter) {
            const w = waiter;
            waiter = null;
            w(queue.splice(0));
        }
        reply(res, 202, { ok: true });
    });
}

function start() {
    if (server) return;
    server = createServer(handle);
    server.listen(0, "127.0.0.1", () => {
        const addr = server!.address();
        if (!addr || typeof addr === "string") return;
        mkdirSync(folder, { recursive: true });
        writeFileSync(file, JSON.stringify({ port: addr.port, token, pid: process.pid }), { mode: 0o600 });
    });
    process.on("exit", () => {
        try { unlinkSync(file); } catch { }
    });
}
start();

/** The plugin asks for messages to send; this answers as soon as there are some (or after 25 s). */
export function next(_event: unknown): Promise<Job[]> {
    lastSeen = Date.now();
    if (queue.length) return Promise.resolve(queue.splice(0));
    return new Promise(resolve => {
        if (waiter) waiter([]);
        waiter = resolve;
        setTimeout(() => {
            if (waiter === resolve) {
                waiter = null;
                lastSeen = Date.now();
                resolve([]);
            }
        }, 25_000);
    });
}
