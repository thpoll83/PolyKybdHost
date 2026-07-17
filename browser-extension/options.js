"use strict";

const api = globalThis.browser ?? globalThis.chrome;
const DEFAULTS = { port: 50164, token: "" };

const portEl = document.getElementById("port");
const tokenEl = document.getElementById("token");
const statusEl = document.getElementById("status");

function setStatus(msg, ok) {
  statusEl.textContent = msg;
  statusEl.className = ok ? "ok" : "err";
}

api.storage.local.get(DEFAULTS, (items) => {
  const cfg = { ...DEFAULTS, ...(items || {}) };
  portEl.value = cfg.port;
  tokenEl.value = cfg.token;
});

document.getElementById("save").addEventListener("click", () => {
  const port = parseInt(portEl.value, 10);
  if (!port || port < 1 || port > 65535) {
    setStatus("Invalid port", false);
    return;
  }
  api.storage.local.set({ port, token: tokenEl.value.trim() }, () => {
    setStatus("Saved", true);
  });
});

document.getElementById("test").addEventListener("click", () => {
  const port = parseInt(portEl.value, 10) || DEFAULTS.port;
  setStatus("Testing…", true);
  fetch(`http://127.0.0.1:${port}/ping`)
    .then((r) => r.json())
    .then((j) => {
      if (j && j.ok && j.app === "PolyKybdHost") setStatus("Connected to PolyKybdHost ✓", true);
      else setStatus("Unexpected response", false);
    })
    .catch(() => setStatus("No response — is PolyKybdHost running with browser detection on?", false));
});
