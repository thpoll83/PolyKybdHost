"""GUI integration harness for the PolyHost tray app (H4a).

`PolyHost` is a QApplication that imports `pynput` (needs an X server) and can
only have one instance per process, so each construction runs in its own
subprocess. These tests are skipped unless a display is available — run the
suite under a virtual X server to exercise them:

    xvfb-run -a .venv/bin/python -m unittest tests.gui.host_client_test

They cover:
  * **default (in-process) mode** still constructs (regression guard for the
    client-mode branch added to `PolyHost.__init__`), and
  * **client mode** (`--connect`): the tray attaches to a running core over the
    control socket as a `RemoteCore`, renders a pushed `status_changed`, and
    `quit_app()` leaves the daemon serving.

The subprocess entrypoints live at the bottom (`python host_client_test.py
{client|default}`); the QT platform is forced to `offscreen` there so no real
display surface is needed beyond pynput's X requirement.
"""
import os
import subprocess
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run_smoke(mode):
    env = dict(os.environ)
    env["PYTHONPATH"] = _REPO_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    env["QT_QPA_PLATFORM"] = "offscreen"
    return subprocess.run([sys.executable, os.path.abspath(__file__), mode],
                          capture_output=True, text=True, env=env, timeout=120)


def _grab(stdout, key):
    """The value of a `KEY value` line printed by a smoke subprocess."""
    for line in stdout.splitlines():
        if line.startswith(key + " "):
            return line[len(key) + 1:]
    raise AssertionError(f"{key} not printed by the smoke run:\n{stdout}")


@unittest.skipUnless(os.environ.get("DISPLAY"),
                     "GUI harness needs an X display — run under xvfb-run")
