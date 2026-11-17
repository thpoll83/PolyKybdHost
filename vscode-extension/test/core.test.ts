// SPDX-License-Identifier: GPL-3.0-or-later
// Unit tests for src/core.ts, without the editor:
//   node --experimental-strip-types --experimental-detect-module --test test/core.test.ts
//   (Node 22.6+; 22.18+ needs neither flag)
// tests/vscode_extension/extension_core_test.py runs this from the host suite when Node is installed.
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  activeMode, appToken, BRIDGE_VERSION, bridgeMessage, DEFAULT_PORT, InputClock, isTextDiff,
  MAX_ENTRIES, MAX_REMOTE_SESSIONS, modeFor, modeUrl, parseBridgeMessage, payload, RemoteStates, ReportQueue,
  SendPolicy, SessionState, settleWithin, validPort, WorkspaceBridge,
} from "../src/core.ts";

test("app token follows env.appName", () => {
  assert.equal(appToken("Visual Studio Code"), "vscode");
  assert.equal(appToken("Visual Studio Code - Insiders"), "vscode");
  assert.equal(appToken("Cursor"), "cursor");
  assert.equal(appToken("Windsurf"), "windsurf");
  assert.equal(appToken("Devin"), "windsurf");
  assert.equal(appToken(undefined), "vscode");
});

test("mode URLs", () => {
  assert.equal(modeUrl("vscode", modeFor(undefined)), "vscode://edit");
  const s = new SessionState();
  assert.equal(modeUrl("cursor", modeFor(s)), "cursor://debug/running");
  s.fromAdapter({ type: "event", event: "stopped", body: { threadId: 1, reason: "breakpoint" } });
  assert.equal(modeUrl("windsurf", modeFor(s)), "windsurf://debug/stopped");
});

test("a stopped event stops, a continued event resumes", () => {
  const s = new SessionState();
  assert.equal(s.isStopped(), false);
  s.fromAdapter({ type: "event", event: "stopped", body: { threadId: 3 } });
  assert.equal(s.isStopped(), true);
  s.fromAdapter({ type: "event", event: "continued", body: { threadId: 3 } });
  assert.equal(s.isStopped(), false);
});

test("continued with allThreadsContinued false resumes only that thread", () => {
  const s = new SessionState();
  s.fromAdapter({ type: "event", event: "stopped", body: { threadId: 1 } });
  s.fromAdapter({ type: "event", event: "stopped", body: { threadId: 2 } });
  s.fromAdapter({ type: "event", event: "continued", body: { threadId: 1, allThreadsContinued: false } });
  assert.equal(s.isStopped(), true);
  s.fromAdapter({ type: "event", event: "continued", body: { threadId: 2, allThreadsContinued: false } });
  assert.equal(s.isStopped(), false);
});

test("a successful step response resumes, a failed one does not", () => {
  const s = new SessionState();
  s.fromAdapter({ type: "event", event: "stopped", body: { threadId: 1, allThreadsStopped: true } });
  s.toAdapter({ type: "request", seq: 10, command: "next", arguments: { threadId: 1 } });
  s.fromAdapter({ type: "response", request_seq: 10, success: false, command: "next" });
  assert.equal(s.isStopped(), true);
  s.toAdapter({ type: "request", seq: 11, command: "next", arguments: { threadId: 1 } });
  s.fromAdapter({ type: "response", request_seq: 11, success: true, command: "next" });
  assert.equal(s.isStopped(), false);
});

test("continue response: missing allThreadsContinued means every thread", () => {
  const s = new SessionState();
  s.fromAdapter({ type: "event", event: "stopped", body: { threadId: 1 } });
  s.fromAdapter({ type: "event", event: "stopped", body: { threadId: 2 } });
  s.toAdapter({ type: "request", seq: 5, command: "continue", arguments: { threadId: 1 } });
  s.fromAdapter({ type: "response", request_seq: 5, success: true, command: "continue", body: {} });
  assert.equal(s.isStopped(), false);
});

