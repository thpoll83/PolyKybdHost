// SPDX-License-Identifier: GPL-3.0-or-later
/**
 * The part of the PolyKybd Mode Reporter that does not need the editor API.
 *
 * Everything here runs in plain Node (the unit tests in ../test run it with
 * `node --test`): the app token, the pseudo-URL, the debug state read from the
 * Debug Adapter Protocol messages, the bridge from a remote extension host,
 * when to send, and the JSON body. `extension.ts` (the UI part) connects it to
 * the `vscode` API and to the network; `remote.ts` (the workspace part, a
 * second small extension in `remote/`) runs the debug tracker in a remote
 * extension host and passes the state to the UI part.
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

// The most requests waiting for a response that SessionState keeps. A request
// past it drops the oldest one.
export const MAX_ENTRIES = 128;

// The most remote debug sessions RemoteStates keeps (states and last seqs). A
// session past it drops the oldest one.
export const MAX_REMOTE_SESSIONS = 128;

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

/**
 * `<app>://<mode>`, and `/diff` after it while a diff editor is the active
 * editor tab: `<app>://edit`, `<app>://edit/diff`, `<app>://debug/running`,
 * `<app>://debug/running/diff`, `<app>://debug/stopped`,
 * `<app>://debug/stopped/diff`.
 *
 * The debug mode comes first, so a host that routes on the debug mode alone
 * (`urls-contains`, a substring match) still finds it in a diff URL.
 */
export function modeUrl(app: string, mode: Mode, diff: boolean = false): string {
  return `${app}://${mode}${diff ? "/diff" : ""}`;
}

/**
 * Whether the active editor tab is a text diff editor. `input` is
 * `window.tabGroups.activeTabGroup.activeTab?.input`, `textDiff` the
 * `vscode.TabInputTextDiff` class (a parameter, so this runs without the
 * editor). A notebook diff (`TabInputNotebookDiff`) does not count: its change
 * keys are other keys (Alt+F3, Shift+Alt+F3), see README.md.
 */