class TestPolyHostModes(unittest.TestCase):

    def test_default_mode_constructs(self):
        proc = _run_smoke("default")
        self.assertEqual(proc.returncode, 0, f"stdout={proc.stdout}\nstderr={proc.stderr}")
        self.assertIn("SMOKE OK", proc.stdout)
        self.assertIn("CORE_TYPE PolyCore", proc.stdout)
        self.assertIn("DAEMON_QUIT_ACTION absent", proc.stdout)
        self.assertIn("SUPPORT_ACTION absent", proc.stdout)
        self.assertIn("ABOUT_OK True", proc.stdout)

    def test_normal_menu_is_the_simplified_structure(self):
        """The default tray shows only what normal operation needs: no Developer
        submenu, and none of the diagnostic entries that used to sit one click
        deep in "All PolyKybd Commands"."""
        proc = _run_smoke("default")
        self.assertEqual(proc.returncode, 0, f"stdout={proc.stdout}\nstderr={proc.stderr}")
        top = _grab(proc.stdout, "TOPLEVEL")
        self.assertEqual(
            top.split("|"),
            ["Waiting for PolyKybd...", "Pause", "Brightness", "Idle Display",
             "Keycap Script", "Configure Keymap", "Updates", "Maintenance",
             "Settings...", "Help && About", "Quit"])
        # The flat command dump is gone, and so is the demo overlay sender.
        self.assertNotIn("All PolyKybd Commands", top)
        self.assertNotIn("Send Shortcut Overlay", top)
        self.assertNotIn("Developer", top)
        # About + the log file moved into Help & About and are still reachable.
        self.assertIn("ABOUT_UNDER Help && About True True", proc.stdout)
        # "Collect logs..." sits beside them and stays clickable while
        # disconnected — a support bundle is a file read, not a device command,
        # and the disconnected case is when it is most needed.
        self.assertIn("COLLECT_LOGS True True", proc.stdout)
        # The row must actually open the dialog, and a second click must reuse it.
        self.assertIn("COLLECT_LOGS_DIALOG True LogBundleDialog", proc.stdout)
        self.assertIn("COLLECT_LOGS_REUSED True", proc.stdout)
        # The guided "Report a Problem..." row beside it.
        self.assertIn("REPORT_PROBLEM True True", proc.stdout)
        self.assertIn("REPORT_PROBLEM_DIALOG True ReportProblemDialog", proc.stdout)
        self.assertIn("REPORT_PROBLEM_GATED True", proc.stdout)
        self.assertIn("REPORT_PROBLEM_REDACTS True", proc.stdout)
        self.assertIn("REPORT_PROBLEM_REUSED True", proc.stdout)
        # The newer-firmware row must not clutter the normal menu.
        self.assertIn("NEWER_FW_ROW False", proc.stdout)

    def test_developer_mode_only_adds_a_submenu(self):
        """Developer mode must ADD, never rearrange — muscle memory has to survive
        the toggle, so the normal rows stay identical and in the same order."""
        normal = _grab(_run_smoke("default").stdout, "TOPLEVEL").split("|")
        proc = _run_smoke("developer")
        self.assertEqual(proc.returncode, 0, f"stdout={proc.stdout}\nstderr={proc.stderr}")
        dev_top = _grab(proc.stdout, "TOPLEVEL").split("|")
        self.assertIn("Developer", dev_top)
        self.assertEqual([r for r in dev_top if r != "Developer"], normal)
        # And it carries the diagnostic half that left the normal menu.
        subs = _grab(proc.stdout, "DEV_SUBMENUS").split("|")
        for expected in ("Overlays", "Font Pack", "Firmware", "Idle"):
            self.assertIn(expected, subs)

    def test_client_mode_connects_and_renders(self):
        proc = _run_smoke("client")
        self.assertEqual(proc.returncode, 0, f"stdout={proc.stdout}\nstderr={proc.stderr}")
        self.assertIn("SMOKE OK", proc.stdout)
        self.assertIn("CORE_TYPE RemoteCore", proc.stdout)
        self.assertIn("CONNECTED True", proc.stdout)
        self.assertIn("UPDATE_CHECK_OK", proc.stdout)
        # Synthesized from cached device info (no text in the steady-state event).
        self.assertIn("STATUS_TEXT PolyKybd Split72", proc.stdout)
        self.assertIn("FW 0.8.0", proc.stdout)
        self.assertIn("LANG_MENU_BUILT True", proc.stdout)
        self.assertIn("LAYOUT_OK layers=9", proc.stdout)
        self.assertIn("DAEMON_QUIT_ACTION present", proc.stdout)
        self.assertIn("UPDATE_ROUTED_TO_DAEMON True", proc.stdout)
        self.assertIn("CLIENT_ABOUT_OK True", proc.stdout)
        self.assertIn("SERVER_RUNNING True", proc.stdout)
        # One stale bundle -> the row says so and offers the flash, rather than
        # a bare "Sync" whose effect you cannot know before clicking it.
        self.assertIn("FONT_ROW Update keyboard fonts (1)", proc.stdout)
        # Failed-but-current-looking bundle: the row offers the retry and stays live.
        self.assertIn("FONT_ROW_RETRY Retry keyboard fonts (1 failed)", proc.stdout)
        self.assertIn("| enabled True", proc.stdout)
        # Genuinely current: the row answers the question and disables itself.
        self.assertIn("FONT_ROW_CURRENT Keyboard fonts: up to date", proc.stdout)


# ---------------------------------------------------------------------------
# Subprocess entrypoints (each gets a fresh QApplication + isolated sockets)
# ---------------------------------------------------------------------------

def _toplevel(app):
    """The tray's top-level rows as a '|'-joined string.

    Separators and HIDDEN actions are dropped: this is what the user actually
    sees, and the contextual rows (newer-firmware, WinCompose) exist in the menu
    from construction but only surface when they apply.
    """
    return "|".join(a.text() for a in app.menu.actions()
                    if not a.isSeparator() and a.isVisible())


