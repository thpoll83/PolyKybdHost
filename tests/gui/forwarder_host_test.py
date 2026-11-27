"""The forwarder's host setup, with mock input: where it reports, and what it does on a
window change or a failed send.

`PolyForwarder` is a QApplication that imports `pynput` (needs an X server) and
`pywinctl`, and a process can hold one instance, so the checks run in one subprocess
(`python forwarder_host_test.py`, QT offscreen, in an empty working directory because the
forwarder writes `forwarder_log.txt`). The tests skip without a display or pywinctl:

    xvfb-run -a .venv/bin/python -m unittest tests.gui.forwarder_host_test

Nothing here touches the network or the connection table. The socket, the host file's
text, the window and the address watcher are replaced by fakes.
"""
import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run_smoke(*mode):
    env = dict(os.environ)
    env["PYTHONPATH"] = _REPO_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    env["QT_QPA_PLATFORM"] = "offscreen"
    with tempfile.TemporaryDirectory() as workdir:
        return subprocess.run([sys.executable, os.path.abspath(__file__), *(mode or ("run",))],
                              capture_output=True, text=True, env=env, timeout=120,
                              cwd=workdir)


_RESULT = {}


def _results():
    """The scenarios' answers, from one subprocess shared by every test here."""
    if not _RESULT:
        proc = _run_smoke()
        if "SMOKE SKIP" in proc.stdout:
            raise unittest.SkipTest("pywinctl not installed: the forwarder cannot be imported")
        assert proc.returncode == 0, f"stdout={proc.stdout}\nstderr={proc.stderr}"
        for line in proc.stdout.splitlines():
            if line.startswith("RESULT "):
                _RESULT.update(json.loads(line[len("RESULT "):]))
        assert _RESULT, f"no RESULT line:\n{proc.stdout}\n{proc.stderr}"
    return _RESULT


_SWITCH = {}


def _switch_results(mode):
    """The "Switch to ..." scenarios of one subprocess: `switch` (unpaired forwarder) or
    `switch-paired`."""
    if mode not in _SWITCH:
        proc = _run_smoke(mode)
        if "SMOKE SKIP" in proc.stdout:
            raise unittest.SkipTest("pywinctl not installed: the forwarder cannot be imported")
        assert proc.returncode == 0, f"stdout={proc.stdout}\nstderr={proc.stderr}"
        for line in proc.stdout.splitlines():
            if line.startswith("RESULT "):
                _SWITCH[mode] = json.loads(line[len("RESULT "):])
        assert mode in _SWITCH, f"no RESULT line:\n{proc.stdout}\n{proc.stderr}"
    return _SWITCH[mode]


@unittest.skipUnless(os.environ.get("DISPLAY"),
                     "GUI harness needs an X display: run under xvfb-run")
class ForwarderHostSetupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = _results()

    def test_the_harness_starts_no_browser_report_listener(self):
        self.assertTrue(self.r["browser_listener_stubbed"])

    def test_the_harness_never_runs_the_workers_that_rewrite_installed_integrations(self):
        self.assertTrue(self.r["refresh_worker_was_the_stand_in"])
        self.assertTrue(self.r["update_worker_was_the_stand_in"])

    def test_host_names_the_target(self):
        self.assertEqual(self.r["host_only"], "10.0.0.1")

    def test_the_host_file_takes_priority_over_host_and_is_trimmed(self):
        self.assertEqual(self.r["file_over_host"], "10.0.0.2")

    def test_an_absent_or_empty_host_file_means_no_host_even_with_host_set(self):
        self.assertIsNone(self.r["file_absent"])
        self.assertIsNone(self.r["file_empty"])

    def test_a_found_address_is_used_when_nothing_is_named(self):
        self.assertEqual(self.r["detect_found"], "10.0.0.9")

    def test_a_named_host_or_file_wins_over_a_found_address(self):
        self.assertEqual(self.r["detect_with_host"], "10.0.0.1")
        self.assertEqual(self.r["detect_with_file"], "10.0.0.2")

    def test_a_found_address_is_not_used_without_the_authenticated_connection(self):
        self.assertIsNone(self.r["detect_unpaired"])
        self.assertIs(self.r["detect_unpaired_has_watcher"], False)

    def test_a_found_address_is_not_used_when_the_detection_is_off(self):
        self.assertIsNone(self.r["detect_off"])

    def test_the_target_text_says_what_the_forwarder_waits_for(self):
        self.assertIn("waiting for a Remote Desktop or NoMachine", self.r["text_waiting"])
        self.assertIn("needs a paired forwarder", self.r["text_unpaired"])
        self.assertEqual(self.r["text_found"], "10.0.0.9")

    def test_the_about_row_shows_only_while_a_found_address_is_in_use(self):
        self.assertTrue(self.r["about_found"])
        self.assertFalse(self.r["about_named"])
        self.assertFalse(self.r["about_no_address"])
        self.assertFalse(self.r["about_unpaired"])