test("single-thread step resumes only that thread", () => {
  const s = new SessionState();
  s.fromAdapter({ type: "event", event: "stopped", body: { threadId: 1 } });
  s.fromAdapter({ type: "event", event: "stopped", body: { threadId: 2 } });
  s.toAdapter({ type: "request", seq: 7, command: "stepIn", arguments: { threadId: 1, singleThread: true } });
  s.fromAdapter({ type: "response", request_seq: 7, success: true, command: "stepIn" });
  assert.equal(s.isStopped(), true);
});

test("other requests and events change nothing; pending map is bounded", () => {
  const s = new SessionState();
  s.toAdapter({ type: "request", seq: 1, command: "evaluate", arguments: {} });
  s.fromAdapter({ type: "event", event: "output", body: { output: "x" } });
  assert.equal(s.isStopped(), false);
  for (let i = 0; i < 200; i++) s.toAdapter({ type: "request", seq: i, command: "next", arguments: {} });
  assert.ok(s.pending.size <= MAX_ENTRIES);
  s.toAdapter(null);
  s.fromAdapter(undefined);
});

test("send policy: on change, then keep-alive", () => {
  const p = new SendPolicy(3000);
  assert.equal(p.due("vscode://edit", true, 0), true);
  p.sent("vscode://edit", true, 0);
  assert.equal(p.due("vscode://edit", true, 1000), false);
  assert.equal(p.due("vscode://edit", false, 1000), true);   // focus change
  assert.equal(p.due("vscode://debug/running", true, 1000), true);
  assert.equal(p.due("vscode://edit", true, 3000), true);
  p.reset();
  assert.equal(p.due("vscode://edit", true, 3001), true);
});

test("payload has only the contract's fields", () => {
  const body = JSON.parse(payload("vscode", "vscode://debug/stopped", true, 4242, 0.44));
  assert.deepEqual(body, { app: "vscode", url: "vscode://debug/stopped", focused: true, pid: 4242, input_age: 0.4 });
  assert.deepEqual(JSON.parse(payload("cursor", null, false, 1, undefined, "secret")),
                   { app: "cursor", url: null, focused: false, pid: 1, token: "secret" });
  assert.equal(JSON.parse(payload("vscode", "vscode://edit", true, 1, -5)).input_age, 0);
});

test("port setting", () => {
  assert.equal(validPort(8080), 8080);
  assert.equal(validPort(0), DEFAULT_PORT);
  assert.equal(validPort("x"), DEFAULT_PORT);
  assert.equal(validPort(70000), DEFAULT_PORT);
});

test("all threads stopped: a single-thread resume leaves the others stopped", () => {
  const s = new SessionState();
  s.fromAdapter({ type: "event", event: "stopped", body: { threadId: 1, allThreadsStopped: true } });
  s.toAdapter({ type: "request", seq: 20, command: "next", arguments: { threadId: 1, singleThread: true } });
  s.fromAdapter({ type: "response", request_seq: 20, success: true, command: "next" });
  assert.equal(s.isStopped(), true);   // no thread list: thread 2 may exist

  s.fromAdapter({ type: "event", event: "stopped", body: { threadId: 1, allThreadsStopped: true } });
  s.toAdapter({ type: "request", seq: 21, command: "threads" });
  s.fromAdapter({ type: "response", request_seq: 21, success: true, command: "threads",
                  body: { threads: [{ id: 1, name: "main" }, { id: 2, name: "worker" }] } });
  s.toAdapter({ type: "request", seq: 22, command: "continue", arguments: { threadId: 1, singleThread: true } });
  s.fromAdapter({ type: "response", request_seq: 22, success: true, command: "continue",
                  body: { allThreadsContinued: false } });
  assert.equal(s.isStopped(), true);   // thread 2 is still stopped
  s.fromAdapter({ type: "event", event: "continued", body: { threadId: 2, allThreadsContinued: false } });
  assert.equal(s.isStopped(), false);  // every listed thread resumed
});

test("all threads stopped, one thread listed: its resume runs the program", () => {
  const s = new SessionState();
  s.fromAdapter({ type: "event", event: "stopped", body: { threadId: 1, allThreadsStopped: true } });
  s.toAdapter({ type: "request", seq: 1, command: "threads" });
  s.fromAdapter({ type: "response", request_seq: 1, success: true, command: "threads",
                  body: { threads: [{ id: 1, name: "main" }] } });
  s.toAdapter({ type: "request", seq: 2, command: "stepIn", arguments: { threadId: 1, singleThread: true } });
  s.fromAdapter({ type: "response", request_seq: 2, success: true, command: "stepIn" });
  assert.equal(s.isStopped(), false);
  // A new all-threads stop starts over.
  s.fromAdapter({ type: "event", event: "stopped", body: { threadId: 1, allThreadsStopped: true } });
  assert.equal(s.isStopped(), true);
});

