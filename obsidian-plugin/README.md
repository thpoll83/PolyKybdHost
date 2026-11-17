# PolyKybd Mode Reporter (Obsidian plugin)

Tells PolyKybdHost which kind of view is active in Obsidian, and the Vim mode
when Vim key bindings are on, so the keycaps show the shortcuts that apply:
the editing keys in the editor, the Canvas keys on a canvas, Vim's Normal mode
keys while Vim is in Normal mode. Without the plugin the keyboard still shows
Obsidian's overlay, the editor set, in every view.

Desktop only (Windows, macOS, Linux). **Not tested in Obsidian yet**: see
[What was tested](#what-was-tested).

## What it sends, and where

To **loopback only** (`http://127.0.0.1:<port>/report`), on every change and as
a keep-alive every 3 s while nothing changes:

```json
{ "app": "obsidian", "url": "obsidian://live/vim-normal", "focused": true,
  "pid": 4242, "input_age": 0.4 }
```

- `url` is a pseudo-URL, `obsidian://<view>[/<vim mode>]`:

  | view token | when |
  |---|---|
  | `source` | a note in the editor, Source mode |
  | `live` | a note in the editor, Live Preview |
  | `reading` | a note in Reading view |
  | `canvas` | a canvas |
  | `graph` | Graph view or a local graph |
  | `other` | any other view (PDF, image, settings, a sidebar) or none |

  With Vim key bindings on, the editor tokens get the Vim mode:
  `vim-normal`, `vim-insert`, `vim-visual` or `vim-replace`
  (`obsidian://source/vim-insert`).
- `pid` is the process id of the Obsidian window's renderer, and `input_age`
  the seconds since that window last saw a key or mouse press. With several
  vault windows open, the host follows the one with the newest input.
- **Nothing else.** No note or vault name, no note text, no window title.
- `token` is added only if you set one (see below).

When you turn reporting off, disable the plugin or quit Obsidian, it sends one
last report with `"url": null, "focused": false`, so the keyboard leaves that
view's set at once. On quit the request may not finish before the app closes;
the host then drops the old report after 8 s.

The plugin always sends `"focused": true`. The host uses a report only while
**Obsidian is the focused application** and while it is fresher than 8 s, so
Obsidian in the background never changes another app's overlay.

## Obsidian API used

Checked against the `obsidian` npm package 1.14.4 (`obsidian.d.ts`, the
official API typings, <https://github.com/obsidianmd/obsidian-api>) on
2026-11-13:

| what | call |
|---|---|
| the active view | `app.workspace.getActiveViewOfType(View)`, `View.getViewType()` (`markdown`, `canvas`, `graph`, `localgraph`, ...) |
| Reading view or editor | `MarkdownView.getMode()`: `"preview"` or `"source"` |
| Live Preview or Source mode | the CodeMirror state field `editorLivePreviewField`, read from the editor's `EditorView`; if that fails, `MarkdownView.getState().source` |
| when to look | the `active-leaf-change`, `layout-change` and `window-open` workspace events, `keyup`, and a poll every 0.5 s |
| quitting | the `quit` workspace event, and `onunload()` |
| the HTTP request | `requestUrl()`. It is not subject to CORS; the host's `/report` grants no CORS, so `fetch()` from the page would fail |

**Not public API** (read defensively; when missing the report has no Vim token):

- `MarkdownView.editor.cm`: the CodeMirror 6 `EditorView` behind the editor.
- `EditorView.cm.state.vim` and `.state.overwrite`: the state of
  CodeMirror-vim (`@replit/codemirror-vim`), which runs Obsidian's
  *Vim key bindings* option. Fields used: `insertMode`, `visualMode`
  (`@replit/codemirror-vim-core` 0.1.0, `vim.js`, function `maybeInitVimState`), and
  `overwrite`, which the emulation's `toggleOverwrite` sets for Replace mode.
  Obsidian does not document which library or version it bundles; this comes
  from the library's source and from community plugins that read the same
  state. The plugin polls it every 0.5 s, so a mode change shows within half a
  second. CodeMirror-vim creates that state on first use
  (`maybeInitVimState`), so a note may report no Vim token until a key is
  pressed in it.

## Install

Obsidian loads a community plugin from `<vault>/.obsidian/plugins/<id>/`, per
vault. The plugin is not in Obsidian's community plugin directory, so install
it by hand:

```bash
./build.sh        # needs Node.js and npm -> dist/polykybd-mode-reporter/
```

1. Copy `dist/polykybd-mode-reporter/` (`main.js`, `manifest.json`) to
   `<vault>/.obsidian/plugins/polykybd-mode-reporter/`.
2. In Obsidian: *Settings → Community plugins*, turn off Restricted mode if it
   is on, then enable *PolyKybd Mode Reporter* (use the reload button if it is
   not in the list).

Repeat for every vault you use. PolyKybdHost's "Set up the terminal and
editors…" dialog does not install it: the vault folders and the per-vault
"enable" step belong to the user.

## Settings (plugin settings tab)

| setting | default | |
|---|---|---|
| Report the view and mode | on | switch the reporting off without uninstalling |
| Port | 50164 | PolyKybdHost's `browser_report_port` (the same receiver as the browser extension and the Blender add-on) |
| Token | empty | only if PolyKybdHost has `browser_report_token` set: the same value |

On the host side it is the `browser_url_detection` /
`browser_report_local_enabled` feature (both on by default).

## Which overlays

The host's `obsidian` mapping entry routes the pseudo-URL
(`polyhost/res/overlay-mapping.poly.yaml`). The sets are generated from
`polyhost/res/overlay_sources/obsidian/` (`gen_obsidian_modes.py`, see its
`SOURCES.md`):

| report | keycaps |
|---|---|
| `source`, `live`, `vim-insert`, `vim-replace`, no report | the editor set (unchanged) |
| `.../vim-normal`, `.../vim-visual` | the editor set, with Vim's Normal / Visual keys drawn over it |
| `reading` | the app commands, Find, the view toggle, Copy, Select all |
| `canvas` | the app commands and the Canvas keys |
| `graph` | the app commands and the Graph view keys |
| `other` | the app commands only |

## What was tested

- `test/core.test.mjs` (Node's test runner; `node --test test/core.test.mjs`,
  Node 22.18+): the URL, the payload, the send policy and the sender queue.
  The host suite runs it (`tests/obsidian_plugin/plugin_core_test.py`).
- `./build.sh`: `tsc --noEmit` (strict) against the 1.14.4 typings, then the
  esbuild bundle.
- The built `main.js` was loaded in Node with a stub of the `obsidian` module
  and posted to the real host receiver (`BrowserReportServer`): every view
  token, the Vim tokens, the keep-alive, the token and the withdrawal arrived
  as expected.

**Not tested**: the plugin inside Obsidian (any version, any OS), the private
Vim state in Obsidian's bundled copy, pop-out windows, and several vault
windows at once.
