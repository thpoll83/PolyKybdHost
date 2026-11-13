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
 * - `window.state.focused`, `window.onDidChangeWindowState`.
 */
import * as http from "http";
import * as vscode from "vscode";

import {
  appToken, HTTP_TIMEOUT_MS, KEEPALIVE_MS, modeFor, modeUrl, payload,
  SendPolicy, SessionState, validPort,
} from "./core";

const sessions = new Map<string, SessionState>();
const policy = new SendPolicy();
let app = "vscode";
let lastInput = Date.now();
let reported = false;
let timer: ReturnType<typeof setInterval> | undefined;
let errorsShown = new Set<string>();
let output: vscode.OutputChannel | undefined;

// A dedicated agent: a loopback report must not go through a configured
// HTTP proxy, and must not wait behind other requests of the extension host.
const agent = new http.Agent({ keepAlive: false, maxSockets: 1 });
let inFlight = false;
let queued: { port: number; body: string } | null = null;

function config() {
  const c = vscode.workspace.getConfiguration("polykybd");
  return {
    enabled: c.get<boolean>("reportMode", true),
    port: validPort(c.get<number>("port")),
    token: c.get<string>("token", "") || "",
  };
}

function post(port: number, body: string): void {
  // Only the newest report matters: a report waiting behind a slow one is
  // replaced, never queued up.
  if (inFlight) {
    queued = { port, body };
    return;
  }
  inFlight = true;
  const done = () => {
    inFlight = false;
    const next = queued;
    queued = null;
    if (next) post(next.port, next.body);
  };
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

function currentUrl(): string {
  const active = vscode.debug.activeDebugSession;
  return modeUrl(app, modeFor(active ? sessions.get(active.id) ?? new SessionState() : undefined));
}

function tick(force = false): void {
  const c = config();
  if (!c.enabled) {
    if (reported) withdraw(c.port, c.token);
    return;
  }
  const url = currentUrl();
  const focused = vscode.window.state.focused;
  const now = Date.now();
  if (!force && !policy.due(url, focused, now)) return;
  policy.sent(url, focused, now);
  reported = true;
  post(c.port, payload(app, url, focused, process.pid, (now - lastInput) / 1000, c.token));
}

function withdraw(port: number, token: string): void {
  reported = false;
  policy.reset();
  post(port, payload(app, null, false, process.pid, undefined, token));
}

function input(): void {
  lastInput = Date.now();
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
    vscode.debug.onDidTerminateDebugSession((s) => { sessions.delete(s.id); tick(); }),
    vscode.window.onDidChangeWindowState((s) => {
      if (s.focused) input();
      tick();
    }),
    // Input in this window: with several windows open, the host follows the
    // one with the newest input (`input_age`).
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
}

export function deactivate(): void {
  if (timer) clearInterval(timer);
  timer = undefined;
  const c = config();
  if (reported) withdraw(c.port, c.token);
}
