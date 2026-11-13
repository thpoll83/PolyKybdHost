/*
 * PolyKybd Website Reporter — shared background script (Chromium MV3 + Firefox MV3).
 *
 * Reports the focused tab's URL to the PolyKybdHost loopback receiver
 * (http://127.0.0.1:<port>/report) on every tab switch / navigation / window
 * focus change, so the host can show website-specific keycap overlays instead
 * of guessing from the window title. See ../README.md.
 *
 * No page content is read — only tab.url / tab.title (the same you see in the
 * address bar) and whether this browser window is focused. Everything is sent
 * to loopback only.
 */
"use strict";

// Firefox exposes `browser`; Chromium exposes `chrome`. The callback-style
// APIs used here exist on both.
const api = globalThis.browser ?? globalThis.chrome;

const DEFAULTS = { port: 50164, token: "" };
let config = { ...DEFAULTS };
let configLoaded = false;

// The latest state we WANT the host to hold, and the key of the last state we
// actually DELIVERED (a 200 from the receiver). The delivered key includes the
// receiver config (port|token), so changing the port/token re-sends, and it is
// only advanced on success — a failed send (wrong default port before config
// loaded, or host down) never suppresses the correct retry.
let desired = null;      // { url, title, focused }
let deliveredKey = "";

function configKey() {
  return `${config.port}|${config.token || ""}`;
}

function stateKey(s) {
  return `${configKey()}|${s.focused ? `1|${s.url || ""}` : "0"}`;
}

function loadConfig() {
  const done = (items) => {
    config = { ...DEFAULTS, ...(items || {}) };
    configLoaded = true;
    flush();  // re-deliver the latest desired state against the (new) config
  };
  try {
    api.storage.local.get(DEFAULTS, done);
  } catch (e) {
    done(null);
  }
}
loadConfig();
try {
  api.storage.onChanged.addListener(loadConfig);
} catch (e) { /* storage.onChanged unavailable — config stays at defaults */ }

function detectBrowser() {
  const ua = (navigator && navigator.userAgent) || "";
  if (globalThis.browser && ua.includes("Firefox")) return "firefox";
  if (navigator && navigator.brave) return "brave";
  if (ua.includes("Edg/")) return "edge";
  if (ua.includes("OPR/") || ua.includes("Opera")) return "opera";
  if (ua.includes("Vivaldi")) return "vivaldi";
  return "chrome";
}
const BROWSER = detectBrowser();

function endpoint() {
  return `http://127.0.0.1:${config.port}/report`;
}

// Deliver the latest desired state to the receiver, unless that exact state was
// already delivered to this exact receiver config. Called on every event and
// whenever the config (re)loads. focused=false is sent on blur (url/title
// omitted) so the host stops attributing a URL to this browser.
function flush() {
  if (!configLoaded || !desired) return;
  const key = stateKey(desired);
  if (key === deliveredKey) return;  // already delivered this state here

  const s = desired;
  const body = JSON.stringify({
    browser: BROWSER,
    url: s.focused ? (s.url || null) : null,
    title: s.focused ? (s.title || null) : null,
    focused: !!s.focused,
    token: config.token || undefined,
  });
  fetch(endpoint(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  }).then((r) => {
    // Only mark delivered on a real success — a failure leaves deliveredKey
    // as-is so the next event (or config reload) retries this state.
    if (r && r.ok) deliveredKey = key;
  }).catch(() => { /* host not running / port closed — retry on next event */ });
}

// Record the desired state and attempt delivery.
function send(url, title, focused) {
  desired = { url, title, focused: !!focused };
  flush();
}

// Report the active tab of the (focused) current window.
function reportActiveTab() {
  try {
    api.tabs.query({ active: true, lastFocusedWindow: true }, (tabs) => {
      if (api.runtime.lastError) return;
      const tab = tabs && tabs[0];
      if (!tab) return;
      send(tab.url, tab.title, true);
    });
  } catch (e) { /* ignore */ }
}

// --- Events that change which website is in front ---

// Switched tab within a window.
api.tabs.onActivated.addListener(() => reportActiveTab());

// Navigation / title change / load complete in a tab. Only the active tab
// matters; changeInfo tells us it's worth re-reporting.
api.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (!tab || !tab.active) return;  // active WITHIN its window, not necessarily foreground
  if (!(changeInfo.url || changeInfo.title || changeInfo.status === "complete")) return;
  // tab.active only means active in its own window; a navigation in an
  // unfocused browser window must NOT replace the foreground window's URL. Only
  // report when this tab's window is the focused one.
  try {
    api.windows.get(tab.windowId, (win) => {
      if (api.runtime.lastError) return;
      if (win && win.focused) send(tab.url, tab.title, true);
    });
  } catch (e) { /* ignore */ }
});

