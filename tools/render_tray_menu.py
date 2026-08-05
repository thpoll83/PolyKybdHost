#!/usr/bin/env python3
"""Render the tray menu to PNGs for the documentation.

The docs describe the tray menu in a table, which goes stale the moment someone
reorders a row. This renders the **real** menu — the same `QMenu` the app builds,
with the real labels, icons, separators and order — so a docs image can be
regenerated from the code instead of re-screenshotted by hand.

It runs the GUI in `--connect` client mode against a small fake core, because a
menu rendered with no keyboard attached is entirely greyed out and useless as
documentation. The fake reports a connected Split72 with both feature
capabilities, which is what a normal user's menu looks like.

Usage — on a headless box, xvfb + Qt's offscreen platform (the same pairing the
GUI tests use):

    xvfb-run -a env QT_QPA_PLATFORM=offscreen \
        .venv/bin/python tools/render_tray_menu.py --out-dir /tmp/menus

The X display is for **pynput**, which host.py imports at module load and which
refuses to import without an X connection; Qt itself renders offscreen, so the
xcb platform plugin (and its system libs) are not needed.

Writes `tray-menu.png` (normal), `tray-menu-developer.png` (developer mode) and
one `submenu-<name>.png` per top-level submenu.

⚠️ This is a Qt render on the machine that runs it, so it carries THAT platform's
menu style — on Linux it is not pixel-identical to what a Windows or macOS user
sees. The content (labels, order, icons, grouping) is what the image is for.
"""
import argparse
import logging
import os
import sys
import tempfile
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)


class _FakeCore:
    """The subset of PolyCore the control server exposes, answering as a
    connected Split72. Mirrors the shape of a real status payload."""

    NAME = "Split72"

    def __init__(self):
        self._obs = []

    # -- observer seam -------------------------------------------------
    def subscribe(self, cb):
        self._obs.append(cb)

    def emit(self, name, payload):
        for cb in list(self._obs):
            cb(name, payload)

    # -- state ---------------------------------------------------------
    def get_status(self):
        return {
            "connected": True, "device_present": True, "paused": False,
            "name": self.NAME, "hw_version": "1.0", "protocol": 12,
            "fw_version": "0.9.85", "current_lang": "enUS",
            # Feature gating: without these the Idle/Keycap-Script submenus
            # render disabled, which is not what a normal user sees.
            "capabilities": {"idle_style": True, "glyph_script": True},
        }

    def list_languages(self):
        return ["enUS", "deDE", "frFR", "esES", "jaJP"]

    def settings_list(self):
        return {"brightness_set_daylight_dependent": True}

    def settings_get(self, key):
        return self.settings_list().get(key)

    def fontpack_bundle_status(self):
        # One stale bundle, so the self-labelling Updates row shows its
        # interesting state rather than the "up to date" one.
        return (True, {"shipped": True, "bundles": [
            {"id": "symbol", "index": 0, "device_version": 4,
             "shipped_version": 5, "stale": True}]})

    def get_idle_style(self):
        return (True, 1)          # Jitter

    def get_glyph_script(self):
        return (True, 0)          # Standard

    def keymap_layer_count(self):
        return (True, 9)


def _grab(menu, path, log):
    """Render one QMenu to a PNG.

    A QMenu that has never been shown has no laid-out geometry, so grab() would
    yield a 100x30 stub. show() + processEvents() forces the real layout; the
    menu is hidden again straight after so the next grab isn't overlapped.
    """
    from PyQt5.QtWidgets import QApplication
    menu.ensurePolished()
    menu.show()
    QApplication.processEvents()
    # resize(sizeHint()), NOT adjustSize(): adjustSize clamps a window to 2/3 of
    # the screen, and the offscreen platform reports an 800x600 screen — so the
    # taller (developer) menu was silently capped at 400px and lost its last row.
    menu.resize(menu.sizeHint())
    QApplication.processEvents()
    pixmap = menu.grab()
    menu.hide()
    QApplication.processEvents()
    pixmap.save(path)
    log("wrote %s (%dx%d)", path, pixmap.width(), pixmap.height())
    return pixmap


