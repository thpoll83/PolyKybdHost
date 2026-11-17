# PolyKybd Context Reporter (JupyterLab extension)

Tells PolyKybdHost which activity is active in JupyterLab and, in a notebook,
whether it is in **command mode** or **edit mode**. The keycaps then show the
keys that apply: the single-letter cell keys (A, B, X, C, V, M, Y, …) only in
command mode, the code editor keys (toggle comment, delete line) only while
you type in a cell, file editor or console. Without the extension the keyboard
still shows the Jupyter overlay, with all keys of all modes together.

JupyterLab 4 (tested with 4.5.11) and Jupyter Notebook 7. JupyterLab 3 is not
supported.

## How it works

```
JupyterLab page ──POST <base_url>/polykybd/report──▶ Jupyter server
   (labextension)        (same origin, Jupyter auth)    (server extension)
                                                            │
                                  POST http://127.0.0.1:50164/report
                                                            ▼
                                                      PolyKybdHost
```

The page does not post to PolyKybdHost itself. PolyKybdHost's receiver gives
no CORS permission for `/report` and requires `application/json`, so that no
web page can send it a false report. The page therefore posts to its own
Jupyter server, which is allowed and uses Jupyter's normal authentication
(token and XSRF). The server extension checks the report and forwards it to
the loopback receiver, as the Blender add-on does.

So **the Jupyter server must run on the same computer as PolyKybdHost**. This
is the case for `jupyter lab` started on your computer and for JupyterLab
Desktop (it starts a local server). It is not the case for a JupyterHub or any
other remote server: the server would post to its own loopback address, where
no PolyKybdHost runs. There the keyboard shows the Jupyter overlay without
modes, as before.

It works in a browser tab and in JupyterLab Desktop:

- **Browser**: the focused application is the browser. While the browser is
  focused and a Jupyter page reports that it has focus, PolyKybdHost uses that
  report instead of the tab's address. The browser extension is not needed for
  this.
- **JupyterLab Desktop**: the focused application is JupyterLab Desktop
  (`jupyterlab`, `jupyterlab-desktop` or `JupyterLab`; these names were not
  checked on an install), which is on the host's list of context reporters.

## What it sends

From the page to its Jupyter server, on every change of activity, mode or
page focus, and every 3 s while the page has focus:

```json
{ "url": "jupyter://notebook/edit", "focused": true, "input_age": 0.4 }
```

From the Jupyter server to `http://127.0.0.1:<port>/report`:

```json
{ "app": "jupyter", "url": "jupyter://notebook/edit", "focused": true,
  "pid": 4242, "input_age": 0.4 }
```

| `url` | when |
|---|---|
| `jupyter://notebook/command` | a notebook is active, in command mode |
| `jupyter://notebook/edit` | a notebook is active, a cell is being edited |
| `jupyter://editor` | a file editor is active |
| `jupyter://console` | a code console is active |
| `jupyter://terminal` | a terminal is active |
| `jupyter://other` | anything else (launcher, file browser, settings) |

- `pid` is the Jupyter server's process id, and `input_age` the seconds since
  the page last saw a key or pointer event. With several Jupyter servers, the
  host follows the one with the most recent input.
- **Nothing else.** No file names, paths, cell content or window titles. The
  server extension accepts only the six URLs above and sends nothing for any
  other value.
- `token` is added only if one is configured (see below).
- A page that loses focus (another tab, another application) sends one report
  with `"url": null, "focused": false` and then nothing until it gets focus
  again. All tabs of one server share one report on the host, so a background
  tab must not repeat its report. Closing the tab and turning *Report context*
  off send the same report.

## Install

Into the Python environment that runs the Jupyter server:

```bash
pip install /path/to/PolyKybdHost/jupyterlab-extension
```

The prebuilt labextension is included (`polykybd_jupyterlab/labextension/`),
so this needs no Node.js. Restart the Jupyter server, then reload the page.
Check with `jupyter labextension list` and `jupyter server extension list`.

