// The plugin's Obsidian-free core (src/core.ts). Node strips the TypeScript
// types itself (Node 22.18+), so this needs no build step and no npm install:
//
//     node --test obsidian-plugin/test/core.test.mjs
//
// tests/obsidian_plugin/plugin_core_test.py runs it in the host suite.
import assert from "node:assert/strict";
import test from "node:test";

import {
    APP, DEFAULT_PORT, KEEPALIVE_MS, POLL_MS, SendPolicy, Sender, VIEW_TOKENS, VIM_TOKENS,
    contextUrl, payload, reportUrl, viewToken, vimToken,
} from "../src/core.ts";

test("markdown views", () => {
    assert.equal(viewToken({ viewType: "markdown", mode: "preview" }), "reading");
    assert.equal(viewToken({ viewType: "markdown", mode: "source", livePreview: true }), "live");
    assert.equal(viewToken({ viewType: "markdown", mode: "source", livePreview: false }), "source");
    // Live Preview is Obsidian's default, so an unknown flag reads as live.
    assert.equal(viewToken({ viewType: "markdown", mode: "source", livePreview: null }), "live");
    assert.equal(viewToken({ viewType: "markdown", mode: null }), "other");
});

test("other views", () => {
    assert.equal(viewToken({ viewType: "canvas" }), "canvas");
    assert.equal(viewToken({ viewType: "graph" }), "graph");
    assert.equal(viewToken({ viewType: "localgraph" }), "graph");
    for (const t of ["pdf", "image", "file-explorer", "empty", "", null]) {
        assert.equal(viewToken({ viewType: t }), "other", String(t));
    }
});

test("vim modes", () => {
    assert.equal(vimToken(null), null);
    assert.equal(vimToken(undefined), null);
    assert.equal(vimToken({}), "vim-normal");
    assert.equal(vimToken({ insertMode: false, visualMode: false }), "vim-normal");
    assert.equal(vimToken({ insertMode: true }), "vim-insert");
    assert.equal(vimToken({ insertMode: true, overwrite: true }), "vim-replace");
    assert.equal(vimToken({ visualMode: true }), "vim-visual");
    // Overwrite alone (Insert-key overwrite without Vim's Insert mode) is Normal.
    assert.equal(vimToken({ overwrite: true }), "vim-normal");
});

test("the URL carries the Vim mode only in the editor", () => {
    assert.equal(contextUrl("live", "vim-normal"), "obsidian://live/vim-normal");
    assert.equal(contextUrl("source", "vim-visual"), "obsidian://source/vim-visual");
    assert.equal(contextUrl("live"), "obsidian://live");
    assert.equal(contextUrl("reading", "vim-normal"), "obsidian://reading");
    assert.equal(contextUrl("canvas", "vim-insert"), "obsidian://canvas");
    // Every token is short, lower case and URL-safe.
    for (const t of [...VIEW_TOKENS, ...VIM_TOKENS]) assert.match(t, /^[a-z-]+$/);
});

test("send on change and as a keep-alive", () => {
    const p = new SendPolicy(3000);
    assert.ok(p.due("u1", 0));
    p.sent("u1", 0);
    assert.ok(!p.due("u1", 2999));
    assert.ok(p.due("u2", 1000));
    assert.ok(p.due("u1", 3000));
    assert.ok(!p.due(null, 99999));
});

test("timing fits the host", () => {
    // Two lost keep-alives still land inside the host's 8 s freshness window.
    assert.ok(KEEPALIVE_MS * 2 < 8000);
    assert.ok(POLL_MS >= 500);
    assert.equal(DEFAULT_PORT, 50164);
    assert.equal(reportUrl(50164), "http://127.0.0.1:50164/report");
});

test("the payload has the allowed fields only", () => {
    assert.deepEqual(JSON.parse(payload("obsidian://live")),
                     { app: APP, url: "obsidian://live", focused: true });
    assert.equal(APP, "obsidian");
    const full = JSON.parse(payload("obsidian://canvas",
                                    { token: "t", pid: 7, inputAge: 1.234 }));
    assert.deepEqual(full, { app: "obsidian", url: "obsidian://canvas", focused: true,
                             pid: 7, input_age: 1.2, token: "t" });
    assert.deepEqual(JSON.parse(payload(null, { focused: false, pid: 7 })),
                     { app: "obsidian", url: null, focused: false, pid: 7 });
    // Nonsense pid / age are left out, a negative age is clamped.
    const odd = JSON.parse(payload("u", { pid: -1, inputAge: NaN }));
    assert.ok(!("pid" in odd) && !("input_age" in odd));
    assert.equal(JSON.parse(payload("u", { inputAge: -5 })).input_age, 0);
});

test("the sender delivers the latest report and survives failures", async () => {
    const got = [];
    let release;
    const gate = new Promise((r) => { release = r; });
    const logs = [];
    let first = true;
    const s = new Sender(async (url, body) => {
        if (first) { first = false; await gate; throw new Error("ECONNREFUSED"); }
        got.push([url, JSON.parse(body).url]);
    }, (m) => logs.push(m));
    const p1 = s.submit(50164, payload("a"));
    s.submit(50164, payload("b"));          // replaced before it is sent
    s.submit(50165, payload("c"));
    release();
    await p1;
    await s.pump();
    assert.deepEqual(got, [["http://127.0.0.1:50165/report", "c"]]);
    assert.equal(logs.length, 1);
    assert.match(logs[0], /ECONNREFUSED/);
});