@unittest.skipUnless(os.environ.get("DISPLAY"),
                     "GUI harness needs an X display: run under xvfb-run")
class ForwarderWatcherWiringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = _results()

    def test_a_window_change_touches_the_watcher_and_a_heartbeat_does_not(self):
        self.assertEqual(self.r["touch_on_change"], 1)
        self.assertEqual(self.r["touch_on_heartbeat"], 0)

    def test_nothing_touches_a_forwarder_without_the_detection(self):
        self.assertEqual(self.r["touch_without_detection"], 0)

    def test_a_failed_send_to_a_found_address_asks_for_a_look(self):
        self.assertEqual(self.r["look_after_failed_send"], 1)

    def test_a_good_send_or_a_named_host_asks_for_no_look(self):
        self.assertEqual(self.r["look_after_good_send"], 0)
        self.assertEqual(self.r["look_after_failed_send_named"], 0)


@unittest.skipUnless(os.environ.get("DISPLAY"),
                     "GUI harness needs an X display: run under xvfb-run")
class ForwarderNoHostTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = _results()

    def test_a_report_that_found_no_host_is_sent_again_as_soon_as_one_exists(self):
        self.assertTrue(self.r["resend_flag_set"])
        self.assertEqual(self.r["sent_when_the_client_is_found"], [[77, "konsole"]])
        self.assertFalse(self.r["resend_flag_cleared"])

    def test_the_window_is_sent_again_once_and_not_on_every_tick(self):
        self.assertEqual(self.r["sent_after_two_more_ticks"], 1)

    def test_a_window_is_sent_once_when_the_host_was_never_missing(self):
        self.assertEqual(self.r["sent_when_the_host_was_never_missing"], 1)

    def test_waiting_for_the_first_client_is_not_logged_as_an_error(self):
        self.assertEqual(self.r["levels_while_waiting_for_a_client"], ["INFO"])

    def test_no_host_without_the_detection_is_still_an_error(self):
        self.assertEqual(self.r["levels_without_detection"], ["ERROR"])
        self.assertTrue(self.r["resend_flag_without_detection"])

    def test_a_host_file_that_appears_later_gets_the_window_once(self):
        self.assertTrue(self.r["resend_flag_without_a_host_file"])
        self.assertEqual(self.r["sent_when_the_host_file_appears"], [[77, "konsole"]])


@unittest.skipUnless(os.environ.get("DISPLAY"),
                     "GUI harness needs an X display: run under xvfb-run")
class ForwarderReporterGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = _results()

    def test_a_window_backend_that_raises_does_not_end_the_forwarder(self):
        self.assertTrue(self.r["reporter_survives_a_failing_backend"])

    def test_the_reporter_loop_is_armed_again_after_a_failed_tick(self):
        self.assertEqual(self.r["reporter_rearmed_after_a_failure"], 1)


@unittest.skipUnless(os.environ.get("DISPLAY"),
                     "GUI harness needs an X display: run under xvfb-run")
class ForwarderSwitchTest(unittest.TestCase):
    """A forwarder that started because of the start_as_forwarder setting."""

    @classmethod
    def setUpClass(cls):
        cls.r = _switch_results("switch")
        cls.paired = _switch_results("switch-paired")

    def test_the_menu_has_switch_to_keyboard_mode_only_for_a_setting_launch(self):
        self.assertEqual(self.r["menu_item"], "Switch to Keyboard Mode…")
        self.assertIsNone(_results()["keyboard_mode_item_when_started_by_option"])

    def test_confirming_clears_the_setting_and_restarts(self):
        self.assertEqual(self.r["yes"], {"calls": [[False, "Switch to Keyboard Mode"]],
                                         "restart": True, "quit": 1})

    def test_declining_changes_nothing(self):
        self.assertEqual(self.r["no"], {"calls": [], "restart": False, "quit": 0})

    def test_a_setting_that_cannot_be_saved_does_not_restart(self):
        self.assertEqual(self.r["not_saved"]["restart"], False)
        self.assertEqual(self.r["not_saved"]["quit"], 0)
        self.assertEqual(self.r["not_saved"]["warned"], 1)

    def test_an_unpaired_forwarder_offers_to_pair_once_after_the_switch(self):
        self.assertEqual(self.r["offer_scheduled"], 1)
        self.assertEqual(self.r["offer_yes_pairs"], 1)
        self.assertEqual(self.r["offer_no_pairs"], 0)

    def test_a_paired_forwarder_does_not_offer_but_still_consumes_the_marker(self):
        self.assertEqual(self.paired["offer_scheduled"], 0)
        self.assertEqual(self.paired["marker_taken"], 1)