// Window focus changed (alt-tab between browser windows, or away from the
// browser entirely). WINDOW_ID_NONE = the browser lost focus to another app.
api.windows.onFocusChanged.addListener((windowId) => {
  const NONE = (api.windows && api.windows.WINDOW_ID_NONE) ?? -1;
  if (windowId === NONE) {
    send(null, null, false);
    return;
  }
  try {
    api.tabs.query({ active: true, windowId }, (tabs) => {
      if (api.runtime.lastError) return;
      const tab = tabs && tabs[0];
      if (tab) send(tab.url, tab.title, true);
    });
  } catch (e) { /* ignore */ }
});

// Report once on startup/install so the host has a value immediately.
try { api.runtime.onStartup.addListener(() => reportActiveTab()); } catch (e) {}
try { api.runtime.onInstalled.addListener(() => reportActiveTab()); } catch (e) {}
reportActiveTab();

// --- Commands from the host (agent keys: Claude Code cloud sessions) ---
//
// The host cannot call the extension, so the extension asks: GET /command is
// held open by the host for up to 20 s and answers with the next command, or
// none. The only command is {id, focus_url}: activate the tab whose URL is
// exactly focus_url and focus its window. Nothing is ever opened; a URL that
// no tab has is answered with found: false. The host sends only claude.ai
// session pages. The custom header keeps web pages out (it forces a CORS
// preflight, which these paths never grant).

const COMMAND_HEADERS = () => {
  const h = { "X-PolyKybd-Extension": "1" };
  if (config.token) h["X-PolyKybd-Token"] = config.token;
  return h;
};
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let commandLoopRunning = false;

function promised(fn, ...args) {
  // The callback form exists on both browsers; wrap it once.
  return new Promise((resolve) => {
    try {
      fn(...args, (value) => resolve(api.runtime.lastError ? undefined : value));
    } catch (e) {
      resolve(undefined);
    }
  });
}

function sameUrl(a, b) {
  // Exact match, ignoring only a #fragment the page may have added.
  return typeof a === "string" && typeof b === "string"
    && a.split("#", 1)[0] === b.split("#", 1)[0];
}

async function focusUrl(url) {
  const tabs = (await promised(api.tabs.query.bind(api.tabs), {})) || [];
  const tab = tabs.find((t) => sameUrl(t.url, url));
  if (!tab) return false;
  // The tab can close between the query and the update: then it was not found.
  const updated = await promised(api.tabs.update.bind(api.tabs), tab.id, { active: true });
  if (!updated) return false;
  // A refused window focus still counts as found: the host brings the window
  // forward itself, and the tab is the active one now.
  await promised(api.windows.update.bind(api.windows), tab.windowId, { focused: true });
  return true;
}

async function runCommand(command) {
  if (!command || typeof command.id !== "number") return;
  const found = typeof command.focus_url === "string"
    && command.focus_url.startsWith("https://claude.ai/code/session_")
    && await focusUrl(command.focus_url);
  try {
    await fetch(`http://127.0.0.1:${config.port}/command_result`, {
      method: "POST",
      headers: { ...COMMAND_HEADERS(), "Content-Type": "application/json" },
      body: JSON.stringify({ id: command.id, found: !!found }),
    });
  } catch (e) { /* the host stopped; it gives up after its own timeout */ }
}

async function commandLoop() {
  if (commandLoopRunning) return;
  commandLoopRunning = true;
  try {
    for (;;) {
      // An extension API call keeps a Chromium service worker alive between
      // the waits (it stops one after 30 s without events or API calls).
      await promised(api.runtime.getPlatformInfo.bind(api.runtime));
      if (!configLoaded) { await sleep(500); continue; }
      let reply = null;
      try {
        const r = await fetch(`http://127.0.0.1:${config.port}/command`,
                              { headers: COMMAND_HEADERS() });
        reply = r.ok ? await r.json() : null;
      } catch (e) { reply = null; }
      if (!reply) { await sleep(10000); continue; }   // no host: try again later
      if (reply.command) await runCommand(reply.command);
    }
  } finally {
    commandLoopRunning = false;
  }
}

// Started here, and again by any browser event after the worker was stopped.
commandLoop();
for (const ev of [api.tabs.onActivated, api.windows.onFocusChanged, api.tabs.onUpdated]) {
  try { ev.addListener(() => commandLoop()); } catch (e) { /* ignore */ }
}
