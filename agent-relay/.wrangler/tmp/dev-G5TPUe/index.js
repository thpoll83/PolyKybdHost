var __defProp = Object.defineProperty;
var __name = (target, value) => __defProp(target, "name", { value, configurable: true });

// src/index.js
import { DurableObject } from "cloudflare:workers";
import HOOK_SCRIPT from "./8c23b1ea27ef004821e65f613a74ad13dec4f8af-cloud_hook.py";
var LIMITS = {
  blobChars: 4096,
  // one sealed report is ~300 characters
  entries: 64,
  // sessions kept per channel
  entryTtlMs: 24 * 3600 * 1e3,
  eventsPerDay: 2e3,
  // per channel; a busy day is a few hundred
  eventsPerMinute: 30,
  // per channel, in memory (lost on eviction: fine)
  sockets: 4
  // host connections per channel
};
var HEX32 = /^[0-9a-f]{32}$/;
var HEX64 = /^[0-9a-f]{64}$/;
function json(status, body, extra = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store", ...extra }
  });
}
__name(json, "json");
function bearer(request) {
  const m = /^Bearer ([0-9a-f]{64})$/.exec(request.headers.get("authorization") || "");
  return m ? m[1] : "";
}
__name(bearer, "bearer");
async function sha256hex(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
__name(sha256hex, "sha256hex");
function sameHex(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  const enc = new TextEncoder();
  return crypto.subtle.timingSafeEqual(enc.encode(a), enc.encode(b));
}
__name(sameHex, "sameHex");
async function readJson(request, maxBytes) {
  const text = await request.text();
  if (text.length > maxBytes) throw new Error("too large");
  const body = JSON.parse(text);
  if (!body || typeof body !== "object" || Array.isArray(body)) throw new Error("not an object");
  return body;
}
__name(readJson, "readJson");
var src_default = {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;
    if (request.method === "GET" && path === "/") {
      return new Response("PolyHost agent relay\n", { headers: { "content-type": "text/plain" } });
    }
    if (request.method === "GET" && path === "/v1/hook.py") {
      return new Response(HOOK_SCRIPT, {
        headers: { "content-type": "text/x-python; charset=utf-8", "cache-control": "no-store" }
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
      if (!HEX32.test(body.channel || "") || !HEX64.test(body.read_hash || "") || !HEX64.test(body.write_hash || "")) {
        return json(400, { ok: false, error: "bad channel" });
      }
      const stub2 = env.CHANNEL.get(env.CHANNEL.idFromName(body.channel));
      return stub2.create(body.read_hash, body.write_hash);
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
      const forwarded = new Request(request, { headers: new Headers(request.headers) });
      forwarded.headers.set("x-token-hash", tokenHash);
      return stub.fetch(forwarded);
    }
    if (action === "" && request.method === "DELETE") return stub.remove(tokenHash);
    return json(405, { ok: false, error: "method not allowed" });
  }
};
var Channel = class extends DurableObject {
  static {
    __name(this, "Channel");
  }
  constructor(ctx, env) {
    super(ctx, env);
    this.minute = { start: 0, count: 0 };
  }
  async auth() {
    return await this.ctx.storage.get("auth") || null;
  }
  async create(readHash, writeHash) {
    const auth = await this.auth();
    if (auth) {
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
    if (!HEX32.test(k || "") || typeof blob !== "string" || !blob || blob.length > LIMITS.blobChars || !/^[A-Za-z0-9_-]+$/.test(blob)) {
      return json(400, { ok: false, error: "bad event" });
    }
    const now = Date.now();
    if (now - this.minute.start >= 6e4) this.minute = { start: now, count: 0 };
    if (++this.minute.count > LIMITS.eventsPerMinute) {
      return json(429, { ok: false, error: "too many events this minute" });
    }
    const today = new Date(now).toISOString().slice(0, 10);
    const day = await this.ctx.storage.get("day") || { date: today, n: 0 };
    if (day.date !== today) {
      day.date = today;
      day.n = 0;
    }
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
      try {
        ws.send(message);
      } catch {
      }
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
      try {
        ws.close(4001, "channel deleted");
      } catch {
      }
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
    try {
      ws.close(1e3, "closed");
    } catch {
    }
  }
};

// ../../../../root/.npm/_npx/7301ef091f335fd2/node_modules/wrangler/templates/middleware/middleware-ensure-req-body-drained.ts
var drainBody = /* @__PURE__ */ __name(async (request, env, _ctx, middlewareCtx) => {
  try {
    return await middlewareCtx.next(request, env);
  } finally {
    try {
      if (request.body !== null && !request.bodyUsed) {
        const reader = request.body.getReader();
        while (!(await reader.read()).done) {
        }
      }
    } catch (e) {
      console.error("Failed to drain the unused request body.", e);
    }
  }
}, "drainBody");
var middleware_ensure_req_body_drained_default = drainBody;

// ../../../../root/.npm/_npx/7301ef091f335fd2/node_modules/wrangler/templates/middleware/middleware-miniflare3-json-error.ts
function reduceError(e) {
  return {
    name: e?.name,
    message: e?.message ?? String(e),
    stack: e?.stack,
    cause: e?.cause === void 0 ? void 0 : reduceError(e.cause)
  };
}
__name(reduceError, "reduceError");
var jsonError = /* @__PURE__ */ __name(async (request, env, _ctx, middlewareCtx) => {
  try {
    return await middlewareCtx.next(request, env);
  } catch (e) {
    const error = reduceError(e);
    const body = JSON.stringify(error);
    const headers = {
      "Content-Type": "application/json",
      "MF-Experimental-Error-Stack": "true"
    };
    const encoded = encodeURIComponent(body);
    if (encoded.length <= 8192) {
      headers["MF-Experimental-Error-Stack-Payload"] = encoded;
    }
    return new Response(body, { status: 500, headers });
  }
}, "jsonError");
var middleware_miniflare3_json_error_default = jsonError;

// .wrangler/tmp/bundle-cXwDxv/middleware-insertion-facade.js
var __INTERNAL_WRANGLER_MIDDLEWARE__ = [
  middleware_ensure_req_body_drained_default,
  middleware_miniflare3_json_error_default
];
var middleware_insertion_facade_default = src_default;

// ../../../../root/.npm/_npx/7301ef091f335fd2/node_modules/wrangler/templates/middleware/common.ts
var __facade_middleware__ = [];
function __facade_register__(...args) {
  __facade_middleware__.push(...args.flat());
}
__name(__facade_register__, "__facade_register__");
function __facade_invokeChain__(request, env, ctx, dispatch, middlewareChain) {
  const [head, ...tail] = middlewareChain;
  const middlewareCtx = {
    dispatch,
    next(newRequest, newEnv) {
      return __facade_invokeChain__(newRequest, newEnv, ctx, dispatch, tail);
    }
  };
  return head(request, env, ctx, middlewareCtx);
}
__name(__facade_invokeChain__, "__facade_invokeChain__");
function __facade_invoke__(request, env, ctx, dispatch, finalMiddleware) {
  return __facade_invokeChain__(request, env, ctx, dispatch, [
    ...__facade_middleware__,
    finalMiddleware
  ]);
}
__name(__facade_invoke__, "__facade_invoke__");

// .wrangler/tmp/bundle-cXwDxv/middleware-loader.entry.ts
var __Facade_ScheduledController__ = class ___Facade_ScheduledController__ {
  constructor(scheduledTime, cron, noRetry) {
    this.scheduledTime = scheduledTime;
    this.cron = cron;
    this.#noRetry = noRetry;
  }
  scheduledTime;
  cron;
  static {
    __name(this, "__Facade_ScheduledController__");
  }
  #noRetry;
  noRetry() {
    if (!(this instanceof ___Facade_ScheduledController__)) {
      throw new TypeError("Illegal invocation");
    }
    this.#noRetry();
  }
};
function wrapExportedHandler(worker) {
  if (__INTERNAL_WRANGLER_MIDDLEWARE__ === void 0 || __INTERNAL_WRANGLER_MIDDLEWARE__.length === 0) {
    return worker;
  }
  for (const middleware of __INTERNAL_WRANGLER_MIDDLEWARE__) {
    __facade_register__(middleware);
  }
  const fetchDispatcher = /* @__PURE__ */ __name(function(request, env, ctx) {
    if (worker.fetch === void 0) {
      throw new Error("Handler does not export a fetch() function.");
    }
    return worker.fetch(request, env, ctx);
  }, "fetchDispatcher");
  return {
    ...worker,
    fetch(request, env, ctx) {
      const dispatcher = /* @__PURE__ */ __name(function(type, init) {
        if (type === "scheduled" && worker.scheduled !== void 0) {
          const controller = new __Facade_ScheduledController__(
            Date.now(),
            init.cron ?? "",
            () => {
            }
          );
          return worker.scheduled(controller, env, ctx);
        }
      }, "dispatcher");
      return __facade_invoke__(request, env, ctx, dispatcher, fetchDispatcher);
    }
  };
}
__name(wrapExportedHandler, "wrapExportedHandler");
function wrapWorkerEntrypoint(klass) {
  if (__INTERNAL_WRANGLER_MIDDLEWARE__ === void 0 || __INTERNAL_WRANGLER_MIDDLEWARE__.length === 0) {
    return klass;
  }
  for (const middleware of __INTERNAL_WRANGLER_MIDDLEWARE__) {
    __facade_register__(middleware);
  }
  return class extends klass {
    #fetchDispatcher = /* @__PURE__ */ __name((request, env, ctx) => {
      this.env = env;
      this.ctx = ctx;
      if (super.fetch === void 0) {
        throw new Error("Entrypoint class does not define a fetch() function.");
      }
      return super.fetch(request);
    }, "#fetchDispatcher");
    #dispatcher = /* @__PURE__ */ __name((type, init) => {
      if (type === "scheduled" && super.scheduled !== void 0) {
        const controller = new __Facade_ScheduledController__(
          Date.now(),
          init.cron ?? "",
          () => {
          }
        );
        return super.scheduled(controller);
      }
    }, "#dispatcher");
    fetch(request) {
      return __facade_invoke__(
        request,
        this.env,
        this.ctx,
        this.#dispatcher,
        this.#fetchDispatcher
      );
    }
  };
}
__name(wrapWorkerEntrypoint, "wrapWorkerEntrypoint");
var WRAPPED_ENTRY;
if (typeof middleware_insertion_facade_default === "object") {
  WRAPPED_ENTRY = wrapExportedHandler(middleware_insertion_facade_default);
} else if (typeof middleware_insertion_facade_default === "function") {
  WRAPPED_ENTRY = wrapWorkerEntrypoint(middleware_insertion_facade_default);
}
var middleware_loader_entry_default = WRAPPED_ENTRY;
export {
  Channel,
  LIMITS,
  __INTERNAL_WRANGLER_MIDDLEWARE__,
  middleware_loader_entry_default as default
};
//# sourceMappingURL=index.js.map
