// SPDX-License-Identifier: GPL-3.0-or-later
/**
 * The part of the PolyKybd Mode Reporter that does not need the editor API.
 *
 * Everything here runs in plain Node (the unit tests in ../test run it with
 * `node --test`): the app token, the pseudo-URL, the debug state read from the
 * Debug Adapter Protocol messages, when to send, and the JSON body.
 * `extension.ts` connects it to the `vscode` API and to the network.
 *
 * What is sent, and nothing else:
 *
 *     POST http://127.0.0.1:<port>/report      Content-Type: application/json
 *     {"app": "vscode", "url": "vscode://debug/stopped", "focused": true,
 *      "pid": 4242, "input_age": 0.4, "token": "<only if one is configured>"}
 *
 * Only erasable TypeScript syntax is used (no enums, no parameter
 * properties), so Node can run this file without a compile step.
 */

export const DEFAULT_PORT = 50164; // PolyKybdHost `browser_report_port`
// The host drops a report older than 8 s (browser_url.py DEFAULT_MAX_AGE_S);
// a keep-alive every 3 s keeps it fresh with two lost reports.
export const KEEPALIVE_MS = 3000;
export const HTTP_TIMEOUT_MS = 500;

export type Mode = "edit" | "debug/running" | "debug/stopped";

/**
 * The `app` token for the editor this extension runs in, from `env.appName`
 * ("Visual Studio Code", "Cursor", "Windsurf", "Devin"). The host keeps one
 * allow-list entry per token, so Cursor's report never answers for VS Code.
 */
export function appToken(appName: unknown): string {
  const n = String(appName ?? "").toLowerCase();
  if (n.includes("cursor")) return "cursor";
  if (n.includes("windsurf") || n.includes("devin")) return "windsurf";
  return "vscode";
}

/** `<app>://edit`, `<app>://debug/running` or `<app>://debug/stopped`. */
export function modeUrl(app: string, mode: Mode): string {
  return `${app}://${mode}`;
}

/** The mode for the active debug session: none, or its tracked state. */
export function modeFor(session: SessionState | undefined): Mode {
  if (!session) return "edit";
  return session.isStopped() ? "debug/stopped" : "debug/running";
}

/**
 * The mode to report, or null to report nothing. `hasActive` is whether the
 * editor has an active debug session, `state` its tracker's state. A session
 * with no tracker (it started before the extension was activated, or its
 * adapter runs in a remote extension host) has an unknown state: report
 * nothing, so the host shows every debug key, instead of claiming "running".
 */
export function activeMode(hasActive: boolean, state: SessionState | undefined): Mode | null {
  if (!hasActive) return "edit";
  return state ? modeFor(state) : null;
}

// DAP requests that resume the program when they succeed. Without
// `singleThread: true` every thread resumes; with it, only `threadId`.
const RESUMING = new Set([
  "continue", "next", "stepIn", "stepOut", "stepBack", "reverseContinue",
]);

/**
 * Whether one debug session's program is stopped, read from the Debug Adapter
 * Protocol messages a `DebugAdapterTracker` sees. VS Code's own `debugState`
 * context key is not readable by an extension, so this follows the same
 * events it is built from:
 *
 * - `stopped` event: that thread (or every thread, `allThreadsStopped`) stops.
 * - `continued` event: every thread resumes, unless `allThreadsContinued` is
 *   false, then only `threadId`.
 * - a successful response to a resuming request (continue, next, stepIn, ...):
 *   the threads that request resumed. Adapters do not send `continued` for
 *   those.
 */
export class SessionState {
  stopped: Set<number> = new Set();
  allStopped = false;
  // Threads resumed one at a time since the last all-threads stop. DAP leaves
  // the other threads stopped, so they do not end the stopped state.
  resumed: Set<number> = new Set();
  // The thread ids of the last `threads` response (VS Code asks after every
  // stop), or null before one arrives.
  threads: Set<number> | null = null;
  pending: Map<number, { command: string; threadId?: number; single: boolean }> = new Map();

  isStopped(): boolean {
    if (this.stopped.size > 0) return true;
    if (!this.allStopped) return false;
    // Every thread stopped, then some resumed one at a time. Without a
    // thread list the others are taken to be still stopped.
    if (this.threads === null || this.threads.size === 0) return true;
    for (const t of this.threads) if (!this.resumed.has(t)) return true;
    return false;
  }

  /** A message the editor sends to the adapter (`onWillReceiveMessage`). */
  toAdapter(msg: any): void {
    if (!msg || msg.type !== "request") return;
    if (msg.command !== "threads" && !RESUMING.has(msg.command)) return;
    const args = msg.arguments || {};
    this.pending.set(msg.seq, {
      command: msg.command,
      threadId: typeof args.threadId === "number" ? args.threadId : undefined,
      single: args.singleThread === true,
    });
    // Bounded: a response that never comes must not grow the map.
    if (this.pending.size > 64) {
      const first = this.pending.keys().next().value;
      if (first !== undefined) this.pending.delete(first);
    }
  }

