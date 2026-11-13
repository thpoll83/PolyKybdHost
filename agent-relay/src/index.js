// PolyHost agent relay: carries the state of Claude Code cloud sessions to the
// PolyKybd host on the user's computer (agent keys). Neither end can reach the
// other directly: the cloud VM is behind Anthropic's proxy, the keyboard computer
// behind the user's router. Both connect out to this Worker.
//
// What the relay can see: channel IDs, opaque session keys and ciphertext. The
// title, state, URL and session ID are encrypted end to end by
// polyhost/services/agents/cloud_hook.py with a key the relay never gets.
//
// Endpoints (all JSON; tokens as `Authorization: Bearer <token>`):
//   GET    /                       banner (the deploy smoke test)
//   GET    /v1/hook.py             the hook script for the cloud environment
//   POST   /v1/channels            {channel, read_hash, write_hash}: create
//   POST   /v1/c/<channel>/event   write token: {k, blob, ended}
//   GET    /v1/c/<channel>/state   read token: the current entries
//   GET    /v1/c/<channel>/ws      read token: WebSocket, snapshot then updates
//   DELETE /v1/c/<channel>         read token: delete the channel
//
// Budget (Workers Free: 100,000 Worker and 100,000 Durable Object requests a day,
// account-wide): every event costs one of each, so each channel is capped below.
// polykybd-telemetry-data's usage check alerts at 80 % of the account's day.

import { DurableObject } from "cloudflare:workers";
import HOOK_SCRIPT from "../../polyhost/services/agents/cloud_hook.py";

export const LIMITS = {
  blobChars: 4096,          // one sealed report is ~300 characters
  entries: 64,              // sessions kept per channel
  entryTtlMs: 24 * 3600 * 1000,
  eventsPerDay: 2000,       // per channel; a busy day is a few hundred
  eventsPerMinute: 30,      // per channel, in memory (lost on eviction: fine)
  sockets: 4,               // host connections per channel
};

const HEX32 = /^[0-9a-f]{32}$/;
const HEX64 = /^[0-9a-f]{64}$/;

function json(status, body, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store", ...extra },
  });
}

function bearer(request) {
  const m = /^Bearer ([0-9a-f]{64})$/.exec(request.headers.get("authorization") || "");
  return m ? m[1] : "";
}

async function sha256hex(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function isHex(pattern, value) {
  // RegExp.test() converts its argument: ["<hex>"] would pass without this.
  return typeof value === "string" && pattern.test(value);
}

function sameHex(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  const enc = new TextEncoder();
  return crypto.subtle.timingSafeEqual(enc.encode(a), enc.encode(b));
}

async function readBounded(request, maxBytes) {
  // Refuse by the declared length first: a body without one (chunked) or with a
  // malformed one is refused, not read. Then read the stream and stop as soon as
  // more than maxBytes arrived, so no body is buffered past the limit.
  const declared = request.headers.get("content-length");
  if (declared === null || !/^[0-9]+$/.test(declared) || Number(declared) > maxBytes) {
    throw new Error("too large or no length");
  }
  if (!request.body) return new Uint8Array(0);
  const reader = request.body.getReader();
  const chunks = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > maxBytes) {
      await reader.cancel();
      throw new Error("too large");
    }
    chunks.push(value);
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return bytes;
}

async function readJson(request, maxBytes) {
  const bytes = await readBounded(request, maxBytes);
  const body = JSON.parse(new TextDecoder().decode(bytes));
  if (!body || typeof body !== "object" || Array.isArray(body)) throw new Error("not an object");
  return body;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === "GET" && path === "/") {
      return new Response("PolyHost agent relay\n", { headers: { "content-type": "text/plain" } });
    }
    if (request.method === "GET" && path === "/v1/hook.py") {
      return new Response(HOOK_SCRIPT, {
        headers: { "content-type": "text/x-python; charset=utf-8", "cache-control": "no-store" },
      });
    }
    if (request.method === "POST" && path === "/v1/channels") {
      const ip = request.headers.get("cf-connecting-ip") || "unknown";
      if (env.CREATE_LIMITER) {
        const { success } = await env.CREATE_LIMITER.limit({ key: ip });
        if (!success) return json(429, { ok: false, error: "too many channels created" });
      }
      let body;
      try {
        body = await readJson(request, 1024);
      } catch {
        return json(400, { ok: false, error: "bad json" });
      }
      if (!isHex(HEX32, body.channel) || !isHex(HEX64, body.read_hash)
          || !isHex(HEX64, body.write_hash)) {
        return json(400, { ok: false, error: "bad channel" });
      }
      const stub = env.CHANNEL.get(env.CHANNEL.idFromName(body.channel));
      return stub.create(body.read_hash, body.write_hash);
    }

    const m = /^\/v1\/c\/([0-9a-f]{32})(\/event|\/state|\/ws)?$/.exec(path);
    if (!m) return json(404, { ok: false, error: "not found" });
    const token = bearer(request);
    if (!token) return json(401, { ok: false, error: "missing token" });
    const stub = env.CHANNEL.get(env.CHANNEL.idFromName(m[1]));
    const tokenHash = await sha256hex(token);
    const action = m[2] || "";

    if (action === "/event" && request.method === "POST") {
      let body;
      try {
        body = await readJson(request, LIMITS.blobChars + 256);
      } catch {
        return json(400, { ok: false, error: "bad json" });
      }
      return stub.event(tokenHash, body);
    }
    if (action === "/state" && request.method === "GET") return stub.state(tokenHash);
    if (action === "/ws" && request.method === "GET") {
      if (request.headers.get("upgrade") !== "websocket") {
        return json(426, { ok: false, error: "websocket expected" });
      }
      // The Durable Object checks the token and accepts the socket.
      const forwarded = new Request(request, { headers: new Headers(request.headers) });
      forwarded.headers.set("x-token-hash", tokenHash);
      return stub.fetch(forwarded);
    }
    if (action === "" && request.method === "DELETE") return stub.remove(tokenHash);
    return json(405, { ok: false, error: "method not allowed" });
  },
};