@unittest.skipUnless(os.environ.get("DISPLAY"),
                     "GUI harness needs an X display: run under xvfb-run")
class ForwarderRelayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = _results()

    def test_the_legacy_relay_connects_to_the_resolved_host_and_sends_the_window(self):
        self.assertEqual(self.r["relay_ok"], True)
        self.assertEqual(self.r["relay_connect"][0], "10.0.0.5")
        self.assertEqual(self.r["relay_connect"][1], self.r["tcp_port"])
        fields = self.r["relay_payload"].split(";")
        self.assertEqual(fields[:3], ["77", "konsole", "~ : bash"])
        self.assertEqual(len(fields), 4)                    # the OS value rides last

    def test_without_a_host_nothing_is_sent_and_the_failure_is_recorded(self):
        self.assertIs(self.r["relay_no_host_ok"], False)
        self.assertEqual(self.r["relay_no_host_sockets"], 0)
        self.assertIn("no host", self.r["relay_no_host_error"])

    def test_a_refused_connection_is_a_failed_send_not_a_crash(self):
        self.assertIs(self.r["relay_refused_ok"], False)
        self.assertIn("refused", self.r["relay_refused_error"])


# ---------------------------------------------------------------- subprocess side

class _FakeWatcher:
    """What the forwarder asks of the address watcher, with a fixed answer."""

    def __init__(self, address):
        self._address = address
        self.touches = 0
        self.looks = 0

    def address(self):
        return self._address

    def touch(self):
        self.touches += 1

    def request_look(self):
        self.looks += 1


class _FakeSocket:
    """A socket that records the connection and the bytes, or refuses."""
    instances = []
    refuse = False

    def __init__(self, *args, **kwargs):
        self.connected = None
        self.sent = b""
        _FakeSocket.instances.append(self)

    def settimeout(self, _seconds):
        pass

    def connect(self, address):
        if _FakeSocket.refuse:
            raise ConnectionRefusedError("refused by the fake")
        self.connected = address

    def send(self, data):
        self.sent += data

    def close(self):
        pass


class _NoBrowserUrlSource:
    """Stands in for the browser-report listener the forwarder starts at construction
    (it would bind 127.0.0.1:50164 for the whole run)."""

    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        return False

    def current_url(self, _app_name):
        return None

    def restart_if_changed(self):
        pass

    def close(self):
        pass


