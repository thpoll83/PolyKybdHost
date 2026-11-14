"""The Binary Ninja plugin's UI glue (binaryninja-plugin/polykybd_mode_reporter/__init__.py).

Loaded without Binary Ninja: `binaryninjaui` is missing, so the module defines
`_tick()` and the state but registers nothing. The test sets the sender and
replaces the two reads of the UI (`_prefs`, `_current_url`) and the clock.
Each report goes into a real `BrowserUrlProvider`, so the test shows what the
host picks with two Binary Ninja processes open.
"""
import importlib.util
import itertools
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from polyhost.handler.browser_url import DEFAULT_MAX_AGE_S, BrowserUrlProvider

_PKG = (Path(__file__).resolve().parents[2] / "binaryninja-plugin"
        / "polykybd_mode_reporter")
_count = itertools.count()

HEX = "binaryninja://hex"
LINEAR = "binaryninja://linear/hlil"


def _load_plugin():
    """A separate copy of the plugin package (its own `_state`), as in a
    separate Binary Ninja process."""
    name = f"polykybd_binja_plugin_{next(_count)}"
    spec = importlib.util.spec_from_file_location(
        name, _PKG / "__init__.py", submodule_search_locations=[str(_PKG)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class _Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class _ProviderSender:
    """Delivers each submit straight to the host's provider, as the receiver
    does (`browser_report_server` passes these fields to `update`)."""

    def __init__(self, provider):
        self.provider = provider
        self.sent = []

    def submit(self, port, url, token="", pid=None, input_age=None, focused=True):
        self.sent.append({"url": url, "pid": pid, "input_age": input_age,
                          "focused": focused})
        self.provider.update(app="binaryninja", url=url, focused=focused,
                             pid=pid, input_age=input_age)


class _Instance:
    """One Binary Ninja process running the plugin."""

    def __init__(self, provider, clock, pid, enabled=True):
        self.mod = _load_plugin()
        self.assert_headless()
        self.url = None
        self.enabled = enabled
        self.sender = _ProviderSender(provider)
        self.mod._state["sender"] = self.sender
        self.mod._state["policy"] = self.mod.core.SendPolicy()
        self.mod._prefs = lambda: (self.enabled, 50164, "")
        self.mod._current_url = lambda: self.url
        self.mod.time = SimpleNamespace(monotonic=clock)
        self.mod.os = SimpleNamespace(getpid=lambda: pid)
        self.clock = clock

    def assert_headless(self):
        if self.mod.binaryninjaui is not None:   # pragma: no cover
            raise unittest.SkipTest("binaryninjaui is importable here")

    def focus(self, active):
        self.mod._state["inactive_since"] = None if active else self.clock()

    def tick(self):
        self.mod._tick()


class TwoProcessesTest(unittest.TestCase):
    def setUp(self):
        self.clock = _Clock()
        self.host = BrowserUrlProvider(clock=self.clock, macos_lookup=lambda _a: None)
        self.front = _Instance(self.host, self.clock, pid=1001)
        self.back = _Instance(self.host, self.clock, pid=1002)

    def run_for(self, seconds, check=None):
        end = self.clock.t + seconds
        while self.clock.t < end:
            self.front.tick()
            self.back.tick()
            if check:
                check()
            self.clock.t += 0.5

    def test_background_hex_does_not_win_while_the_front_has_no_view(self):
        # Both show a view; the background one lost focus 30 s ago.
        self.back.url = HEX
        self.back.focus(False)
        self.clock.t += 30.0
        self.front.url = LINEAR
        self.front.focus(True)
        self.run_for(2.0)
        self.assertEqual(self.host.current_url("binaryninja"), LINEAR)

        # The front instance closes its last file: the main set at once ...
        self.front.url = None
        self.front.tick()
        self.assertIsNone(self.host.current_url("binaryninja"))

        # ... and for as long as it shows no view, well past the 8 s window.
        def no_hex():
            self.assertIsNone(self.host.current_url("binaryninja"),
                              f"at +{self.clock.t:.1f} s")
        self.run_for(DEFAULT_MAX_AGE_S * 3, check=no_hex)

        no_view = [s for s in self.front.sender.sent if s["url"] is None]
        self.assertGreater(len(no_view), 3, "the no-view report is not kept fresh")
        self.assertTrue(all(s["input_age"] == 0.0 and s["focused"] is False
                            and s["pid"] == 1001 for s in no_view))

    def test_the_keepalive_is_the_view_keepalive(self):
        self.front.focus(True)
        self.run_for(30.0)
        times = len([s for s in self.front.sender.sent if s["url"] is None])
        # 30 s at one report per KEEPALIVE_S (3 s), first one at once.
        self.assertEqual(times, int(30.0 / self.front.mod.core.KEEPALIVE_S))

    def test_a_view_opened_again_is_sent_at_once(self):
        self.front.focus(True)
        self.front.tick()
        self.front.url = HEX
        self.front.tick()
        self.assertEqual(self.front.sender.sent[-1]["url"], HEX)
        self.assertEqual(self.host.current_url("binaryninja"), HEX)


class DisabledTest(unittest.TestCase):
    def test_turning_reporting_off_sends_one_withdrawal_with_input_age(self):
        clock = _Clock()
        host = BrowserUrlProvider(clock=clock, macos_lookup=lambda _a: None)
        inst = _Instance(host, clock, pid=7)
        inst.url = HEX
        inst.focus(False)
        clock.t += 4.0
        inst.tick()
        inst.enabled = False
        for _ in range(20):
            clock.t += 0.5
            inst.tick()
        self.assertEqual([s["url"] for s in inst.sender.sent], [HEX, None])
        self.assertEqual(inst.sender.sent[-1]["input_age"], 4.5)
        self.assertIs(inst.sender.sent[-1]["focused"], False)


if __name__ == "__main__":
    unittest.main()