export function isTextDiff(input: unknown, textDiff: unknown): boolean {
  return typeof textDiff === "function" && input instanceof (textDiff as new (...a: any[]) => unknown);
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
export function activeMode(hasActive: boolean, state: SessionState | undefined,
                           remote?: RemoteState): Mode | null {
  if (!hasActive) return "edit";
  if (state) return modeFor(state);
  // No tracker in this extension host: the state the remote part sent, if any.
  if (remote === "running") return "debug/running";
  if (remote === "stopped") return "debug/stopped";
  return null;
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
  // Counts the all-threads stops. A `threads` response answers for the stop
  // it was requested after; one requested before the latest stop is stale.
  stopGeneration = 0;
  pending: Map<number, { command: string; threadId?: number; single: boolean; generation: number }> = new Map();

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
      generation: this.stopGeneration,
    });
    // Bounded: a response that never comes must not grow the map.
    if (this.pending.size > MAX_ENTRIES) {
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
          // A thread can have started since the last `threads` response.
          // Until a fresh list arrives, every thread counts as stopped.
          this.threads = null;
          this.stopGeneration++;
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
        if (req.generation !== this.stopGeneration) return;
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

// ---------------------------------------------------------------------------
// The bridge from a remote extension host (Remote SSH, WSL, Dev Containers,
// Codespaces).
//
// VS Code creates a debug adapter tracker only in the extension host where the
// debug adapter runs. In a remote window that is the remote extension host, so
// the UI part's tracker sees nothing. The workspace part (`remote/`,
// `"extensionKind": ["workspace"]`) registers the same tracker there and calls
// a command the UI part registers. `vscode.commands.executeCommand` runs a
// command in whichever extension host registered it, and its arguments cross
// as JSON. A debug session has the same `id` in both extension hosts (the
// window assigns it), so the UI part matches the state to
// `debug.activeDebugSession.id`.
//
// The HTTP report stays in the UI part: only there is 127.0.0.1 the user's
// computer, where PolyKybdHost runs.

/** Registered by the UI part; the workspace part calls it on every change. */
export const BRIDGE_STATE_COMMAND = "polykybd.modeReporter.remoteState";
/** Registered by the workspace part; the UI part calls it when it starts, to
 *  get the states of sessions that began before it. */
export const BRIDGE_SYNC_COMMAND = "polykybd.modeReporter.remoteSync";
export const BRIDGE_VERSION = 1;

/** A session's state as the workspace part reports it; null: no state (the
 *  adapter exited, or the session has no tracker). */
export type RemoteState = "running" | "stopped" | null;

export interface BridgeMessage {
  v: number;
  session: string;
  state: RemoteState;
  seq: number;
}

/**
 * The message for one session. Only the session id and running or stopped
 * cross: no thread ids, no file names.
 */
export function bridgeMessage(session: string, state: SessionState | undefined,
                              seq: number): BridgeMessage {
  return { v: BRIDGE_VERSION, session, state: state ? (state.isStopped() ? "stopped" : "running") : null, seq };
}

/**
 * A message as received, or null when it is not one this version reads. Any
 * extension can call a registered command, so nothing is trusted: the fields
 * are checked one by one and nothing else is kept.
 */
export function parseBridgeMessage(arg: unknown): BridgeMessage | null {
  if (!arg || typeof arg !== "object") return null;
  const m = arg as Record<string, unknown>;
  if (m.v !== BRIDGE_VERSION) return null;
  if (typeof m.session !== "string" || m.session.length === 0) return null;
  if (m.state !== "running" && m.state !== "stopped" && m.state !== null) return null;
  if (typeof m.seq !== "number" || !Number.isSafeInteger(m.seq) || m.seq < 0) return null;
  return { v: BRIDGE_VERSION, session: m.session, state: m.state, seq: m.seq };
}

/**
 * The UI part's copy of the states the workspace part sent, per session.
 * A message older than the last one applied for its session is dropped
 * (`seq` counts up in the workspace part). Bounded to MAX_REMOTE_SESSIONS sessions.
 */
export class RemoteStates {
  states: Map<string, { state: "running" | "stopped"; seq: number }> = new Map();
  // The last seq per session, also after its state was cleared, so a late
  // "running" cannot bring back a session that exited.
  seqs: Map<string, number> = new Map();

  /** Applies one command argument. True when the stored state changed. */
  apply(arg: unknown): boolean {
    const m = parseBridgeMessage(arg);
    if (!m) return false;
    const last = this.seqs.get(m.session);
    if (last !== undefined && m.seq <= last) return false;
    this.seqs.delete(m.session);
    this.seqs.set(m.session, m.seq);
    bound(this.seqs, MAX_REMOTE_SESSIONS);
    const before = this.states.get(m.session)?.state ?? null;
    if (m.state === null) {
      this.states.delete(m.session);
    } else {
      this.states.delete(m.session);
      this.states.set(m.session, { state: m.state, seq: m.seq });
      bound(this.states, MAX_REMOTE_SESSIONS);
    }
    return before !== m.state;
  }

  get(session: string | undefined): RemoteState | undefined {
    if (session === undefined) return undefined;
    return this.states.get(session)?.state;
  }

  /** The session ended (`debug.onDidTerminateDebugSession` in the UI part). */
  forget(session: string): void {
    this.states.delete(session);
  }
}

function bound<K, V>(m: Map<K, V>, max: number): void {
  while (m.size > max) {
    const first = m.keys().next().value;
    if (first === undefined) return;
    m.delete(first);
  }
}

/**
 * The workspace part's trackers. `send` delivers one message to the UI part
 * (`executeCommand(BRIDGE_STATE_COMMAND, msg)`). A message goes out only when
 * a session's state changes, not on every DAP message.
 */
export class WorkspaceBridge {
  send: (msg: BridgeMessage) => void;
  sessions: Map<string, SessionState> = new Map();
  sent: Map<string, RemoteState> = new Map();
  seq = 0;

  constructor(send: (msg: BridgeMessage) => void) {
    this.send = send;
  }

  /** The tracker's three callbacks for one new debug session. */
  track(session: string): { toAdapter: (m: unknown) => void; fromAdapter: (m: unknown) => void; exit: () => void } {
    const state = new SessionState();
    this.sessions.set(session, state);
    this.push(session);
    return {
      toAdapter: (m: unknown) => state.toAdapter(m),
      fromAdapter: (m: unknown) => { state.fromAdapter(m); this.push(session); },
      exit: () => this.end(session),
    };
  }

  /** The adapter exited, or the session terminated. */
  end(session: string): void {
    if (!this.sessions.has(session) && !this.sent.has(session)) return;
    this.sessions.delete(session);
    this.sent.delete(session);
    this.send(bridgeMessage(session, undefined, ++this.seq));
  }

  /** Sends every session's state again (the UI part started later). */
  resync(): void {
    for (const id of this.sessions.keys()) {
      this.sent.delete(id);
      this.push(id);
    }
  }

  push(session: string): void {
    const msg = bridgeMessage(session, this.sessions.get(session), this.seq + 1);
    if (this.sent.has(session) && this.sent.get(session) === msg.state) return;
    this.seq = msg.seq;
    this.sent.set(session, msg.state);
    this.send(msg);
  }
}