def _smoke():
    import logging
    import time
    import unittest.mock as mock
    try:
        importlib.import_module("pywinctl")      # forwarder.py imports it at module load
    except Exception:  # noqa: BLE001
        print("SMOKE SKIP no-pywinctl")
        return
    out = {}
    # forwarder.py binds BrowserUrlSource when it is imported, so the stand-in is
    # installed first.
    # The constructor also starts two workers that rewrite the user's installed
    # integrations (editor plugins, the browser extension): both are replaced.
    with mock.patch("polyhost.input.linux_gnome_helper.LinuxGnomeInputHelper"), \
            mock.patch("polyhost.handler.browser_url_source.BrowserUrlSource",
                       _NoBrowserUrlSource), \
            mock.patch("polyhost.services.editor_plugins.start_refresh_thread") as refresh, \
            mock.patch("polyhost.services.browser_extension.update_if_outdated") as update:
        import polyhost.forwarder as fwd
        out["browser_listener_stubbed"] = fwd.BrowserUrlSource is _NoBrowserUrlSource
        app = fwd.PolyForwarder(logging.CRITICAL, host="10.0.0.1")
        out["keyboard_mode_item_when_started_by_option"] = (
            None if app.keyboard_mode_action is None else app.keyboard_mode_action.text())
        host_file = os.path.join(os.getcwd(), "host_ip")

        def setup(host=None, file=None, text=None, detect=False, rpc=False, address=None):
            """Point the forwarder at the given inputs. `text` is the host file's content
            (None: the file is absent)."""
            app.host = host
            app.host_file = file
            app._detect_flag = detect
            app._detect_checked = (time.monotonic(), False)   # the setting stays off
            app._report_rpc = rpc
            app._client_watcher = _FakeWatcher(address) if detect and rpc else None
            if os.path.exists(host_file):
                os.remove(host_file)
            if file and text is not None:
                with open(file, "w") as handle:
                    handle.write(text)

        setup(host="10.0.0.1")
        deadline = time.monotonic() + 2.0                # the update runs on a thread
        while not update.called and time.monotonic() < deadline:
            time.sleep(0.01)
        out["refresh_worker_was_the_stand_in"] = refresh.called
        out["update_worker_was_the_stand_in"] = update.called
        out["host_only"] = app._resolve_host()
        setup(host="10.0.0.1", file=host_file, text="10.0.0.2\n")
        out["file_over_host"] = app._resolve_host()
        setup(host="10.0.0.1", file=host_file, text=None)
        out["file_absent"] = app._resolve_host()
        setup(host="10.0.0.1", file=host_file, text="  \n")
        out["file_empty"] = app._resolve_host()

        setup(detect=True, rpc=True, address="10.0.0.9")
        out["detect_found"] = app._resolve_host()
        setup(host="10.0.0.1", detect=True, rpc=True, address="10.0.0.9")
        out["detect_with_host"] = app._resolve_host()
        setup(file=host_file, text="10.0.0.2", detect=True, rpc=True, address="10.0.0.9")
        out["detect_with_file"] = app._resolve_host()
        setup(detect=True, rpc=False, address="10.0.0.9")
        app._client_watcher = _FakeWatcher("10.0.0.9")   # even one that knows an address
        out["detect_unpaired"] = app._resolve_host()
        app._client_watcher = None
        app._resolve_host()
        out["detect_unpaired_has_watcher"] = app._client_watcher is not None
        setup(detect=False, rpc=True, address="10.0.0.9")
        app._client_watcher = _FakeWatcher("10.0.0.9")
        with mock.patch.object(fwd, "read_setting", return_value=False):
            out["detect_off"] = app._resolve_host()

        setup(detect=True, rpc=True, address=None)
        out["text_waiting"] = app._target_text()
        setup(detect=True, rpc=False)
        out["text_unpaired"] = app._target_text()
        setup(detect=True, rpc=True, address="10.0.0.9")
        out["text_found"] = app._target_text()

        marker = "found from the Remote Desktop or NoMachine connection"

        def about_has_row():
            return marker in app._about_info_html()
        setup(detect=True, rpc=True, address="10.0.0.9")
        out["about_found"] = about_has_row()
        setup(host="10.0.0.1", detect=True, rpc=True, address="10.0.0.9")
        out["about_named"] = about_has_row()
        setup(detect=True, rpc=True, address=None)
        out["about_no_address"] = about_has_row()
        setup(detect=True, rpc=False, address="10.0.0.9")
        out["about_unpaired"] = about_has_row()

        # --- the window reporter and the watcher -----------------------------------
        window = mock.MagicMock()
        window.getHandle.return_value = 77
        window.title = "~ : bash"
        sent = []
        app.send_to_host = lambda *a, **kw: sent.append(a) or True

        def tick(heartbeat_due):
            """One reporter tick on the same window (first: a new one)."""
            app.prev_win = window
            app.last_update_msec = fwd.NEW_WINDOW_ACCEPT_TIME_MSEC * 2
            app.heartbeat_msec = fwd.HEARTBEAT_MSEC if heartbeat_due else 0
            with mock.patch.object(fwd.pwc, "getActiveWindow", return_value=window), \
                    mock.patch.object(fwd, "app_name_for", return_value="konsole"), \
                    mock.patch.object(fwd, "window_pid", return_value=1), \
                    mock.patch.object(fwd, "own_app_name", return_value="konsole"):
                app.active_window_reporter()

        setup(detect=True, rpc=True, address="10.0.0.9")
        app.win = None
        tick(False)                                    # a new window: a change
        out["touch_on_change"] = app._client_watcher.touches
        tick(True)                                     # the same window: a heartbeat
        out["touch_on_heartbeat"] = app._client_watcher.touches - 1
        setup(detect=False, rpc=True)
        app._client_watcher = _FakeWatcher("10.0.0.9")     # never created when off
        app.win = None
        tick(False)
        out["touch_without_detection"] = app._client_watcher.touches
        app.send_to_host = fwd.PolyForwarder.send_to_host.__get__(app)

        # --- a failed send asks the watcher to look ----------------------------------
        def send(ok, **inputs):
            setup(**inputs)
            app._relay = fwd.RelayHealth()
            app._send_to_host = lambda *a, **kw: ok
            app.send_to_host(1, "t", "n")
            return app._client_watcher.looks if app._client_watcher else 0

        out["look_after_failed_send"] = send(False, detect=True, rpc=True, address="10.0.0.9")
        out["look_after_good_send"] = send(True, detect=True, rpc=True, address="10.0.0.9")
        out["look_after_failed_send_named"] = send(
            False, host="10.0.0.1", detect=True, rpc=True, address="10.0.0.9")
        del app._send_to_host                          # the real transport again

        # --- a report that found no host is sent again once a host exists --------------
        app._note_agent_target = lambda host: None       # writes the user's hook target
        real_rpc = fwd.PolyForwarder._send_via_rpc.__get__(app)
        records = []

        class _Collect(logging.Handler):
            def emit(self, record):
                records.append(record)
        handler = _Collect()
        app.log.addHandler(handler)
        app.log.setLevel(logging.DEBUG)
        rpc_sent = []

        def fresh(**inputs):
            setup(**inputs)
            app._relay = fwd.RelayHealth()
            app._resend_when_host = False
            app.win = None
            records.clear()
            rpc_sent.clear()
            app._send_via_rpc = real_rpc

        def landing_levels():
            return [r.levelname for r in records if "not landing" in r.getMessage()]

        fresh(detect=True, rpc=True, address=None)
        tick(False)                                    # a new window, no client found yet
        out["resend_flag_set"] = app._resend_when_host
        out["levels_while_waiting_for_a_client"] = landing_levels()
        app._send_via_rpc = lambda handle, title, name, url=None: (
            rpc_sent.append((handle, name)) or True)
        app._client_watcher._address = "10.0.0.9"      # the watcher found the client
        tick(False)                                    # same window, no heartbeat due
        out["sent_when_the_client_is_found"] = [list(item) for item in rpc_sent]
        out["resend_flag_cleared"] = app._resend_when_host
        tick(False)
        out["sent_after_two_more_ticks"] = len(rpc_sent)

        fresh(detect=True, rpc=True, address="10.0.0.9")
        app._send_via_rpc = lambda handle, title, name, url=None: (
            rpc_sent.append((handle, name)) or True)
        tick(False)
        tick(False)
        out["sent_when_the_host_was_never_missing"] = len(rpc_sent)

        fresh(detect=False, rpc=True)                  # no detection, nothing named
        tick(False)
        out["levels_without_detection"] = landing_levels()
        out["resend_flag_without_detection"] = app._resend_when_host

        # A host file that appears later (a session starts) is a host that appears too.
        fresh(file=host_file, text=None, rpc=True)      # no file yet: no active session
        tick(False)
        out["resend_flag_without_a_host_file"] = app._resend_when_host
        app._send_via_rpc = lambda handle, title, name, url=None: (
            rpc_sent.append((handle, name)) or True)
        with open(host_file, "w") as handle:
            handle.write("10.0.0.5\n")
        tick(False)
        out["sent_when_the_host_file_appears"] = [list(item) for item in rpc_sent]
        app.log.removeHandler(handler)
        app._send_via_rpc = real_rpc

        # --- one failing tick must not end the reporter loop ---------------------------
        armed = []
        survived = True
        with mock.patch.object(fwd.pwc, "getActiveWindow", side_effect=ValueError("boom")), \
                mock.patch.object(fwd.QTimer, "singleShot",
                                  lambda ms, callback: armed.append(ms)):
            try:
                app.active_window_reporter()
            except Exception:  # noqa: BLE001 - the thing being tested
                survived = False
        out["reporter_survives_a_failing_backend"] = survived
        out["reporter_rearmed_after_a_failure"] = len(armed)

        # --- the legacy relay, with a fake socket --------------------------------------
        out["tcp_port"] = fwd.TCP_PORT
        with mock.patch.object(fwd.socket, "socket", _FakeSocket):
            setup(host="10.0.0.5")
            out["relay_ok"] = app._send_to_host(77, "~ : bash", "konsole")
            sock = _FakeSocket.instances[-1]
            out["relay_connect"] = list(sock.connected)
            out["relay_payload"] = sock.sent.decode("utf-8")
            _FakeSocket.instances.clear()
            setup(host=None)
            out["relay_no_host_ok"] = app._send_to_host(77, "t", "n")
            out["relay_no_host_sockets"] = len(_FakeSocket.instances)
            out["relay_no_host_error"] = app._send_error
            setup(host="10.0.0.5")
            _FakeSocket.refuse = True
            out["relay_refused_ok"] = app._send_to_host(77, "t", "n")
            out["relay_refused_error"] = app._send_error
        app.quit_app()
    print("RESULT " + json.dumps(out))


