# PolyKybd Context Reporter (IDA plugin)

Tells PolyKybdHost which kind of IDA **view** has the focus, so the keycaps show
the shortcuts of that view: N is "Rename variable" and Tab is "Jump to
disassembly" in the pseudocode window, C/D/A/U make code and data in the
disassembly view, and a list or the local types window shows only the keys
that act from any window. Without the plugin the keyboard still shows IDA's
overlay (`ida_template`), with the keys of every view on one set.

IDA Pro, IDA Home and IDA Free, IDA 8.5 and later (plugin folder install); the
plugin file also loads in older IDA 7.x and 8.x when copied by hand (below).
**Not tested on a real IDA.** The code was checked against the IDAPython
reference only, and its IDA-free half is tested by the host's test suite with
stand-ins for the IDA constants (`tests/ida_plugin/reporter_test.py`).

## What it sends, and where

To **loopback only** (`http://127.0.0.1:<port>/report`), when the view changes
and as a keep-alive every 3 s while nothing changes:

```json
{ "app": "ida", "url": "ida://pseudocode", "focused": true,
  "pid": 4242, "input_age": 0.4 }
```

`url` is `ida://<view>[/<render>]`, built from the widget **type** only:

| URL | widget (`get_widget_type`) | overlay |
|---|---|---|
| `ida://disasm/text`, `ida://disasm/graph`, `ida://disasm/proximity` | `BWN_DISASM`, with `get_view_renderer_type` | `ida_disasm_template` |
| `ida://pseudocode` | `BWN_PSEUDOCODE` | `ida_pseudocode_template` |
| `ida://hex` | `BWN_HEXVIEW` | `ida_disasm_template` |
| `ida://types` | `BWN_TICSR` / `BWN_TILVIEW` / `BWN_LOCTYPS` (IDA 9), `BWN_STRUCTS` / `BWN_ENUMS` (IDA 8) | `ida_global_template` |
| `ida://list` | the choosers (`BWN_CHOOSER`, `BWN_FUNCS`, `BWN_NAMES`, `BWN_STRINGS`, ...) | `ida_global_template` |
| `ida://output`, `ida://cli`, `ida://other` | `BWN_OUTPUT`, `BWN_CLI`, any other widget | `ida_global_template` |

- `pid` is IDA's process id and `input_age` the seconds since this IDA last saw
  a key, a click, a cursor move or a widget change. With several IDAs open, the
  host follows the one with the most recent input.
- **Nothing else.** No address, function or file name, database content or
  window title. `token` is added only if you set one (below).
- When the database closes or IDA exits, the plugin sends one last report with
  `"url": null, "focused": false`, so the keyboard leaves that view's overlay at
  once.

The plugin cannot tell whether IDA has OS focus, so its reports always say
`focused: true`. The host uses a report only while **IDA is the focused
application** and while it is younger than 8 s. The HTTP request runs on a
background thread; if PolyKybdHost is not running, the send fails and IDA does
not wait on it.

### IDA calls used

From the IDAPython reference (<https://python.docs.hex-rays.com/namespaceida__kernwin.html>,
<https://python.docs.hex-rays.com/classida__kernwin_1_1_u_i___hooks.html>,
<https://python.docs.hex-rays.com/classida__kernwin_1_1_view___hooks.html>,
<https://python.docs.hex-rays.com/namespaceida__idaapi.html>), read 2026-11-13:

- `ida_kernwin.get_current_widget()`, `get_widget_type(widget)` and
  `get_view_renderer_type(widget)` (`TCCRT_FLAT`, `TCCRT_GRAPH`,
  `TCCRT_PROXIMITY`), polled by `ida_kernwin.register_timer(250, callback)`.
  Polling is needed because Space (text/graph) changes no widget, so
  `UI_Hooks.current_widget_changed(widget, prev_widget)` alone does not see it.
- `UI_Hooks.current_widget_changed`, `UI_Hooks.screen_ea_changed`,
  `View_Hooks.view_keydown`, `view_click` and `view_curpos` only record the time
  of the last input. `UI_Hooks.database_closed` sends the last report.
- The `BWN_*` constants are read with `getattr`: IDA 9 has no `BWN_STRUCTS` and
  `BWN_ENUMS` (Local types replaced them) and adds `BWN_TICSR`.
- `ida_idaapi.plugin_t` with `PLUGIN_MULTI | PLUGIN_HIDE`, whose `init()`
  returns a `plugmod_t` (the IDA 9 plugin style,
  <https://docs.hex-rays.com/developer/idapython/how-tos/how-to-create-a-plugin.md>).
  The plugin has no menu item and starts with each database.
- `ida_diskio.get_user_idadir()` for the optional settings file.

## Install

The tray app copies it: *Updates → Set up the terminal and editors…*, tick
**IDA**, or `polyctl editor-plugins install --editor ida`. It writes
`polykybd_ida.py` and `ida-plugin.json` to `<IDAUSR>/plugins/polykybd/`:

| OS | folder (`IDAUSR` unset) |
|---|---|
| Windows | `%APPDATA%\Hex-Rays\IDA Pro\plugins\polykybd` |
| Linux, macOS | `~/.idapro/plugins/polykybd` |

With `IDAUSR` set, the first folder it lists is used (Hex-Rays,
"Environment variables": <https://docs.hex-rays.com/core/disassembler/concepts/environment-variables.md>).
A folder with `ida-plugin.json` is loaded by IDA 8.5 and later. For an older
IDA, copy `polykybd_ida.py` alone into `<IDAUSR>/plugins/` by hand. Restart IDA.

The copy is refreshed when PolyKybdHost starts after an update, unless you
changed it by hand.

## Settings

Optional. The defaults match the host's defaults.

| setting | default | where |
|---|---|---|
| port | 50164 | `"port"` in `<IDAUSR>/polykybd.json`, or `POLYKYBD_REPORT_PORT` |
| token | empty | `"token"` in that file, or `POLYKYBD_REPORT_TOKEN`; only if PolyKybdHost has `browser_report_token` set |
| enabled | true | `"enabled": false` in that file, or `POLYKYBD_REPORT_DISABLED=1` |

```json
{ "port": 50164, "token": "" }
```

## Which overlays

`polyhost/res/overlay_sources/ida/`: `bindings.yaml` is the fallback set and
the source of the three view sets that `gen_views.py` writes. `SOURCES.md`
lists the shortcut references.

## Tested

- Tested: the URL, payload, settings, send policy and sender thread (host
  suite, without IDA); the host routing of every URL on Windows, Linux and
  macOS; the installer's copy, refresh and removal in a temporary home.
- Not tested: loading in a real IDA (any version or OS), the hooks, the timer,
  the folder install in IDA 8.5+, the hand install in older IDA, and the
  process names IDA reports to the host.
