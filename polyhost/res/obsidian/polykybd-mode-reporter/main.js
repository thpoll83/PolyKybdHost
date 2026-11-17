"use strict";
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// src/main.ts
var main_exports = {};
__export(main_exports, {
  default: () => PolyKybdModeReporter
});
module.exports = __toCommonJS(main_exports);
var import_obsidian = require("obsidian");

// src/core.ts
var APP = "obsidian";
var DEFAULT_PORT = 50164;
var KEEPALIVE_MS = 3e3;
var POLL_MS = 500;
function viewToken(info) {
  switch (info.viewType) {
    case "markdown":
      if (info.mode === "preview") return "reading";
      if (info.mode === "source") return info.livePreview === false ? "source" : "live";
      return "other";
    case "canvas":
      return "canvas";
    case "graph":
    case "localgraph":
      return "graph";
    default:
      return "other";
  }
}
function vimToken(state) {
  if (!state) return null;
  if (state.insertMode) return state.overwrite ? "vim-replace" : "vim-insert";
  if (state.visualMode) return "vim-visual";
  return "vim-normal";
}
function contextUrl(view, vim = null) {
  const editor = view === "source" || view === "live";
  return editor && vim ? `obsidian://${view}/${vim}` : `obsidian://${view}`;
}
var SendPolicy = class {
  constructor(keepaliveMs = KEEPALIVE_MS) {
    this.lastUrl = null;
    this.lastSent = null;
    this.keepaliveMs = keepaliveMs;
  }
  due(url, now) {
    if (url === null) return false;
    if (url !== this.lastUrl || this.lastSent === null) return true;
    return now - this.lastSent >= this.keepaliveMs;
  }
  sent(url, now) {
    this.lastUrl = url;
    this.lastSent = now;
  }
};
function payload(url, opts = {}) {
  const body = {
    app: APP,
    url,
    focused: opts.focused === void 0 ? true : !!opts.focused
  };
  if (typeof opts.pid === "number" && Number.isInteger(opts.pid) && opts.pid > 0) {
    body.pid = opts.pid;
  }
  if (typeof opts.inputAge === "number" && Number.isFinite(opts.inputAge)) {
    body.input_age = Math.round(Math.max(0, opts.inputAge) * 10) / 10;
  }
  if (opts.token) body.token = opts.token;
  return JSON.stringify(body);
}
function reportUrl(port) {
  return `http://127.0.0.1:${port}/report`;
}
var Sender = class {
  constructor(post, log = () => {
  }) {
    this.pending = null;
    this.busy = false;
    this.seen = /* @__PURE__ */ new Set();
    this.post = post;
    this.log = log;
  }
  submit(port, body) {
    this.pending = [reportUrl(port), body];
    return this.pump();
  }
  /** Resolves once nothing is pending or in flight (for tests and unload). */
  async pump() {
    if (this.busy) return;
    this.busy = true;
    try {
      while (this.pending) {
        const [url, body] = this.pending;
        this.pending = null;
        try {
          await this.post(url, body);
        } catch (e) {
          const msg = e instanceof Error ? e.message : String(e);
          if (!this.seen.has(msg)) {
            this.seen.add(msg);
            this.log(`PolyKybd Mode Reporter: report not delivered: ${msg}`);
          }
        }
      }
    } finally {
      this.busy = false;
    }
  }
};