test("a session with no tracker reports nothing, not running", () => {
  assert.equal(activeMode(false, undefined), "edit");
  assert.equal(activeMode(true, undefined), null);
  assert.equal(activeMode(true, new SessionState()), "debug/running");
});

test("input counts only while the window is focused", () => {
  const c = new InputClock(0);
  c.input(false, 5000);
  assert.equal(c.ageS(6000), 6);
  c.input(true, 5000);
  assert.equal(c.ageS(6000), 1);
  c.focus(5900);
  assert.equal(c.ageS(6000), 0.1);
});

test("report queue: one at a time, the newest waiting report replaces older ones", () => {
  const sent: string[] = [];
  const pending: Array<() => void> = [];
  const q = new ReportQueue((_port, body, done) => { sent.push(body); pending.push(done); });
  q.post(1, "a");
  q.post(1, "b");
  q.post(1, "c");
  assert.deepEqual(sent, ["a"]);
  pending.shift()!();
  assert.deepEqual(sent, ["a", "c"]);
});

test("report queue: a second done() for the same request changes nothing", () => {
  const sent: string[] = [];
  const pending: Array<() => void> = [];
  const q = new ReportQueue((_port, body, done) => { sent.push(body); pending.push(done); });
  q.post(1, "a");
  q.post(1, "b");
  const doneA = pending.shift()!;
  doneA();                       // starts "b"
  assert.deepEqual(sent, ["a", "b"]);
  doneA();                       // the request's second error event
  assert.equal(q.inFlight, true); // "b" is still on the way
  q.post(1, "c");
  q.post(1, "d");
  assert.deepEqual(sent, ["a", "b"]);
  assert.deepEqual(q.queued, { port: 1, body: "d" });
});

test("report queue: idle() waits for the waiting report too", async () => {
  const pending: Array<() => void> = [];
  const q = new ReportQueue((_port, _body, done) => { pending.push(done); });
  await q.idle();                // nothing on the way
  q.post(1, "a");
  q.post(1, "withdraw");
  let settled = false;
  const idle = q.idle().then(() => { settled = true; });
  pending.shift()!();
  await Promise.resolve();
  assert.equal(settled, false);  // the withdrawal is on the way now
  pending.shift()!();
  await idle;
  assert.equal(settled, true);
});

test("settleWithin: resolves at the limit when the report never ends", async () => {
  const start = Date.now();
  await settleWithin(new Promise<void>(() => {}), 30);
  assert.ok(Date.now() - start >= 25);
  await settleWithin(Promise.resolve(), 10000);   // resolves at once, timer cleared
});

// --- stale thread list (CodeRabbit on #839, reply to 4567312574) -----------

function threads(s: SessionState, seq: number, ids: number[]): void {
  s.toAdapter({ type: "request", seq, command: "threads" });
  s.fromAdapter({ type: "response", request_seq: seq, success: true, command: "threads",
                  body: { threads: ids.map((id) => ({ id })) } });
}

test("a new all-threads stop drops the old thread list", () => {
  const s = new SessionState();
  s.fromAdapter({ type: "event", event: "stopped", body: { threadId: 1, allThreadsStopped: true } });
  threads(s, 1, [1]);
  s.fromAdapter({ type: "event", event: "continued", body: { threadId: 1 } });
  // Thread 2 starts while running; the next stop stops both, and the step on
  // thread 1 comes before a fresh threads response.
  s.fromAdapter({ type: "event", event: "stopped", body: { threadId: 1, allThreadsStopped: true } });
  s.toAdapter({ type: "request", seq: 2, command: "next", arguments: { threadId: 1, singleThread: true } });
  s.fromAdapter({ type: "response", request_seq: 2, success: true, command: "next" });
  assert.equal(s.isStopped(), true, "thread 2 is still stopped");
  // The fresh list names thread 2, which has not resumed.
  threads(s, 3, [1, 2]);
  assert.equal(s.isStopped(), true);
  s.toAdapter({ type: "request", seq: 4, command: "next", arguments: { threadId: 2, singleThread: true } });
  s.fromAdapter({ type: "response", request_seq: 4, success: true, command: "next" });
  assert.equal(s.isStopped(), false);
});