  /** A message the adapter sends to the editor (`onDidSendMessage`). */
  fromAdapter(msg: any): void {
    if (!msg) return;
    if (msg.type === "event") {
      const body = msg.body || {};
      if (msg.event === "stopped") {
        if (body.allThreadsStopped || typeof body.threadId !== "number") {
          this.allStopped = true;
          this.resumed.clear();
        }
        if (typeof body.threadId === "number") {
          this.stopped.add(body.threadId);
          this.resumed.delete(body.threadId);
        }
      } else if (msg.event === "continued") {
        this.resume(body.allThreadsContinued === false ? body.threadId : undefined);
      }
      return;
    }
    if (msg.type === "response") {
      const req = this.pending.get(msg.request_seq);
      if (!req) return;
      this.pending.delete(msg.request_seq);
      if (!msg.success) return;
      if (req.command === "threads") {
        const list = msg.body && Array.isArray(msg.body.threads) ? msg.body.threads : null;
        if (list) {
          this.threads = new Set(list.map((t: any) => t && t.id).filter((id: unknown) => typeof id === "number"));
        }
        return;
      }
      // A continue response says so itself; a missing value means all threads.
      const body = msg.body || {};
      const single = req.command === "continue"
        ? body.allThreadsContinued === false || req.single
        : req.single;
      this.resume(single ? req.threadId : undefined);
    }
  }

  /** `threadId` undefined: every thread resumes. */
  resume(threadId: number | undefined): void {
    if (threadId === undefined) {
      this.stopped.clear();
      this.resumed.clear();
      this.allStopped = false;
    } else {
      this.stopped.delete(threadId);
      if (this.allStopped) this.resumed.add(threadId);
    }
  }
}

/** Send on a change of URL or focus, plus a keep-alive while nothing changes. */
export class SendPolicy {
  keepaliveMs: number;
  last: string | null = null;
  lastSent: number | null = null;

  constructor(keepaliveMs: number = KEEPALIVE_MS) {
    this.keepaliveMs = keepaliveMs;
  }

  due(url: string, focused: boolean, now: number): boolean {
    const key = `${focused ? 1 : 0}${url}`;
    if (key !== this.last || this.lastSent === null) return true;
    return now - this.lastSent >= this.keepaliveMs;
  }

  sent(url: string, focused: boolean, now: number): void {
    this.last = `${focused ? 1 : 0}${url}`;
    this.lastSent = now;
  }

  reset(): void {
    this.last = null;
    this.lastSent = null;
  }
}

/**
 * One report as the JSON text to POST. `url` null with `focused` false
 * withdraws this window's mode (sent when reporting is turned off or the
 * extension stops).
 */
export function payload(app: string, url: string | null, focused: boolean,
                        pid?: number, inputAgeS?: number, token?: string): string {
  const body: Record<string, unknown> = { app, url, focused: Boolean(focused) };
  if (typeof pid === "number") body.pid = Math.trunc(pid);
  if (typeof inputAgeS === "number" && Number.isFinite(inputAgeS)) {
    body.input_age = Math.round(Math.max(0, inputAgeS) * 10) / 10;
  }
  if (token) body.token = token;
  return JSON.stringify(body);
}

/** A port setting as a valid TCP port, or the default. */
export function validPort(value: unknown): number {
  const n = Number(value);
  return Number.isInteger(n) && n >= 1 && n <= 65535 ? n : DEFAULT_PORT;
}

/**
 * When this window last had user input, for `input_age`. Only input while the
 * window is focused counts: a selection change in a background window can come
 * from a command or another extension, and the host follows the window with
 * the newest input, then requires it to be focused.
 */
export class InputClock {
  last: number;

  constructor(now: number) {
    this.last = now;
  }

  /** A cursor or editor change. */
  input(focused: boolean, now: number): void {
    if (focused) this.last = now;
  }

  /** The window gained focus. */
  focus(now: number): void {
    this.last = now;
  }

  ageS(now: number): number {
    return (now - this.last) / 1000;
  }
}

/**
 * Sends one report at a time. A report that arrives while one is on the way
 * replaces the waiting one (only the newest report matters), so a slow or
 * missing receiver never builds a queue.
 *
 * `send` delivers one body and calls `done` when the request ended. A request
 * can end in two ways at once (a timeout after the response headers arrived
 * fails both the request and the response); only the first `done` counts.
 */
export type Sender = (port: number, body: string, done: () => void) => void;

export class ReportQueue {
  send: Sender;
  inFlight = false;
  queued: { port: number; body: string } | null = null;
  waiters: Array<() => void> = [];

  constructor(send: Sender) {
    this.send = send;
  }

  post(port: number, body: string): void {
    if (this.inFlight) {
      this.queued = { port, body };
      return;
    }
    this.inFlight = true;
    let finished = false;
    this.send(port, body, () => {
      if (finished) return;
      finished = true;
      this.inFlight = false;
      const next = this.queued;
      this.queued = null;
      if (next) {
        this.post(next.port, next.body);
      } else {
        const w = this.waiters;
        this.waiters = [];
        for (const f of w) f();
      }
    });
  }

  /** Settles when the report on the way and the waiting one are done. */
  idle(): Promise<void> {
    if (!this.inFlight) return Promise.resolve();
    return new Promise((resolve) => this.waiters.push(resolve));
  }
}

/** `p`, or a resolved promise after `ms`, whichever comes first. */
export function settleWithin(p: Promise<void>, ms: number): Promise<void> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const limit = new Promise<void>((resolve) => { timer = setTimeout(resolve, ms); });
  return Promise.race([p, limit]).finally(() => clearTimeout(timer));
}