def _smoke_default():
    import logging
    from unittest import mock
    with mock.patch("polyhost.input.linux_gnome_helper.LinuxGnomeInputHelper") as H:
        inst = H.return_value
        inst.get_languages.return_value = []
        inst.get_current_language.return_value = (False, "n/a")
        from polyhost.host import PolyHost
        app = PolyHost(logging.CRITICAL, 0)
        print("CORE_TYPE", type(app.core).__name__)
        assert app.keeb is not None and app.worker is not None and app.cmdMenu is not None
        # In-process Quit already stops everything; no separate daemon-quit entry.
        print("DAEMON_QUIT_ACTION", "absent" if app.exit_with_daemon is None else "present")
        # "Get Support" was folded into the About dialog — no separate menu item.
        print("SUPPORT_ACTION", "absent" if not hasattr(app, "support") else "present")
        # About dialog: builds (without the modal exec_ blocking), shows the host
        # version, and links to homepage + support + all three repos.
        from PyQt5.QtWidgets import QLabel, QDialogButtonBox
        from polyhost._version import __version__ as _ver
        about = app._build_about_dialog()
        blob = " ".join(l.text() for l in about.findChildren(QLabel))
        has_links = all(u in blob for u in (
            "polykybd.org", "ko-fi.com/polykb", "Blog", "Discord", "discord.gg",
            "github.com/thpoll83/PolyKybdHost",
            "github.com/thpoll83/qmk_firmware", "github.com/thpoll83/PolyKybd"))
        # Status block renders either "No keyboard connected" or a "Connected
        # keyboard" line depending on whether HID enumeration finds a device.
        has_status = "eyboard" in blob
        # Environment metrics: uptime + config/log paths.
        has_env = ("Uptime" in blob) and ("Config" in blob) and ("Logs" in blob)
        bb = about.findChild(QDialogButtonBox)
        has_ok = bb.button(QDialogButtonBox.Ok) is not None
        has_copy = any(b.text().startswith("Copy diagnostics") for b in bb.buttons())
        # Diagnostics text (clipboard payload) carries the version + a Config line.
        diag = app._diagnostics_text(app._gather_about_info())
        has_diag = (_ver in diag) and ("Config:" in diag)
        print("ABOUT_OK", (_ver in blob) and has_links and has_status
              and has_env and has_ok and has_copy and has_diag)
        about.deleteLater()
        print("TOPLEVEL", _toplevel(app))
        # Contextual row: built, but invisible until the core reports safe mode.
        print("NEWER_FW_ROW", app.newer_fw_action.isVisible())
        about_parent = app.help_menu.title()
        print("ABOUT_UNDER", about_parent,
              app.about in app.help_menu.actions(), app.log_dialog in app.help_menu.actions())
        # Log collection reads files, never the device, so it must survive the
        # blanket disable managed_connection_status applies on a disconnect —
        # that is exactly when someone goes looking for the logs.
        app.managed_connection_status()
        print("COLLECT_LOGS",
              app.collect_logs_action in app.help_menu.actions(),
              app.collect_logs_action.isEnabled())
        # Same three properties for the guided report row: present, live while
        # disconnected, opens its dialog, and reuses it on a second click (which
        # here also protects a half-written description).
        print("REPORT_PROBLEM",
              app.report_problem_action in app.help_menu.actions(),
              app.report_problem_action.isEnabled())
        app.report_problem_action.trigger()
        rdlg = app.report_problem_dialog
        print("REPORT_PROBLEM_DIALOG", rdlg is not None,
              type(rdlg).__name__ if rdlg else "-")
        # Empty description => nothing to report, so the button must be dead.
        print("REPORT_PROBLEM_GATED",
              rdlg is not None and not rdlg.create_btn.isEnabled())
        # Masking defaults ON here (unlike the local bundle) — a report is aimed
        # at a public tracker.
        print("REPORT_PROBLEM_REDACTS", rdlg is not None and rdlg.redact.isChecked())
        app.report_problem_action.trigger()
        print("REPORT_PROBLEM_REUSED", app.report_problem_dialog is rdlg)
        if rdlg is not None:
            rdlg.close()

        # Actually fire it: a disconnected signal or a broken import would leave
        # the row enabled and do nothing at all when clicked, which is exactly
        # the silent failure the icon test exists to prevent elsewhere.
        app.collect_logs_action.trigger()
        dlg = app.log_bundle_dialog
        print("COLLECT_LOGS_DIALOG", dlg is not None,
              type(dlg).__name__ if dlg else "-")
        # Re-triggering must REUSE the instance: it holds the only reference to
        # the dialog, whose collection QThread is parented to it, so rebuilding
        # mid-collection can destroy a running thread.
        app.collect_logs_action.trigger()
        print("COLLECT_LOGS_REUSED", app.log_bundle_dialog is dlg)
        if dlg is not None:
            dlg.close()
        app.quit_app()
    print("SMOKE OK")


