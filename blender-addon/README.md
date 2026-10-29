# PolyKybd Context Reporter (Blender add-on)

Tells PolyKybdHost which **mode** Blender is in and which **editor** is under the
mouse, so the keycaps show the shortcuts that actually apply: Loop Cut on `Ctrl+R`
in Edit Mode, the brush keys in Sculpt Mode, the Node Editor's keys over a node
tree. Without it the keyboard still shows Blender's overlay, but only the keys
shared by every 3D View mode.

Blender 4.2+ (extension) and 3.6–4.1 (legacy add-on). Tested on Blender 5.2.2
(extension install, Linux); the legacy 3.6–4.1 path is untested.

## What it sends, and where

To **loopback only** (`http://127.0.0.1:<port>/report`), on every change of mode
or editor and as a keep-alive every 3 s while nothing changes:

```json
{ "app": "blender", "url": "blender://EDIT_MESH/VIEW_3D", "focused": true,
  "pid": 4242, "input_age": 0.4 }
```

- `url` is a pseudo-URL: `blender://<mode>/<editor>[/<editor variant>]`, built
  from `context.mode`, `area.type` and `area.ui_type` (e.g.
  `blender://EDIT_MESH/IMAGE_EDITOR/UV`, `blender://OBJECT/NODE_EDITOR/ShaderNodeTree`).
- `pid` is Blender's process id and `input_age` the seconds since this Blender
  last saw a mouse or key event. With several Blenders open, the host follows the
  one with the most recent input, so a background instance's keep-alive cannot
  replace the mode of the one you are working in.
- **Nothing else.** No file names, object or scene data, no window title. Keep it
  that way: the host routes on these tokens alone.
- `token` is added only if you set one (see below).

When you turn "Report context" off, or disable the add-on, it sends one last
report with `"url": null, "focused": false`, so the keyboard leaves that mode's
overlay at once instead of keeping it until the window changes.

The add-on cannot tell whether Blender has OS focus, so its other reports never
say "unfocused". They do not need to: the host uses a report only while **Blender is the focused
application**, and only while it is fresher than 8 s (hence the 3 s keep-alive). A
Blender in the background can never change the overlay of the app in front.

The HTTP request runs on a background thread. If PolyKybdHost is not running the
send fails silently and Blender's UI never waits on it.

### How it finds the editor

Blender sends a key to the editor **under the mouse**, and Python can read the
mouse position only from an event. So the add-on runs one tiny modal operator per
window that records the mouse position and passes every event straight through
(`PASS_THROUGH`); a timer then looks up the area at that position.

## Install

```bash
./build.sh          # -> dist/polykybd_context_reporter-<version>.zip
```

- **Blender 4.2+**: *Edit → Preferences → Get Extensions →* (drop-down, top right)
  *Install from Disk…* → pick the zip.
- **Blender 3.6–4.1**: *Edit → Preferences → Add-ons → Install…* → pick the zip,
  then tick *PolyKybd Context Reporter*.

## Settings (add-on preferences)

| setting | default | |
|---|---|---|
| Report context | on | switch the reporting off without uninstalling |
| Port | 50164 | PolyKybdHost's `browser_report_port` (the same receiver the browser extension uses) |
| Token | empty | only if PolyKybdHost has `browser_report_token` set: the same value |

On the host side it is the `browser_url_detection` / `browser_report_local_enabled`
feature (both default on). The receiver is shared with the
[browser extension](../browser-extension/README.md): loopback-only, JSON-only,
size-capped, optional token.

## Which overlays

The host's `blender` mapping entry routes the pseudo-URL to one overlay per
context, generated from Blender's own default keymap:
`polyhost/res/overlay_sources/blender/` (`gen_blender_bindings.py`, `COVERAGE.md`).