test("a threads response requested before the latest stop is ignored", () => {
  const s = new SessionState();
  s.toAdapter({ type: "request", seq: 1, command: "threads" });
  s.fromAdapter({ type: "event", event: "stopped", body: { threadId: 1, allThreadsStopped: true } });
  s.fromAdapter({ type: "response", request_seq: 1, success: true, command: "threads",
                  body: { threads: [{ id: 1 }] } });
  assert.equal(s.threads, null);
  s.toAdapter({ type: "request", seq: 2, command: "next", arguments: { threadId: 1, singleThread: true } });
  s.fromAdapter({ type: "response", request_seq: 2, success: true, command: "next" });
  assert.equal(s.isStopped(), true);
});

// --- diff view --------------------------------------------------------------

test("diff URLs keep the debug mode first", () => {
  assert.equal(modeUrl("vscode", "edit", true), "vscode://edit/diff");
  assert.equal(modeUrl("cursor", "debug/running", true), "cursor://debug/running/diff");
  assert.equal(modeUrl("windsurf", "debug/stopped", true), "windsurf://debug/stopped/diff");
  assert.equal(modeUrl("vscode", "debug/stopped", false), "vscode://debug/stopped");
  // A host that routes on the debug mode alone still finds it.
  assert.ok(modeUrl("vscode", "debug/stopped", true).includes("vscode://debug/stopped"));
  assert.ok(modeUrl("vscode", "edit", true).includes("vscode://edit"));
});

test("only a text diff tab counts as a diff", () => {
  class TabInputTextDiff { }
  class TabInputNotebookDiff { }
  class TabInputText { }
  assert.equal(isTextDiff(new TabInputTextDiff(), TabInputTextDiff), true);
  assert.equal(isTextDiff(new TabInputNotebookDiff(), TabInputTextDiff), false);
  assert.equal(isTextDiff(new TabInputText(), TabInputTextDiff), false);
  assert.equal(isTextDiff(undefined, TabInputTextDiff), false);
  // An editor without the class (older than the tab API) reports no diff.
  assert.equal(isTextDiff(new TabInputTextDiff(), undefined), false);
});

// --- bridge from a remote extension host -----------------------------------

test("activeMode: a local tracker takes priority, then the remote state", () => {
  const local = new SessionState();
  assert.equal(activeMode(true, local, "stopped"), "debug/running");
  assert.equal(activeMode(true, undefined, "stopped"), "debug/stopped");
  assert.equal(activeMode(true, undefined, "running"), "debug/running");
  assert.equal(activeMode(true, undefined, null), null);
  assert.equal(activeMode(true, undefined, undefined), null);
  assert.equal(activeMode(false, undefined, "stopped"), "edit");
});

test("bridge messages: only well-formed ones are read", () => {
  const ok = { v: BRIDGE_VERSION, session: "abc", state: "stopped", seq: 3 };
  assert.deepEqual(parseBridgeMessage(ok), ok);
  assert.deepEqual(parseBridgeMessage({ ...ok, state: null }), { ...ok, state: null });
  // extra fields are dropped
  assert.deepEqual(parseBridgeMessage({ ...ok, file: "/home/x/secret.py" }), ok);
  for (const bad of [undefined, null, "x", 3, {}, { ...ok, v: 2 }, { ...ok, session: "" },
                     { ...ok, session: 5 }, { ...ok, state: "paused" }, { ...ok, seq: -1 },
                     { ...ok, seq: 1.5 }, { ...ok, seq: "1" }]) {
    assert.equal(parseBridgeMessage(bad), null, JSON.stringify(bad));
  }
  const s = new SessionState();
  assert.deepEqual(bridgeMessage("id", s, 1), { v: BRIDGE_VERSION, session: "id", state: "running", seq: 1 });
  s.fromAdapter({ type: "event", event: "stopped", body: { threadId: 1 } });
  assert.equal(bridgeMessage("id", s, 2).state, "stopped");
  assert.equal(bridgeMessage("id", undefined, 3).state, null);
});