def _smoke_client():
    import logging
    import tempfile
    import time
    from unittest import mock
    from polyhost._version import __version__
    from polyhost.server import protocol
    from polyhost.server.control_server import ControlServer

    class FakeCore:
        def __init__(self):
            self._o = []

        def subscribe(self, cb):
            self._o.append(cb)

        def emit(self, n, p):
            for cb in list(self._o):
                cb(n, p)

        def get_status(self):
            return {"connected": True, "device_present": True, "paused": False,
                    "name": "Split72", "hw_version": "1.0", "protocol": 3,
                    "fw_version": "0.8.0", "current_lang": "enUS"}

        def list_languages(self):
            return ["enUS", "deDE"]

        def keymap_layer_count(self):
            return (True, 9)

        def keymap_buffer(self):
            return (False, "no device")   # dialog takes the failed-read path

        def keymap_default_layer(self):
            return (True, 0)

        def settings_list(self):
            return {"brightness": 25}

        def install_update(self):
            self.install_update_called = True
            return (True, {"queued": True, "version": "9.9.9"})

        # Mutated between _refresh_fontpack_action() calls below to drive the row's
        # three states through the real RPC mirror.
        fontpack_state = "stale"

        def fontpack_bundle_status(self):
            stale = self.fontpack_state == "stale"
            retry = self.fontpack_state == "retry"
            return (True, {"shipped": True, "bundles": [
                {"id": "symbol", "index": 0, "device_version": 4 if stale else 5,
                 "shipped_version": 5, "stale": stale,
                 "retry": retry, "last_error": "COMMIT incomplete" if retry else ""},
                {"id": "emoji", "index": 5, "device_version": 1,
                 "shipped_version": 1, "stale": False, "retry": False}],
                "failed": ["symbol"] if retry else []})

    addr = os.path.join(tempfile.mkdtemp(), "ctl.sock")
    key = protocol.load_or_create_authkey()
    lg = logging.getLogger("smoke")
    lg.addHandler(logging.NullHandler())
    core = FakeCore()
    srv = ControlServer(core, __version__, lg, address=addr, authkey=key)
    srv.start()
    time.sleep(0.2)
    try:
        with mock.patch("polyhost.input.linux_gnome_helper.LinuxGnomeInputHelper") as H:
            inst = H.return_value
            inst.get_languages.return_value = []
            inst.get_current_language.return_value = (False, "n/a")
            inst.set_language.return_value = (True, "")
            from polyhost.host import PolyHost
            app = PolyHost(logging.CRITICAL, 0, client_mode=True, endpoint=addr)
            print("CORE_TYPE", type(app.core).__name__)
            print("CONNECTED", app.core.connected)
            # Update check must not reach self.keeb (None in client mode).
            app._start_update_check()
            print("UPDATE_CHECK_OK")
            # The REAL scenario: a late-connecting client gets a steady-state
            # status_changed with NO text/icon and state_changed False. It must
            # still render a descriptive status (from cached device info) and
            # build the language menu — not stay on "Waiting for PolyKybd".
            core.emit("status_changed", {"connected": True, "device_present": True,
                                         "state_changed": False, "lang": "enUS"})
            for _ in range(60):
                app.processEvents()
                time.sleep(0.02)
            print("STATUS_TEXT", app.status.text())
            print("LANG_MENU_BUILT", app.keeb_lang_menu is not None)
            # Layout editor over RPC (keymap_* via the daemon) — must construct.
            app.open_layout_editor()
            app.processEvents()
            print("LAYOUT_OK layers=%s" % app.layout_dialog.num_layers)
            app.layout_dialog.close()
            # Client mode offers an explicit "stop the daemon too" entry.
            print("DAEMON_QUIT_ACTION", "present" if app.exit_with_daemon is not None else "absent")
            # A self-update in client mode must be driven through the daemon over
            # RPC (so the daemon re-execs onto the new protocol), NOT via a local
            # in-GUI UpdateInstaller thread. Drive _run_update_installer directly
            # (a real install would end in restart_app/os.execv, which we avoid by
            # not emitting the terminal update_finished_ok event here).
            core.install_update_called = False
            rel = type("Rel", (), {"version": "9.9.9", "published_at": ""})()
            app._run_update_installer(rel)
            for _ in range(20):
                app.processEvents()
                time.sleep(0.02)
            print("UPDATE_ROUTED_TO_DAEMON",
                  getattr(core, "install_update_called", False) and app._update_installer is None)
            if app._update_progress is not None:
                app._update_progress.close()
                app._update_progress = None
            # About dialog over the RemoteCore path (client mode): builds and
            # renders the daemon's status snapshot (get_status/list_languages via
            # RPC), the links, and the Copy-diagnostics button — the standalone
            # smoke covers the in-process core; this covers the client core.
            from PyQt5.QtWidgets import QLabel as _QLabel, QDialogButtonBox as _QBB
            about = app._build_about_dialog()
            cblob = " ".join(l.text() for l in about.findChildren(_QLabel))
            c_links = all(u in cblob for u in (
                "polykybd.org", "discord.gg", "github.com/thpoll83/PolyKybdHost"))
            c_bb = about.findChild(_QBB)
            c_copy = any(b.text().startswith("Copy diagnostics") for b in c_bb.buttons())
            c_diag = "Config:" in app._diagnostics_text(app._gather_about_info())
            print("CLIENT_ABOUT_OK",
                  (__version__ in cblob) and c_links and ("eyboard" in cblob)
                  and c_copy and c_diag)
            about.deleteLater()
            # The Updates menu labels the font row from the daemon's per-bundle
            # comparison (over the RPC mirror) instead of hiding it in a dialog.
            app._refresh_fontpack_action()
            print("FONT_ROW", app.fontpack_update_action.text())
            # A bundle whose last flash FAILED reads as up to date by version, so the
            # row must offer a retry instead of claiming everything is fine — the
            # state that left a failed bundle unreachable from the UI (2026-08-17).
            core.fontpack_state = "retry"
            app._refresh_fontpack_action()
            print("FONT_ROW_RETRY", app.fontpack_update_action.text(),
                  "| enabled", app.fontpack_update_action.isEnabled())
            core.fontpack_state = "current"
            app._refresh_fontpack_action()
            print("FONT_ROW_CURRENT", app.fontpack_update_action.text())
            app.quit_app()
        print("SERVER_RUNNING", srv._running)
    finally:
        srv.stop()
    print("SMOKE OK")


def _smoke_developer():
    """Developer mode: the same menu PLUS the Developer submenu — nothing moves."""
    import logging
    from unittest import mock
    with mock.patch("polyhost.input.linux_gnome_helper.LinuxGnomeInputHelper") as H:
        inst = H.return_value
        inst.get_languages.return_value = []
        inst.get_current_language.return_value = (False, "n/a")
        from polyhost.host import PolyHost
        app = PolyHost(logging.CRITICAL, 0, True)
        print("TOPLEVEL", _toplevel(app))
        dev = app._developer_menu
        print("DEV_SUBMENUS", "|".join(a.text() for a in dev.actions() if not a.isSeparator()))
        app.quit_app()
    print("SMOKE OK")


if __name__ == "__main__":
    {"default": _smoke_default, "client": _smoke_client,
     "developer": _smoke_developer}[sys.argv[1]]()