def _render(developer, out_dir, log):
    from polyhost.server import protocol
    from polyhost.server.control_server import ControlServer
    from polyhost._version import __version__

    addr = os.path.join(tempfile.mkdtemp(prefix="polymenu_"), "ctl.sock")
    key = protocol.load_or_create_authkey()
    quiet = logging.getLogger("render_tray_menu.server")
    quiet.addHandler(logging.NullHandler())
    core = _FakeCore()
    srv = ControlServer(core, __version__, quiet, address=addr, authkey=key)
    srv.start()
    time.sleep(0.2)
    written = []
    try:
        from unittest import mock
        # Stub the OS input helper: rendering a menu must not try to switch the
        # host's system input language (which needs a real desktop session — it
        # throws on a bare container) and the menu does not depend on it.
        helper = mock.patch("polyhost.input.linux_gnome_helper.LinuxGnomeInputHelper")
        stub = helper.start()
        stub.return_value.get_languages.return_value = []
        stub.return_value.get_current_language.return_value = (False, "n/a")
        stub.return_value.set_language.return_value = (True, "")

        from polyhost.host import PolyHost
        app = PolyHost(logging.CRITICAL, 0, developer, client_mode=True, endpoint=addr)
        # Drive the status render so the language menu is built and everything
        # is enabled, exactly as on a real connect.
        core.emit("status_changed", {"connected": True, "device_present": True,
                                     "state_changed": True, "lang": "enUS"})
        for _ in range(60):
            app.processEvents()
            time.sleep(0.02)
        # The two self-labelling rows normally update on aboutToShow, which a
        # grab() does not trigger.
        app._refresh_fontpack_action()
        app.cmdMenu._refresh_auto_brightness_action()

        suffix = "-developer" if developer else ""
        path = os.path.join(out_dir, f"tray-menu{suffix}.png")
        _grab(app.menu, path, log)
        written.append(path)

        for action in app.menu.actions():
            sub = action.menu()
            if sub is None or not action.isVisible():
                continue
            slug = action.text().replace("&&", "and").replace("&", "")
            slug = "".join(c if c.isalnum() else "-" for c in slug).strip("-").lower()
            path = os.path.join(out_dir, f"submenu-{slug}{suffix}.png")
            _grab(sub, path, log)
            written.append(path)

        app.quit_app()
    finally:
        try:
            helper.stop()
        except (NameError, RuntimeError):
            pass
        srv.stop()
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default="menu-renders")
    ap.add_argument("--mode", choices=["normal", "developer", "both"], default="both")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    log = logging.getLogger("render_tray_menu")
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Qt renders into pixmaps fine on the offscreen platform (what the GUI tests
    # use), which avoids needing the xcb plugin's system libs. Default to it
    # unless the caller picked a platform.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if not os.environ.get("DISPLAY"):
        # Not for Qt — pynput (imported by host.py) refuses to load without one.
        print("error: no DISPLAY; run under `xvfb-run -a` (pynput needs an X "
              "connection even though Qt renders offscreen)", file=sys.stderr)
        return 2

    modes = [False, True] if args.mode == "both" else [args.mode == "developer"]
    # One QApplication per process, and PolyHost IS the QApplication — so each
    # mode needs its own process. Re-exec for the second one.
    if len(modes) > 1:
        import subprocess
        rc = 0
        for mode in ("normal", "developer"):
            rc |= subprocess.run([sys.executable, os.path.abspath(__file__),
                                  "--out-dir", args.out_dir, "--mode", mode]).returncode
        return rc

    _render(modes[0], args.out_dir, log.info)
    return 0


if __name__ == "__main__":
    sys.exit(main())
