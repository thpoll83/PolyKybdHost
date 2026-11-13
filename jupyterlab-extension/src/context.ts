// SPDX-License-Identifier: GPL-3.0-or-later
/**
 * The JupyterLab-free half of the reporter: the pseudo-URL and the decision
 * when to send. Tested with `npm test` (node's own test runner).
 *
 * The URL names only the kind of the active activity and, for a notebook, its
 * mode. No file name, path, cell content or window title is ever sent.
 */

/** The kinds of activity that change which keys apply. */
export type ActivityKind = 'notebook' | 'editor' | 'console' | 'terminal' | 'other';

/** `NotebookMode` of @jupyterlab/notebook 4.x. */
export type NotebookMode = 'command' | 'edit';

/** How often a focused page repeats its report. The host drops a report after
 * 8 s (browser_url.py DEFAULT_MAX_AGE_S), so two lost keep-alives still leave
 * it fresh. */
export const KEEPALIVE_MS = 3000;

/**
 * `jupyter://notebook/command`, `jupyter://notebook/edit`, `jupyter://editor`,
 * `jupyter://console`, `jupyter://terminal` or `jupyter://other`.
 */
export function contextUrl(kind: ActivityKind, mode?: string | null): string {
  if (kind === 'notebook') {
    return mode === 'edit' ? 'jupyter://notebook/edit' : 'jupyter://notebook/command';
  }
  if (kind === 'editor' || kind === 'console' || kind === 'terminal') {
    return `jupyter://${kind}`;
  }
  return 'jupyter://other';
}

/**
 * Send on a change of URL or focus, and repeat the report every
 * `KEEPALIVE_MS` while the page has focus. An unfocused page sends its
 * `focused: false` once and then nothing: all tabs of one Jupyter server share
 * one report slot on the host (keyed by the server's pid), so a background
 * tab's keep-alive would replace the focused tab's report.
 */
export class SendPolicy {
  private lastUrl: string | null = null;
  private lastFocused: boolean | null = null;
  private lastSent: number | null = null;

  constructor(private keepaliveMs: number = KEEPALIVE_MS) {}

  due(url: string | null, focused: boolean, now: number): boolean {
    if (this.lastSent === null) {
      // Nothing sent yet: an unfocused page has nothing to withdraw.
      return focused;
    }
    if (url !== this.lastUrl || focused !== this.lastFocused) {
      return true;
    }
    return focused && now - this.lastSent >= this.keepaliveMs;
  }

  sent(url: string | null, focused: boolean, now: number): void {
    this.lastUrl = url;
    this.lastFocused = focused;
    this.lastSent = now;
  }
}

/** The JSON body for the server extension's `POST <base>/polykybd/report`.
 * `inputAgeS` is the seconds since this page last saw a key or pointer event. */
export function reportBody(url: string | null, focused: boolean, inputAgeS: number): string {
  const age = Math.max(0, Math.round(inputAgeS * 10) / 10);
  return JSON.stringify({ url: focused ? url : null, focused, input_age: age });
}
