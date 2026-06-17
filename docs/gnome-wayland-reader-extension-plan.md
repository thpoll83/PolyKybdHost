# Plan: a minimal, read-only GNOME Shell extension for active-window reporting

**Status:** planned (not started). Captured for a follow-up session.
**Owner:** —
**Related code:** `polyhost/handler/gnome_wayland_reporter.py`, `polyhost/handler/active_window.py`, `polyhost/forwarder.py`

## Why

On GNOME/**Wayland**, Mutter does not expose the active window over X11/EWMH, so
`pywinctl` can't see native Wayland windows. Today `gnome_wayland_reporter.py`
works around this by calling the community **Window Calls** GNOME Shell extension
(interface `org.gnome.Shell.Extensions.Windows`). That extension is a general
**window-management** tool: alongside the read methods (`List`, `GetTitle`) it
exposes mutating ones — `Move`, `Resize`, `MoveResize`, `Maximize`, `Minimize`,
`Unmaximize`, `Activate`, `Close`, `MoveToWorkspace`, …

The problem isn't the extension's own privileges (any GNOME Shell extension runs
inside `gnome-shell` with full rights). **The boundary is what it exposes on the
session D-Bus.** Once Window Calls is installed and enabled, *any* process on the
user's session bus can move, resize, or close their windows. Asking a PolyKybd
user to install that just so the keyboard can read the focused app's name grants
a lot of latent authority to every app on the machine.

**Goal:** ship our own purpose-built extension that exposes **only** read
methods. No setters, ever. The exposed surface becomes "you can ask what's
focused, and nothing else."

## Decision

Use a **custom, PolyKybd-namespaced, read-only interface** (option 2 from the
design discussion) rather than mimicking `org.gnome.Shell.Extensions.Windows`:

- Avoids a name/path collision if the user also has the real Window Calls
  installed.
- Makes the "reads only" property obvious by construction — there is no setter
  to audit away.
- One D-Bus round-trip per poll (the base Window Calls drops the title from
  `List` "for privacy", forcing a second `GetTitle` call). We just return the
  title directly.

### D-Bus contract

| | |
|---|---|
| **Bus name (dest)** | `org.gnome.Shell` (the extension is hosted in gnome-shell) |
| **Object path** | `/org/polykybd/WindowReporter` |
| **Interface** | `org.polykybd.WindowReporter` |

**Methods (all read-only):**

- `GetFocusedWindow() -> String` — JSON object for the currently focused window,
  or the JSON literal `null` when nothing is focused:
  ```json
  {"id": 12345, "wm_class": "firefox", "wm_class_instance": "Navigator", "title": "Mozilla Firefox"}
  ```
- *(optional, future)* `GetWindows() -> String` — JSON array of all open windows
  with the same fields. Still read-only; add only if a caller needs more than the
  focused window. Not required for the host's current needs.

No `Move`/`Resize`/`Activate`/`Close`/anything mutating. The introspection XML
declares only the getter(s), so the bus literally cannot route a mutation call.

### Field semantics

Derived from the focused `MetaWindow`:
- `id` — `win.get_id()` (stable for the window's lifetime; the host treats it as
  an opaque handle for equality).
- `wm_class` — `win.get_wm_class()`; `wm_class_instance` — `win.get_wm_class_instance()`.
  The host's `getAppName()` uses `wm_class` (falls back to `wm_class_instance`).
- `title` — `win.get_title()` (may be empty; that's fine).

## The extension (separate repo)

Suggested repo: `polykybd-gnome-window-reporter` (or a subfolder if you prefer to
keep it in-tree; a separate repo keeps the GNOME-extension release/review cadence
independent of the host).

### Files

- **`metadata.json`**
  ```json
  {
    "uuid": "window-reporter@polykybd.org",
    "name": "PolyKybd Window Reporter",
    "description": "Read-only D-Bus endpoint reporting the focused window (id, wm_class, title) for PolyKybd on Wayland. Exposes no window-modifying methods.",
    "shell-version": ["45", "46", "47", "48"],
    "url": "https://github.com/thpoll83/polykybd-gnome-window-reporter"
  }
  ```
  - Keep `shell-version` current; GNOME 45+ uses ESM `extension.js`
    (`import`/`export default class`). If GNOME ≤ 44 must be supported, a second
    legacy entry point is needed — decide based on target distros.

- **`extension.js`** (GNOME 45+ ESM shape):
  ```js
  import Gio from 'gi://Gio';

  const IFACE = `
  <node>
    <interface name="org.polykybd.WindowReporter">
      <method name="GetFocusedWindow">
        <arg type="s" direction="out" name="json"/>
      </method>
    </interface>
  </node>`;

  export default class WindowReporterExtension {
    enable() {
      this._dbus = Gio.DBusExportedObject.wrapJSObject(IFACE, this);
      this._dbus.export(Gio.DBus.session, '/org/polykybd/WindowReporter');
    }
    disable() {
      this._dbus?.unexport();
      this._dbus = null;
    }
    GetFocusedWindow() {
      const w = global.display.get_focus_window();
      if (!w) return 'null';
      return JSON.stringify({
        id: w.get_id(),
        wm_class: w.get_wm_class() ?? '',
        wm_class_instance: w.get_wm_class_instance() ?? '',
        title: w.get_title() ?? '',
      });
    }
  }
  ```
  - `disable()` **must** unexport (extensions are disabled on lock screen; leaking
    the export would fail re-enable).
  - No timers, no signal connections, no other state — nothing to leak.

- **`README.md`** — install steps:
  ```
  git clone … ~/.local/share/gnome-shell/extensions/window-reporter@polykybd.org
  # log out/in (Wayland can't reload extensions live), or on X11: Alt+F2 → r
  gnome-extensions enable window-reporter@polykybd.org
  # verify:
  gdbus call --session --dest org.gnome.Shell \
    --object-path /org/polykybd/WindowReporter \
    --method org.polykybd.WindowReporter.GetFocusedWindow
  ```

- **`LICENSE`** — match the host's license (GPL-2.0-or-later is typical for GNOME
  extensions; confirm against PolyKybdHost's).

### Optional: publish to extensions.gnome.org

EGO review will scrutinise exactly the thing we're optimising for (no unsafe
calls, clean enable/disable), so it should pass easily and gives users a one-click
install. Manual-install-from-repo is fine for a first cut.

## Host-side changes (`gnome_wayland_reporter.py`)

Small, mechanical. Keep the existing fallback architecture intact (the
`_UNAVAILABLE` sentinel + pywinctl/XWayland fallback from PR #65 — see
`getActiveWindow()`); only the extension call changes.

1. **Constants:**
   ```python
   _DEST  = "org.gnome.Shell"
   _PATH  = "/org/polykybd/WindowReporter"
   _IFACE = "org.polykybd.WindowReporter"
   ```

2. **`_query_extension()`** — replace the `List` + find-focus + on-demand
   `GetTitle` dance with a single call:
   ```python
   res = _gdbus("GetFocusedWindow")          # one round-trip
   # ... same returncode / FileNotFoundError / TimeoutExpired handling -> _UNAVAILABLE
   payload = _unwrap_gdbus_string(res.stdout)
   if payload == "null":
       return None                            # extension up, nothing focused -> NO fallback
   win = json.loads(payload)
   return GnomeWin(win)
   ```
   - Preserve the **two distinct failure modes**: missing/unreachable extension
     → `_UNAVAILABLE` (caller falls back to pywinctl); extension up but `null`
     → `None` (a real "nothing focused", do **not** fall back). This distinction
     is the whole point of the sentinel and is already unit-tested.

3. **`GnomeWin`** — unchanged; it already reads `id` / `wm_class` /
   `wm_class_instance` / `title`.

4. **Docstring** — update the module header: we now target our own
   `org.polykybd.WindowReporter` (read-only), not Window Calls. Drop the
   "Window Calls / Window Calls Extended" naming and the "List omits title for
   privacy" note. Keep the ⚠️ untested-on-hardware caveat and the X11/XWayland
   fallback description.

5. **`_warn_once`** message — point users at the PolyKybd extension repo +
   `gnome-extensions enable …`, not "install Window Calls".

### Tests (`tests/handler/gnome_wayland_reporter_test.py`)

Rework the gdbus mocks from `List`-shaped output to `GetFocusedWindow`-shaped:
- focused window present → `GnomeWin` with id/appname/title (now from a single
  call; drop the second-call `GetTitle` test).
- `'null'` return → `getActiveWindow()` returns `None`, **no** pywinctl fallback.
- non-zero returncode / `FileNotFoundError` / timeout → `_UNAVAILABLE` →
  pywinctl fallback attempted; warns once.
- keep the `_unwrap_gdbus_string` escaping test and the `GnomeWin.__eq__` test.

The module stays Qt-free and import-guarded; only output parsing is unit-tested
(no GNOME-Wayland env in CI). Live D-Bus + exotic-title escaping validated on
real hardware.

## Edge cases / notes

- **gdbus escaping:** `GetFocusedWindow` returns a single string; reuse the
  existing `_unwrap_gdbus_string` (strips the `('…',)` tuple wrapper and undoes
  single-quote/backslash escaping). Titles with quotes/emoji are the risky bit —
  validate on hardware.
- **Wayland live-reload:** extensions can't be reloaded with `Alt+F2 r` under
  Wayland (that's X11-only); a logout/login is required after install. Document it.
- **Shell version churn:** GNOME's extension API breaks across majors; the
  `global.display.get_focus_window()` / `MetaWindow` getters used here are stable
  and present across 45–48, but re-test on each new GNOME before bumping
  `shell-version`.
- **No focused window** is normal (e.g. focus on the shell overview) — returning
  `null` → host `None` is correct and must not trigger the XWayland fallback.
- **Security posture to preserve:** never add a method that takes a window id and
  acts on it. If a future need arises (e.g. activate-on-keypress), that belongs
  behind a deliberate, separately-reviewed decision — not this reporter.

## Out of scope

- KDE/Plasma path (`kde_win_reporter.py`) — unaffected.
- The X11 path — unaffected; this module is only selected when
  `XDG_SESSION_TYPE == "wayland"` on a non-KDE desktop.
- Retiring the pywinctl/XWayland fallback — keep it; it's the graceful
  degradation when the extension isn't installed yet.
