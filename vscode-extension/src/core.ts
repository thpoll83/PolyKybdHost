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
  pending: Map<number, { command: string; threadId?: number; single: boolean }> = new Map();

  isStopped(): boolean {
    return this.allStopped || this.stopped.size > 0;
  }

  /** A message the editor sends to the adapter (`onWillReceiveMessage`). */
  toAdapter(msg: any): void {
    if (!msg || msg.type !== "request" || !RESUMING.has(msg.command)) return;
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
        if (body.allThreadsStopped) this.allStopped = true;
        if (typeof body.threadId === "number") this.stopped.add(body.threadId);
        if (!body.allThreadsStopped && typeof body.threadId !== "number") this.allStopped = true;
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
      this.allStopped = false;
    } else {
      this.stopped.delete(threadId);
      if (this.stopped.size === 0) this.allStopped = false;
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
