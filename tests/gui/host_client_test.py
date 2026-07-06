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
        self.assertIn("SERVER_RUNNING True", proc.stdout)


# ---------------------------------------------------------------------------
# Subprocess entrypoints (each gets a fresh QApplication + isolated sockets)
# ---------------------------------------------------------------------------

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
            "polykybd.org", "discord.gg", "github.com/thpoll83/PolyKybdHost",
            "github.com/thpoll83/qmk_firmware", "github.com/thpoll83/PolyKybd"))
        # Status block renders either "No keyboard connected" or a "Connected
        # keyboard" line depending on whether HID enumeration finds a device.
        has_status = "eyboard" in blob
        has_ok = about.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok) is not None
        print("ABOUT_OK", (_ver in blob) and has_links and has_status and has_ok)
        about.deleteLater()
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
            app.quit_app()
        print("SERVER_RUNNING", srv._running)
    finally:
        srv.stop()
    print("SMOKE OK")


if __name__ == "__main__":
    {"default": _smoke_default, "client": _smoke_client}[sys.argv[1]]()
