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

// Dedupe: skip a report identical to the last one we sent (tabs.onUpdated fires
// several times per navigation — loading/complete/title — for the same URL).
let lastSent = "";

function loadConfig() {
  try {
    api.storage.local.get(DEFAULTS, (items) => {
      config = { ...DEFAULTS, ...(items || {}) };
    });
  } catch (e) {
    config = { ...DEFAULTS };
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

// Post one report. focused=false is sent on blur (url/title omitted) so the host
// stops attributing a URL to this browser when another app takes focus.
function send(url, title, focused) {
  const key = focused ? `1|${url || ""}` : "0";
  if (key === lastSent) return;
  lastSent = key;

  const body = JSON.stringify({
    browser: BROWSER,
    url: focused ? (url || null) : null,
    title: focused ? (title || null) : null,
    focused: !!focused,
    token: config.token || undefined,
  });
  // Fire-and-forget; the host may not be running — swallow the network error.
  fetch(endpoint(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  }).catch(() => { /* host not running / port closed — ignore */ });
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
  if (!tab || !tab.active) return;
  if (changeInfo.url || changeInfo.title || changeInfo.status === "complete") {
    send(tab.url, tab.title, true);
  }
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