export class Channel extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.minute = { start: 0, count: 0 };
  }

  async auth() {
    return (await this.ctx.storage.get("auth")) || null;
  }

  async create(readHash, writeHash) {
    const auth = await this.auth();
    if (auth) {
      // Creating again with the same hashes is fine (a host that retried).
      if (sameHex(auth.read, readHash) && sameHex(auth.write, writeHash)) {
        return json(200, { ok: true, existed: true });
      }
      return json(409, { ok: false, error: "channel exists" });
    }
    await this.ctx.storage.put("auth", { read: readHash, write: writeHash, created: Date.now() });
    return json(201, { ok: true });
  }

  async entries() {
    const now = Date.now();
    const rows = await this.ctx.storage.list({ prefix: "e:" });
    const out = [];
    const stale = [];
    for (const [key, value] of rows) {
      if (now - value.ts > LIMITS.entryTtlMs) stale.push(key);
      else out.push({ k: key.slice(2), blob: value.blob, ts: value.ts });
    }
    if (stale.length) await this.ctx.storage.delete(stale);
    return out;
  }

  async event(tokenHash, body) {
    const auth = await this.auth();
    if (!auth) return json(404, { ok: false, error: "no such channel" });
    if (!sameHex(auth.write, tokenHash)) return json(403, { ok: false, error: "bad token" });
    const k = body.k;
    const blob = body.blob;
    const ended = body.ended === true;
    if (!isHex(HEX32, k) || typeof blob !== "string" || !blob
        || blob.length > LIMITS.blobChars || !/^[A-Za-z0-9_-]+$/.test(blob)) {
      return json(400, { ok: false, error: "bad event" });
    }

    const now = Date.now();
    if (now - this.minute.start >= 60000) this.minute = { start: now, count: 0 };
    if (++this.minute.count > LIMITS.eventsPerMinute) {
      return json(429, { ok: false, error: "too many events this minute" });
    }
    const today = new Date(now).toISOString().slice(0, 10);
    const day = (await this.ctx.storage.get("day")) || { date: today, n: 0 };
    if (day.date !== today) { day.date = today; day.n = 0; }
    if (day.n >= LIMITS.eventsPerDay) {
      return json(429, { ok: false, error: "daily limit of this channel reached" });
    }
    day.n += 1;

    if (ended) {
      await this.ctx.storage.delete("e:" + k);
      await this.ctx.storage.put("day", day);
    } else {
      await this.ctx.storage.put({ ["e:" + k]: { blob, ts: now }, day });
      const all = await this.entries();
      if (all.length > LIMITS.entries) {
        all.sort((a, b) => a.ts - b.ts);
        await this.ctx.storage.delete(all.slice(0, all.length - LIMITS.entries).map((e) => "e:" + e.k));
      }
    }
    const message = JSON.stringify({ type: "event", k, blob, ts: now, ended });
    for (const ws of this.ctx.getWebSockets()) {
      try { ws.send(message); } catch { /* a closing socket: the host reconnects */ }
    }
    return json(200, { ok: true });
  }

  async state(tokenHash) {
    const auth = await this.auth();
    if (!auth) return json(404, { ok: false, error: "no such channel" });
    if (!sameHex(auth.read, tokenHash)) return json(403, { ok: false, error: "bad token" });
    return json(200, { ok: true, entries: await this.entries() });
  }

  async remove(tokenHash) {
    const auth = await this.auth();
    if (!auth) return json(404, { ok: false, error: "no such channel" });
    if (!sameHex(auth.read, tokenHash)) return json(403, { ok: false, error: "bad token" });
    for (const ws of this.ctx.getWebSockets()) {
      try { ws.close(4001, "channel deleted"); } catch { /* already closed */ }
    }
    await this.ctx.storage.deleteAll();
    return json(200, { ok: true });
  }

  // The WebSocket upgrade (forwarded by the Worker with the token's hash).
  async fetch(request) {
    const auth = await this.auth();
    if (!auth) return json(404, { ok: false, error: "no such channel" });
    if (!sameHex(auth.read, request.headers.get("x-token-hash") || "")) {
      return json(403, { ok: false, error: "bad token" });
    }
    if (this.ctx.getWebSockets().length >= LIMITS.sockets) {
      return json(429, { ok: false, error: "too many connections" });
    }
    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);
    // Hibernation API: an idle connection costs no duration while it waits.
    this.ctx.acceptWebSocket(server);
    server.send(JSON.stringify({ type: "snapshot", entries: await this.entries() }));
    return new Response(null, { status: 101, webSocket: client });
  }

  // The host sends nothing but an occasional "ping" (each counts as a request,
  // so the host keeps them rare); anything else closes the socket.
  async webSocketMessage(ws, message) {
    if (message === "ping") ws.send("pong");
    else ws.close(4002, "unexpected message");
  }

  async webSocketClose(ws) {
    // The peer's code can be one close() may not send (1005, 1006): answer 1000.
    try { ws.close(1000, "closed"); } catch { /* already closed */ }
  }
}
