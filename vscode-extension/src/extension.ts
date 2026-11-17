// SPDX-License-Identifier: GPL-3.0-or-later
/**
 * PolyKybd Mode Reporter: the `vscode` API side.
 *
 * Reports whether this window has a debug session and whether its program is
 * running or stopped, to the PolyKybdHost on this computer, so the keycaps
 * show the debug keys that work now. See README.md; the wire format is in
 * core.ts.
 *
 * Signals used (all stable API):
 * - `debug.activeDebugSession`, `debug.onDidChangeActiveDebugSession`,
 *   `debug.onDidTerminateDebugSession`;
 * - `debug.registerDebugAdapterTrackerFactory('*', ...)`: the Debug Adapter
 *   Protocol messages, to tell a running program from a stopped one;
 * - `window.state.focused`, `window.onDidChangeWindowState`;
 * - `window.tabGroups.activeTabGroup.activeTab.input instanceof
 *   TabInputTextDiff`, `tabGroups.onDidChangeTabs` / `onDidChangeTabGroups`:
 *   whether a diff editor is the active editor tab;
 * - `commands.registerCommand(BRIDGE_STATE_COMMAND)`: the debug state the
 *   workspace part (remote/) reads in a remote extension host.
 */
import * as http from "http";
import * as vscode from "vscode";

import {
  activeMode, appToken, BRIDGE_STATE_COMMAND, BRIDGE_SYNC_COMMAND, HTTP_TIMEOUT_MS, InputClock,
  isTextDiff, KEEPALIVE_MS, modeUrl, payload, RemoteStates, ReportQueue, SendPolicy, SessionState,
  settleWithin, validPort,
} from "./core";

const sessions = new Map<string, SessionState>();
// States sent by the workspace part from a remote extension host.
const remote = new RemoteStates();
const policy = new SendPolicy();
let app = "vscode";
const clock = new InputClock(Date.now());
let reported = false;
let timer: ReturnType<typeof setInterval> | undefined;
let errorsShown = new Set<string>();
let output: vscode.OutputChannel | undefined;

// A dedicated agent: a loopback report must not go through a configured
// HTTP proxy, and must not wait behind other requests of the extension host.
const agent = new http.Agent({ keepAlive: false, maxSockets: 1 });
const queue = new ReportQueue(send);

function config() {
  const c = vscode.workspace.getConfiguration("polykybd");
  return {
    enabled: c.get<boolean>("reportMode", true),
    port: validPort(c.get<number>("port")),
    token: c.get<string>("token", "") || "",
  };
}

function post(port: number, body: string): void {
  queue.post(port, body);
}

/** One request. `done` can be called twice (request and response error);
 *  ReportQueue counts only the first. */
function send(port: number, body: string, done: () => void): void {
  const req = http.request({
    host: "127.0.0.1", port, path: "/report", method: "POST", agent,
    timeout: HTTP_TIMEOUT_MS,
    headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) },
  }, (res) => {
    res.resume();
    if (res.statusCode && res.statusCode >= 400) note(`HTTP ${res.statusCode}`);
    res.on("end", done);
    res.on("error", done);
  });
  req.on("timeout", () => req.destroy(new Error("timeout")));
  req.on("error", (e) => { note(`${e.name}: ${e.message}`); done(); });
  req.end(body);
}

/** Each distinct delivery error once, in the extension's output channel. */
function note(msg: string): void {
  if (errorsShown.has(msg)) return;
  errorsShown.add(msg);
  output?.appendLine(`Report not delivered: ${msg}`);
}

/** Whether the active editor tab is a text diff editor. */
function diffInFront(): boolean {
  const input = vscode.window.tabGroups?.activeTabGroup?.activeTab?.input;
  return isTextDiff(input, vscode.TabInputTextDiff);
}

/** The URL to report, or null when the active session has no tracker here
 *  and no state from the workspace part. */
function currentUrl(): string | null {
  const active = vscode.debug.activeDebugSession;
  const mode = activeMode(active !== undefined, active ? sessions.get(active.id) : undefined,
                          remote.get(active?.id));
  return mode ? modeUrl(app, mode, diffInFront()) : null;
}

function tick(force = false): void {
  const c = config();
  if (!c.enabled) {
    if (reported) withdraw(c.port, c.token);
    return;
  }
  const url = currentUrl();
  if (url === null) {
    if (reported) withdraw(c.port, c.token);
    return;
  }
  const focused = vscode.window.state.focused;
  const now = Date.now();
  if (!force && !policy.due(url, focused, now)) return;
  policy.sent(url, focused, now);
  reported = true;
  post(c.port, payload(app, url, focused, process.pid, clock.ageS(now), c.token));
}

function withdraw(port: number, token: string): void {
  reported = false;
  policy.reset();
  post(port, payload(app, null, false, process.pid, undefined, token));
}

function input(): void {
  clock.input(vscode.window.state.focused, Date.now());
}

export function activate(context: vscode.ExtensionContext): void {
  app = appToken(vscode.env.appName);
  output = vscode.window.createOutputChannel("PolyKybd Mode Reporter");
  context.subscriptions.push(output);

  context.subscriptions.push(
    vscode.debug.registerDebugAdapterTrackerFactory("*", {
      createDebugAdapterTracker(session: vscode.DebugSession) {
        const state = new SessionState();
        sessions.set(session.id, state);
        return {
          onWillReceiveMessage: (m: unknown) => state.toAdapter(m),
          onDidSendMessage: (m: unknown) => { state.fromAdapter(m); tick(); },
          onExit: () => { sessions.delete(session.id); tick(); },
        };
      },
    }),
    vscode.debug.onDidChangeActiveDebugSession(() => tick()),
    vscode.debug.onDidTerminateDebugSession((s) => { sessions.delete(s.id); remote.forget(s.id); tick(); }),
    // The workspace part (remote/) in a remote extension host calls this with
    // { v, session, state, seq } on every change of a session's state.
    vscode.commands.registerCommand(BRIDGE_STATE_COMMAND, (msg: unknown) => {
      if (remote.apply(msg)) tick();
    }),
    vscode.window.tabGroups.onDidChangeTabs(() => tick()),
    vscode.window.tabGroups.onDidChangeTabGroups(() => tick()),
    vscode.window.onDidChangeWindowState((s) => {
      if (s.focused) clock.focus(Date.now());
      tick();
    }),
    // Input in this window, counted only while it is focused: with several
    // windows open, the host follows the one with the newest input
    // (`input_age`).
    vscode.window.onDidChangeTextEditorSelection(input),
    vscode.window.onDidChangeActiveTextEditor(input),
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("polykybd")) {
        errorsShown = new Set();
        policy.reset();
        tick(true);
      }
    }),
  );

  timer = setInterval(() => tick(), KEEPALIVE_MS / 3);
  context.subscriptions.push({ dispose: () => { if (timer) clearInterval(timer); } });
  tick(true);
  // Sessions that started in a remote extension host before this part ran.
  // Fails when the workspace part is not installed or not active there: then
  // there is nothing to ask for.
  if (vscode.env.remoteName) {
    Promise.resolve(vscode.commands.executeCommand(BRIDGE_SYNC_COMMAND)).catch(() => undefined);
  }
}

/** Returns a promise, so the extension host waits for the last report (the
 *  withdrawal, and a report still on the way before it), at most two request
 *  timeouts. */
export function deactivate(): Promise<void> {
  if (timer) clearInterval(timer);
  timer = undefined;
  const c = config();
  if (reported) withdraw(c.port, c.token);
  return settleWithin(queue.idle(), 2 * HTTP_TIMEOUT_MS + 200);
}
