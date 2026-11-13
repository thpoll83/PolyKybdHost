// SPDX-License-Identifier: GPL-3.0-or-later
// Unit tests for src/core.ts, without the editor:
//   node --experimental-strip-types --test test/core.test.ts      (Node 22.6+; 22.18+ without the flag)
// tests/vscode_extension/core_test.py runs this from the host suite when Node is installed.
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  appToken, DEFAULT_PORT, modeFor, modeUrl, payload, SendPolicy, SessionState, validPort,
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
  assert.ok(s.pending.size <= 64);
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
