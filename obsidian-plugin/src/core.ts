// SPDX-License-Identifier: GPL-3.0-or-later
/*
 * Obsidian-free half of the PolyKybd Mode Reporter (unit-tested without the app).
 *
 * Everything here runs without Obsidian: building the pseudo-URL from plain
 * values, deciding when to send, the payload, and the sender queue. main.ts is
 * the thin glue that reads the values from Obsidian.
 *
 * What is sent, and nothing else:
 *
 *     POST http://127.0.0.1:<port>/report      Content-Type: application/json
 *     {"app": "obsidian", "url": "obsidian://live/vim-normal", "focused": true,
 *      "pid": 4242, "input_age": 0.4, "token": "<only if one is configured>"}
 *
 * The URL names the kind of view and, in the editor with Vim key bindings on,
 * the Vim mode. No file name, note text, vault name or window title.
 *
 * Only erasable TypeScript syntax is used (no enums, no parameter
 * properties), so Node runs this file directly in the tests.
 */

export const APP = "obsidian";
/** PolyKybdHost `browser_report_port`. */
export const DEFAULT_PORT = 50164;
/** The host drops a report older than 8 s (browser_url.py DEFAULT_MAX_AGE_S),
 *  so the context is re-sent well inside that window: two lost keep-alives
 *  still leave the report fresh. */
export const KEEPALIVE_MS = 3000;
/** How often the plugin looks for a change that has no event (the Vim mode). */
export const POLL_MS = 500;

/** View tokens. `source` and `live` are the editor (Source mode, Live
 *  Preview), `reading` is Reading view, `other` every view without its own
 *  keys (PDF, image, settings, the sidebars). */
export const VIEW_TOKENS = ["source", "live", "reading", "canvas", "graph", "other"] as const;
export type ViewToken = typeof VIEW_TOKENS[number];
export const VIM_TOKENS = ["vim-normal", "vim-insert", "vim-visual", "vim-replace"] as const;
export type VimToken = typeof VIM_TOKENS[number];

export interface ViewInfo {
    /** `View.getViewType()` of the active view, or null when there is none. */
    viewType: string | null;
    /** `MarkdownView.getMode()`: "source" (editor) or "preview" (Reading view). */
    mode?: string | null;
    /** Live Preview on (`editorLivePreviewField`), for a Markdown editor. */
    livePreview?: boolean | null;
}

/** The view token for the active view. */
export function viewToken(info: ViewInfo): ViewToken {
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

/** The fields of CodeMirror-vim's state the plugin reads
 *  (`cm.state.vim.insertMode` / `.visualMode`, and `cm.state.overwrite` for
 *  Replace mode). */
export interface VimState {
    insertMode?: unknown;
    visualMode?: unknown;
    overwrite?: unknown;
}

/** The Vim token, or null when Vim key bindings are off (no state). */
export function vimToken(state: VimState | null | undefined): VimToken | null {
    if (!state) return null;
    if (state.insertMode) return state.overwrite ? "vim-replace" : "vim-insert";
    if (state.visualMode) return "vim-visual";
    return "vim-normal";
}

/** `obsidian://<view>[/<vim>]`. The Vim mode is added only in the editor. */
export function contextUrl(view: ViewToken, vim: VimToken | null = null): string {
    const editor = view === "source" || view === "live";
    return editor && vim ? `obsidian://${view}/${vim}` : `obsidian://${view}`;
}

/** Send on change, plus a keep-alive while nothing changes. */
export class SendPolicy {
    keepaliveMs: number;
    lastUrl: string | null = null;
    lastSent: number | null = null;

    constructor(keepaliveMs: number = KEEPALIVE_MS) {
        this.keepaliveMs = keepaliveMs;
    }

    due(url: string | null, now: number): boolean {
        if (url === null) return false;
        if (url !== this.lastUrl || this.lastSent === null) return true;
        return now - this.lastSent >= this.keepaliveMs;
    }

    sent(url: string, now: number): void {
        this.lastUrl = url;
        this.lastSent = now;
    }
}

export interface PayloadOptions {
    token?: string;
    pid?: number | null;
    /** Seconds since this window last saw a key or mouse event. */
    inputAge?: number | null;
    focused?: boolean;
}

/** One report body. `focused: false` with no URL withdraws this instance's
 *  context, so the host stops showing its mode at once. */
export function payload(url: string | null, opts: PayloadOptions = {}): string {
    const body: Record<string, unknown> = {
        app: APP, url, focused: opts.focused === undefined ? true : !!opts.focused,
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

export function reportUrl(port: number): string {
    return `http://127.0.0.1:${port}/report`;
}

/** A POST: resolves when done; any rejection is caught by the Sender. */
export type PostFn = (url: string, body: string) => Promise<unknown>;

/** Delivers the LATEST report; an older one still waiting is dropped. At most
 *  one request is in flight, so a host that is down or slow cannot pile up
 *  requests. Failures are reported once per distinct message to `log`. */
export class Sender {
    private post: PostFn;
    private log: (msg: string) => void;
    private pending: [string, string] | null = null;
    private busy = false;
    private seen = new Set<string>();

    constructor(post: PostFn, log: (msg: string) => void = () => {}) {
        this.post = post;
        this.log = log;
    }

    submit(port: number, body: string): Promise<void> {
        this.pending = [reportUrl(port), body];
        return this.pump();
    }

    /** Resolves once nothing is pending or in flight (for tests and unload). */
    async pump(): Promise<void> {
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
}