For JupyterLab Desktop, install into its bundled environment (*Settings →
Server → Python environment* shows the path), for example
`<env>/bin/python -m pip install /path/to/PolyKybdHost/jupyterlab-extension`.

Remove it with `pip uninstall polykybd_jupyterlab`.

## Settings

In JupyterLab: *Settings → Settings Editor → PolyKybd Context Reporter*:

| setting | default | |
|---|---|---|
| Report context | on | turn reporting off without uninstalling |

On the Jupyter server (environment variables, or `jupyter_server_config.py`):

| setting | default | |
|---|---|---|
| `POLYKYBD_REPORT_PORT` / `c.PolyKybdReporter.port` | 50164 | PolyKybdHost's `browser_report_port` |
| `POLYKYBD_REPORT_TOKEN` / `c.PolyKybdReporter.token` | empty | only if PolyKybdHost has `browser_report_token` set: the same value |

The environment variables take priority. On the host the feature is
`browser_url_detection` / `browser_report_local_enabled` (both on by default).

## API used

All from JupyterLab 4.5.11, read from the package type declarations and the
API reference
(<https://jupyterlab.readthedocs.io/en/latest/api/classes/notebook.Notebook-1.html>):

- `Notebook.mode` (`NotebookMode = 'command' | 'edit'`) and
  `Notebook.stateChanged`, which emits `{ name: 'mode', oldValue, newValue }`
  on every mode change.
- `INotebookTracker`, `IEditorTracker`, `IConsoleTracker`, `ITerminalTracker`
  (`.has(widget)`) to name the active activity.
- `ILabShell.activeWidget` with `activeChanged` and `currentChanged`. In a
  shell without `ILabShell` (Notebook 7), `JupyterFrontEnd.IShell.currentWidget`
  and its optional `currentChanged`.
- `document.hasFocus()` and `document.visibilityState` for page focus.
- `ServerConnection.makeRequest` for the post to the server extension.
- Server side: `jupyter_server` extension points
  (`_jupyter_server_extension_points`, `_load_jupyter_server_extension`) and an
  authenticated `APIHandler`
  (<https://jupyter-server.readthedocs.io/en/latest/developers/extensions.html>).

Every signal is backed up by a check every 1.5 s, so a change that no signal
reports is sent within that time.

## Build from source

Only needed after a change to `src/`:

```bash
pip install "jupyterlab>=4,<5"
npm install
npm run build        # writes polykybd_jupyterlab/labextension/
npm test             # the pure functions in src/context.ts (node's test runner)
```

The Python half (`polykybd_jupyterlab/report.py`) is tested by the host suite:
`tests/jupyterlab_extension/report_test.py`.

## What was tested

- Built here with JupyterLab 4.5.11 and `@jupyterlab/builder` 4.5.11, installed
  with `pip install .` (no Node.js used by the install), and run in JupyterLab
  4.5.11 on Linux in headless Chromium, with a stand-in receiver on the report
  port in place of PolyKybdHost. Seen at the receiver: `jupyter://other` at
  start, `jupyter://notebook/command` for a new notebook,
  `jupyter://notebook/edit` after Enter, `jupyter://notebook/command` after
  Escape, then `jupyter://console`, `jupyter://terminal` and
  `jupyter://editor`, the 3 s keep-alive, and `"url": null, "focused": false`
  when the page lost focus and when it was left.
- Headless Chromium does not move focus between windows, so the focus loss
  was simulated (`document.hasFocus()` replaced, then a real `blur` event).
- Moving focus to the file browser left the report on the main area's
  activity: `ILabShell.activeWidget` was null there.
- Not tested: JupyterLab Desktop, Jupyter Notebook 7, Windows and macOS,
  Firefox and Safari, a real PolyKybdHost and a real keyboard.

## Which overlays

The host's `jupyterlab` entry and the browser entries route the URL to one
overlay per mode: `polyhost/res/overlay_sources/jupyter/` (`gen_specs.py`,
`SOURCES.md`).
