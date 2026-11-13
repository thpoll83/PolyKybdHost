// SPDX-License-Identifier: GPL-3.0-or-later
/*
 * PolyKybd Mode Reporter: Obsidian glue.
 *
 * Reports which kind of view is active (editor in Source mode or Live
 * Preview, Reading view, Canvas, Graph view, anything else) and, with Vim key
 * bindings on, the Vim mode, to the local PolyKybdHost, so the keycaps show
 * the shortcuts that apply. See README.md; the wire format is in core.ts.
 *
 * Public API used: Workspace.getActiveViewOfType(View), View.getViewType(),
 * MarkdownView.getMode(), editorLivePreviewField, the 'active-leaf-change',
 * 'layout-change', 'window-open' and 'quit' workspace events, requestUrl().
 * NOT public API: `editor.cm` (the CodeMirror 6 EditorView) and its `cm`
 * adapter's `state.vim` (CodeMirror-vim). Both are read defensively: when they
 * are missing the report has no Vim token and the plugin keeps working.
 */
import {
    App, MarkdownView, Plugin, PluginSettingTab, Setting, View,
    editorLivePreviewField, requestUrl,
} from "obsidian";

import {
    DEFAULT_PORT, POLL_MS, SendPolicy, Sender, VimState, contextUrl, payload,
    viewToken, vimToken,
} from "./core";

interface Settings {
    enabled: boolean;
    port: number;
    token: string;
}

const DEFAULTS: Settings = { enabled: true, port: DEFAULT_PORT, token: "" };

/* eslint-disable @typescript-eslint/no-explicit-any */
function editorView(view: MarkdownView): any {
    return (view.editor as any)?.cm ?? null;
}

function livePreview(view: MarkdownView): boolean | null {
    const ev = editorView(view);
    try {
        const v = ev?.state?.field?.(editorLivePreviewField, false);
        if (typeof v === "boolean") return v;
    } catch {
        // fall through to the view state
    }
    const s = view.getState() as Record<string, unknown>;
    return typeof s.source === "boolean" ? !s.source : null;
}

function vimState(view: MarkdownView): VimState | null {
    const cm = editorView(view)?.cm;          // CodeMirror-vim's adapter
    const vim = cm?.state?.vim;
    if (!vim) return null;
    return { insertMode: vim.insertMode, visualMode: vim.visualMode,
             overwrite: cm.state.overwrite };
}
/* eslint-enable @typescript-eslint/no-explicit-any */

export default class PolyKybdModeReporter extends Plugin {
    settings: Settings = { ...DEFAULTS };
    private sender = new Sender(
        async (url, body) => {
            const r = await requestUrl({ url, method: "POST", contentType: "application/json",
                                         body, throw: false });
            if (r.status >= 400) throw new Error(`HTTP ${r.status}`);
        },
        (msg) => console.warn(msg));
    private policy = new SendPolicy();
    private lastInput: number | null = null;
    private reported = false;

    async onload(): Promise<void> {
        this.settings = { ...DEFAULTS, ...(await this.loadData()) };
        this.addSettingTab(new ReporterSettingTab(this.app, this));

        const input = () => { this.lastInput = Date.now(); };
        const watch = (doc: Document) => {
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

    onunload(): void {
        this.withdraw();
    }

    currentUrl(): string {
        const view = this.app.workspace.getActiveViewOfType(View);
        if (view instanceof MarkdownView) {
            const token = viewToken({ viewType: view.getViewType(), mode: view.getMode(),
                                      livePreview: livePreview(view) });
            return contextUrl(token, vimToken(vimState(view)));
        }
        return contextUrl(viewToken({ viewType: view ? view.getViewType() : null }));
    }

    tick(): void {
        if (!this.settings.enabled) {
            this.withdraw();
            return;
        }
        try {
            const url = this.currentUrl();
            const now = Date.now();
            if (this.policy.due(url, now)) {
                const age = this.lastInput === null ? null : (now - this.lastInput) / 1000;
                void this.sender.submit(this.settings.port, payload(url, {
                    token: this.settings.token, pid: process.pid, inputAge: age }));
                this.policy.sent(url, now);
                this.reported = true;
            }
        } catch (e) {
            console.warn("PolyKybd Mode Reporter:", e);
        }
    }

    /** Tell the host this instance stopped reporting, once, so the keyboard
     *  leaves the last mode's set instead of keeping it for up to 8 s. */
    withdraw(): void {
        if (!this.reported) return;
        void this.sender.submit(this.settings.port, payload(null, {
            token: this.settings.token, pid: process.pid, focused: false }));
        this.reported = false;
        this.policy = new SendPolicy();
    }

    async saveSettings(): Promise<void> {
        await this.saveData(this.settings);
    }
}

class ReporterSettingTab extends PluginSettingTab {
    plugin: PolyKybdModeReporter;

    constructor(app: App, plugin: PolyKybdModeReporter) {
        super(app, plugin);
        this.plugin = plugin;
    }

    display(): void {
        const { containerEl } = this;
        containerEl.empty();
        new Setting(containerEl)
            .setName("Report the view and mode")
            .setDesc("Send the kind of view and the Vim mode to PolyKybdHost on this "
                     + "computer (127.0.0.1). No note names or content.")
            .addToggle((t) => t.setValue(this.plugin.settings.enabled).onChange(async (v) => {
                this.plugin.settings.enabled = v;
                await this.plugin.saveSettings();
                this.plugin.tick();
            }));
        new Setting(containerEl)
            .setName("Port")
            .setDesc("PolyKybdHost's browser_report_port (default 50164).")
            .addText((t) => t.setValue(String(this.plugin.settings.port)).onChange(async (v) => {
                const n = Number(v);
                if (Number.isInteger(n) && n > 0 && n < 65536) {
                    this.plugin.withdraw();
                    this.plugin.settings.port = n;
                    await this.plugin.saveSettings();
                }
            }));
        new Setting(containerEl)
            .setName("Token")
            .setDesc("Only if PolyKybdHost has browser_report_token set: the same value.")
            .addText((t) => {
                t.inputEl.type = "password";
                t.setValue(this.plugin.settings.token).onChange(async (v) => {
                    this.plugin.settings.token = v;
                    await this.plugin.saveSettings();
                });
            });
    }
}