def _smoke_switch(paired):
    """A forwarder that started because of the start_as_forwarder setting."""
    import logging
    import unittest.mock as mock
    try:
        importlib.import_module("pywinctl")
    except Exception:  # noqa: BLE001
        print("SMOKE SKIP no-pywinctl")
        return
    out = {}
    scheduled = []
    taken = []
    keyfile = os.path.join(os.getcwd(), "authkey")      # so no key is made in the config dir
    with open(keyfile, "wb") as handle:
        handle.write(b"test-key")
    with mock.patch("polyhost.input.linux_gnome_helper.LinuxGnomeInputHelper"), \
            mock.patch("polyhost.handler.browser_url_source.BrowserUrlSource",
                       _NoBrowserUrlSource), \
            mock.patch("polyhost.services.editor_plugins.start_refresh_thread"), \
            mock.patch("polyhost.services.browser_extension.update_if_outdated"):
        import polyhost.forwarder as fwd
        from polyhost.services import start_mode
        # Timers are recorded, not run: nothing here may start the reporter loop.
        with mock.patch.object(fwd.QTimer, "singleShot",
                               lambda ms, callback: scheduled.append(
                                   getattr(callback, "__name__", "?"))), \
                mock.patch.object(start_mode, "take_pair_prompt",
                                  lambda: taken.append(1) or True):
            app = fwd.PolyForwarder(logging.CRITICAL, detect_host=True,
                                    report_rpc=paired, report_authkey_file=keyfile,
                                    launched_by_setting=True)
        out["menu_item"] = app.keyboard_mode_action.text()
        out["offer_scheduled"] = scheduled.count("_offer_to_pair")
        out["marker_taken"] = len(taken)

        calls, quits, warned = [], [], []
        app.quit_app = lambda: quits.append(1)

        def switch(answer, saved):
            calls.clear()
            quits.clear()
            warned.clear()
            app.wants_restart = False

            def fake_set(settings, enabled, source):
                calls.append([enabled, source])
                return saved
            with mock.patch.object(start_mode, "set_start_as_forwarder", fake_set), \
                    mock.patch("polyhost.settings.PolySettings", mock.MagicMock()), \
                    mock.patch.object(fwd.QMessageBox, "question", return_value=answer), \
                    mock.patch.object(fwd.message_box, "warning",
                                      lambda *a, **k: warned.append(1)):
                app._switch_to_keyboard_mode()
            return {"calls": [list(c) for c in calls], "restart": app.wants_restart,
                    "quit": len(quits), "warned": len(warned)}

        yes = switch(fwd.QMessageBox.Yes, True)
        out["yes"] = {k: yes[k] for k in ("calls", "restart", "quit")}
        no = switch(fwd.QMessageBox.No, True)
        out["no"] = {k: no[k] for k in ("calls", "restart", "quit")}
        out["not_saved"] = switch(fwd.QMessageBox.Yes, False)

        pairs = []
        with mock.patch.object(app, "_pair_clicked", lambda: pairs.append(1)):
            with mock.patch.object(fwd.QMessageBox, "question",
                                   return_value=fwd.QMessageBox.Yes):
                app._offer_to_pair()
            out["offer_yes_pairs"] = len(pairs)
            pairs.clear()
            with mock.patch.object(fwd.QMessageBox, "question",
                                   return_value=fwd.QMessageBox.No):
                app._offer_to_pair()
            out["offer_no_pairs"] = len(pairs)
    print("RESULT " + json.dumps(out))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        _smoke()
    elif len(sys.argv) > 1 and sys.argv[1] in ("switch", "switch-paired"):
        _smoke_switch(sys.argv[1] == "switch-paired")
    else:
        unittest.main()