test("remote states: newer seq wins, a late message cannot revive an ended session", () => {
  const r = new RemoteStates();
  assert.equal(r.apply({ v: 1, session: "a", state: "running", seq: 1 }), true);
  assert.equal(r.apply({ v: 1, session: "a", state: "stopped", seq: 2 }), true);
  assert.equal(r.get("a"), "stopped");
  assert.equal(r.apply({ v: 1, session: "a", state: "running", seq: 2 }), false, "same seq");
  assert.equal(r.apply({ v: 1, session: "a", state: "stopped", seq: 3 }), false, "no change");
  assert.equal(r.apply({ v: 1, session: "a", state: null, seq: 4 }), true);
  assert.equal(r.get("a"), undefined);
  assert.equal(r.apply({ v: 1, session: "a", state: "running", seq: 3 }), false, "late");
  assert.equal(r.get("a"), undefined);
  assert.equal(r.apply("junk"), false);
  assert.equal(r.get(undefined), undefined);
  r.apply({ v: 1, session: "b", state: "stopped", seq: 5 });
  r.forget("b");
  assert.equal(r.get("b"), undefined);
});

test("remote states are bounded", () => {
  const r = new RemoteStates();
  for (let i = 0; i < MAX_REMOTE_SESSIONS + 10; i++) r.apply({ v: 1, session: `s${i}`, state: "running", seq: i });
  assert.equal(r.states.size, MAX_REMOTE_SESSIONS);
  assert.equal(r.seqs.size, MAX_REMOTE_SESSIONS);
  assert.equal(r.get("s0"), undefined);
  assert.equal(r.get(`s${MAX_REMOTE_SESSIONS + 9}`), "running");
});

test("workspace bridge: sends on a change of state only", () => {
  const sent: any[] = [];
  const b = new WorkspaceBridge((m) => sent.push(m));
  const t = b.track("s1");
  assert.deepEqual(sent.map((m) => m.state), ["running"]);
  t.fromAdapter({ type: "event", event: "output", body: { output: "hello" } });
  t.fromAdapter({ type: "event", event: "stopped", body: { threadId: 1 } });
  t.fromAdapter({ type: "event", event: "stopped", body: { threadId: 1 } });
  t.toAdapter({ type: "request", seq: 7, command: "continue", arguments: { threadId: 1 } });
  t.fromAdapter({ type: "response", request_seq: 7, success: true, command: "continue", body: {} });
  t.exit();
  b.end("s1"); // the terminate event after onExit: nothing more
  assert.deepEqual(sent.map((m) => m.state), ["running", "stopped", "running", null]);
  const seqs = sent.map((m) => m.seq);
  assert.deepEqual(seqs, [...seqs].sort((x, y) => x - y));
  assert.equal(new Set(seqs).size, seqs.length);
});

test("workspace bridge: resync sends every live session again", () => {
  const sent: any[] = [];
  const b = new WorkspaceBridge((m) => sent.push(m));
  b.track("a");
  const tb = b.track("b");
  tb.fromAdapter({ type: "event", event: "stopped", body: { threadId: 1 } });
  b.end("a");
  sent.length = 0;
  b.resync();
  assert.deepEqual(sent.map((m) => [m.session, m.state]), [["b", "stopped"]]);
});

test("bridge end to end: remote tracker to the URL the UI part reports", () => {
  const ui = new RemoteStates();
  // The command argument crosses the extension hosts as JSON.
  const b = new WorkspaceBridge((m) => ui.apply(JSON.parse(JSON.stringify(m))));
  const t = b.track("session-1");
  const url = () => {
    const mode = activeMode(true, undefined, ui.get("session-1"));
    return mode ? modeUrl("vscode", mode, true) : null;
  };
  assert.equal(url(), "vscode://debug/running/diff");
  t.fromAdapter({ type: "event", event: "stopped", body: { threadId: 1, allThreadsStopped: true } });
  assert.equal(url(), "vscode://debug/stopped/diff");
  t.exit();
  assert.equal(url(), null);
});
