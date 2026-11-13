// SPDX-License-Identifier: GPL-3.0-or-later
/**
 * PolyKybd Context Reporter for JupyterLab 4 (and Jupyter Notebook 7).
 *
 * Tells PolyKybdHost which activity is active (notebook, file editor, console,
 * terminal) and, in a notebook, whether it is in command or edit mode. The
 * page posts to its own Jupyter server (`<base>/polykybd/report`), and the
 * server extension in `polykybd_jupyterlab/` forwards it to the loopback
 * receiver of PolyKybdHost. The page cannot post to that receiver itself: it
 * grants no CORS for /report, on purpose.
 */
import {
  ILabShell,
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import { IConsoleTracker } from '@jupyterlab/console';
import { IEditorTracker } from '@jupyterlab/fileeditor';
import { INotebookTracker, NotebookPanel } from '@jupyterlab/notebook';
import { ServerConnection } from '@jupyterlab/services';
import { ISettingRegistry } from '@jupyterlab/settingregistry';
import { ITerminalTracker } from '@jupyterlab/terminal';
import { Widget } from '@lumino/widgets';

import { ActivityKind, contextUrl, KEEPALIVE_MS, reportBody, SendPolicy } from './context';

const PLUGIN_ID = 'polykybd-jupyterlab-context-reporter:plugin';

interface ITracker {
  has(widget: Widget): boolean;
}

const plugin: JupyterFrontEndPlugin<void> = {
  id: PLUGIN_ID,
  description: 'Reports the JupyterLab activity and notebook mode to PolyKybdHost.',
  autoStart: true,
  optional: [
    ILabShell,
    INotebookTracker,
    IEditorTracker,
    IConsoleTracker,
    ITerminalTracker,
    ISettingRegistry
  ],
  activate: (
    app: JupyterFrontEnd,
    labShell: ILabShell | null,
    notebooks: INotebookTracker | null,
    editors: IEditorTracker | null,
    consoles: IConsoleTracker | null,
    terminals: ITerminalTracker | null,
    settingRegistry: ISettingRegistry | null
  ) => {
    const serverSettings = ServerConnection.makeSettings();
    const endpoint = serverSettings.baseUrl.replace(/\/?$/, '/') + 'polykybd/report';
    const policy = new SendPolicy();
    let enabled = true;
    let lastInput = Date.now();

    const has = (tracker: ITracker | null, w: Widget): boolean =>
      tracker !== null && tracker.has(w);

    const classify = (): { kind: ActivityKind; mode?: string } => {
      // ILabShell.activeWidget is the focused widget in any area, or null
      // (then the main area's current widget answers). Notebook 7 has only
      // currentWidget.
      const w = (labShell ? labShell.activeWidget : null) ?? app.shell.currentWidget;
      if (!w) {
        return { kind: 'other' };
      }
      if (has(notebooks, w)) {
        return { kind: 'notebook', mode: (w as NotebookPanel).content.mode };
      }
      if (has(editors, w)) {
        return { kind: 'editor' };
      }
      if (has(consoles, w)) {
        return { kind: 'console' };
      }
      if (has(terminals, w)) {
        return { kind: 'terminal' };
      }
      return { kind: 'other' };
    };

    const pageFocused = (): boolean =>
      document.visibilityState === 'visible' && document.hasFocus();

    const post = (url: string | null, focused: boolean, keepalive = false): void => {
      const init: RequestInit = {
        method: 'POST',
        body: reportBody(url, focused, (Date.now() - lastInput) / 1000),
        keepalive
      };
      // Errors stay silent: PolyKybdHost may not run, and the next change or
      // keep-alive tries again.
      ServerConnection.makeRequest(endpoint, init, serverSettings).catch(() => undefined);
    };

    const update = (): void => {
      if (!enabled) {
        return;
      }
      const { kind, mode } = classify();
      const url = contextUrl(kind, mode);
      const focused = pageFocused();
      const now = Date.now();
      if (policy.due(url, focused, now)) {
        policy.sent(url, focused, now);
        post(url, focused);
      }
    };

    const withdraw = (keepalive: boolean): void => {
      policy.sent(null, false, Date.now());
      post(null, false, keepalive);
    };

    // Mode changes: Notebook.stateChanged emits { name: 'mode' } (4.x).
    const watchPanel = (panel: NotebookPanel): void => {
      panel.content.stateChanged.connect((_, args) => {
        if (args.name === 'mode') {
          update();
        }
      });
    };
    if (notebooks) {
      notebooks.forEach(watchPanel);
      notebooks.widgetAdded.connect((_, panel) => watchPanel(panel));
    }
    // Activity changes.
    if (labShell) {
      labShell.activeChanged.connect(update);
      labShell.currentChanged.connect(update);
    } else if (app.shell.currentChanged) {
      app.shell.currentChanged.connect(update);
    }
    // Page focus.
    window.addEventListener('focus', update);
    window.addEventListener('blur', update);
    document.addEventListener('visibilitychange', update);
    window.addEventListener('pagehide', () => withdraw(true));
    // Input time, for the host's choice between several Jupyter servers.
    const noteInput = (): void => {
      lastInput = Date.now();
    };
    document.addEventListener('keydown', noteInput, true);
    document.addEventListener('pointerdown', noteInput, true);
    // Keep-alive, and a catch-all for any change no signal reported.
    window.setInterval(update, KEEPALIVE_MS / 2);

    if (settingRegistry) {
      settingRegistry
        .load(PLUGIN_ID)
        .then(settings => {
          const apply = (): void => {
            const now = settings.get('enabled').composite !== false;
            if (enabled && !now) {
              withdraw(false);
            }
            enabled = now;
            update();
          };
          settings.changed.connect(apply);
          apply();
        })
        .catch(() => undefined);
    }
    app.restored.then(update).catch(() => undefined);
  }
};

export default plugin;
