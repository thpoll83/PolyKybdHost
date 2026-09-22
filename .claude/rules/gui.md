---
paths:
  - "polyhost/gui/host.py"
  - "polyhost/gui/cmd_menu.py"
  - "polyhost/forwarder.py"
  - "polyhost/host.py"
---
# Tray GUI and the forwarder

Full notes: `docs/tray-ui.md` · `docs/icons.md`.

- **Developer mode only ADDS a submenu — it must not rearrange anything.** Pinned by
  `tests/gui/host_client_test.py`.
- ⚠️ **`managed_connection_status` blanket-disables every top-level action first**, so a
  new group parent must be re-enabled explicitly there or its submenu is unreachable
  on a disconnect.
- **A new device-coupled GUI surface is expected to work in CLIENT MODE over RPC.**
  Client mode is the default under daemon-by-default; anything gated off it is
  unreachable out of the box.
- ⚠️ **The FORWARDER is a second tray app on a different machine** — its own
  `QApplication`, menu and log file. A user-facing feature added to `host.py` is absent
  there until wired separately, and its logs can never appear in a host-side bundle.
  Its menu mirrors the tray app's shape minus the device group, and its About is the
  shared `gui/about_dialog.build_about_dialog`; render both with
  `tools/render_tray_menu.py --mode all`. It wears the **F** mark
  (`IconStateManager(prefix="f")`), and its Settings is the `FORWARDER_SETTING_KEYS`
  allow-list — the full settings dict would show device rows that change nothing here.
- ⚠️ **A wrong or missing icon NAME fails silently** (`QIcon()` returns an empty icon);
  `tests/gui/icon_assets_test.py` is the only guard.
- **Network I/O belongs on a thread too** — a menu handler starts one and opens a
  progress dialog, never calls `requests` itself.
- ⚠️ **A self-re-arming `QTimer.singleShot` loop must guard INSIDE itself** — the
  re-arm sits *after* the raise, and PyQt5 turns an exception in a slot into
  `sys.excepthook` then `qFatal()`, so one bad tick ends the loop for the life of
  the process. `PolyHost.active_window_reporter` called `tick_window_tracking()`
  bare while the headless core (`core/poly_core.py`) had wrapped the **same call**
  in `try/except` all along — one function, two paths, one guard.