// src/main.ts
var DEFAULTS = { enabled: true, port: DEFAULT_PORT, token: "" };
function editorView(view) {
  return view.editor?.cm ?? null;
}
function livePreview(view) {
  const ev = editorView(view);
  try {
    const v = ev?.state?.field?.(import_obsidian.editorLivePreviewField, false);
    if (typeof v === "boolean") return v;
  } catch {
  }
  const s = view.getState();
  return typeof s.source === "boolean" ? !s.source : null;
}
function vimState(view) {
  const cm = editorView(view)?.cm;
  const vim = cm?.state?.vim;
  if (!vim) return null;
  return {
    insertMode: vim.insertMode,
    visualMode: vim.visualMode,
    overwrite: cm.state.overwrite
  };
}
var PolyKybdModeReporter = class extends import_obsidian.Plugin {
  constructor() {
    super(...arguments);
    this.settings = { ...DEFAULTS };
    this.sender = new Sender(
      async (url, body) => {
        const r = await (0, import_obsidian.requestUrl)({
          url,
          method: "POST",
          contentType: "application/json",
          body,
          throw: false
        });
        if (r.status >= 400) throw new Error(`HTTP ${r.status}`);
      },
      (msg) => console.warn(msg)
    );
    this.policy = new SendPolicy();
    this.lastInput = null;
    this.reported = false;
  }
  async onload() {
    this.settings = { ...DEFAULTS, ...await this.loadData() };
    this.addSettingTab(new ReporterSettingTab(this.app, this));
    const input = () => {
      this.lastInput = Date.now();
    };
    const watch = (doc) => {
      this.registerDomEvent(doc, "keydown", input, true);
      this.registerDomEvent(doc, "mousedown", input, true);
      this.registerDomEvent(doc, "keyup", () => this.tick(), true);
    };
    watch(document);
    this.registerEvent(this.app.workspace.on("window-open", (w) => watch(w.doc)));
    this.registerEvent(this.app.workspace.on("active-leaf-change", () => this.tick()));
    this.registerEvent(this.app.workspace.on("layout-change", () => this.tick()));
    this.registerEvent(this.app.workspace.on("quit", () => this.withdraw()));
    this.registerInterval(window.setInterval(() => this.tick(), POLL_MS));
    this.app.workspace.onLayoutReady(() => this.tick());
  }
  onunload() {
    this.withdraw();
  }
  currentUrl() {
    const view = this.app.workspace.getActiveViewOfType(import_obsidian.View);
    if (view instanceof import_obsidian.MarkdownView) {
      const token = viewToken({
        viewType: view.getViewType(),
        mode: view.getMode(),
        livePreview: livePreview(view)
      });
      return contextUrl(token, vimToken(vimState(view)));
    }
    return contextUrl(viewToken({ viewType: view ? view.getViewType() : null }));
  }
  tick() {
    if (!this.settings.enabled) {
      this.withdraw();
      return;
    }
    try {
      const url = this.currentUrl();
      const now = Date.now();
      if (this.policy.due(url, now)) {
        const age = this.lastInput === null ? null : (now - this.lastInput) / 1e3;
        void this.sender.submit(this.settings.port, payload(url, {
          token: this.settings.token,
          pid: process.pid,
          inputAge: age
        }));
        this.policy.sent(url, now);
        this.reported = true;
      }
    } catch (e) {
      console.warn("PolyKybd Mode Reporter:", e);
    }
  }
  /** Tell the host this instance stopped reporting, once, so the keyboard
   *  leaves the last mode's set instead of keeping it for up to 8 s. */
  withdraw() {
    if (!this.reported) return;
    void this.sender.submit(this.settings.port, payload(null, {
      token: this.settings.token,
      pid: process.pid,
      focused: false
    }));
    this.reported = false;
    this.policy = new SendPolicy();
  }
  async saveSettings() {
    await this.saveData(this.settings);
  }
};
var ReporterSettingTab = class extends import_obsidian.PluginSettingTab {
  constructor(app, plugin) {
    super(app, plugin);
    this.plugin = plugin;
  }
  display() {
    const { containerEl } = this;
    containerEl.empty();
    new import_obsidian.Setting(containerEl).setName("Report the view and mode").setDesc("Send the kind of view and the Vim mode to PolyKybdHost on this computer (127.0.0.1). No note names or content.").addToggle((t) => t.setValue(this.plugin.settings.enabled).onChange(async (v) => {
      this.plugin.settings.enabled = v;
      await this.plugin.saveSettings();
      this.plugin.tick();
    }));
    new import_obsidian.Setting(containerEl).setName("Port").setDesc("PolyKybdHost's browser_report_port (default 50164).").addText((t) => t.setValue(String(this.plugin.settings.port)).onChange(async (v) => {
      const n = Number(v);
      if (Number.isInteger(n) && n > 0 && n < 65536) {
        this.plugin.withdraw();
        this.plugin.settings.port = n;
        await this.plugin.saveSettings();
      }
    }));
    new import_obsidian.Setting(containerEl).setName("Token").setDesc("Only if PolyKybdHost has browser_report_token set: the same value.").addText((t) => {
      t.inputEl.type = "password";
      t.setValue(this.plugin.settings.token).onChange(async (v) => {
        this.plugin.settings.token = v;
        await this.plugin.saveSettings();
      });
    });
  }
};
