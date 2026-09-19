"""The forwarder-resolved app identity, and why the RECEIVER decides.

The application runs on the forwarder's machine, so its `.desktop` entry, its PE
resources and its pid all live there. Only the forwarder can ask the OS that is
actually running it — a keyboard machine on Windows has no desktop entries at
all. So the identity travels over `window.report`, and the icon travels only
when this side says it needs it.
"""
import base64
import unittest
from unittest.mock import patch

import polyhost.util.log_util  # noqa: F401 - installs Logger.debug_detailed

from polyhost.handler.remote_window import MAX_FORWARDED_APPS, RemoteHandler
from polyhost.server.window_report_server import (MAX_ICON_B64,
                                                  WindowReportServer)
from polyhost.services import shortcut_fetcher

ICON = b"\x89PNG\r\n\x1a\n-pretend-this-is-art"
OTHER = b"\x89PNG\r\n\x1a\n-a-different-icon"
# What `shortcut_relay.decode` hands the handler: already-validated triples.
SHORTCUTS = ((1, 0x16, "Save"), (1, 0x06, "Copy"))


def _handler():
    return RemoteHandler(mapping={})


class _ShortcutsOff:
    """Pin ONE ask per class.

    The reply now carries two independent asks, so a class asserting the whole
    dict is otherwise coupled to whether the OTHER feature happens to be on --
    and `shortcut_icons_enabled` defaults True, so every icon test would have to
    spell out a shortcut expectation it does not care about. Turning it off here
    keeps the icon contract readable; `WantShortcutsTest` pins the other ask and
    `test_both_asks_can_ride_ONE_reply` pins that they compose.
    """

    def setUp(self):
        off = patch.object(shortcut_fetcher, "enabled", return_value=False)
        off.start()
        self.addCleanup(off.stop)
        super().setUp()


class WantIconTest(_ShortcutsOff, unittest.TestCase):

    def test_the_first_sighting_of_an_app_ASKS_for_the_icon(self):
        h = _handler()
        got = h.report_window(1, "gimp", "GIMP", names=("GNU Image Manipulation",),
                              icon_key="abc123")
        self.assertEqual(got, {"want_icon": True})

    def test_once_the_icon_ARRIVES_it_is_not_asked_for_again(self):
        h = _handler()
        h.report_window(1, "gimp", "GIMP", icon_key="abc123")
        self.assertIsNone(h.report_window(1, "gimp", "GIMP", icon_key="abc123",
                                          icon=ICON))
        self.assertIsNone(h.report_window(1, "gimp", "GIMP", icon_key="abc123"))
        self.assertEqual(h.forwarded_identity("gimp")["icon"], ICON)

    def test_a_CHANGED_icon_key_asks_again(self):
        # ⚠️ Keyed on the content hash, not on "we have an icon". A theme change
        # or an app update gives the same application different art, and mere
        # presence would pin the old picture forever.
        h = _handler()
        h.report_window(1, "gimp", "GIMP", icon_key="abc123", icon=ICON)
        self.assertEqual(h.report_window(1, "gimp", "GIMP", icon_key="zzz999"),
                         {"want_icon": True})

    def test_an_app_with_NO_icon_is_never_asked(self):
        # The forwarder found nothing to offer, so asking would loop forever.
        h = _handler()
        self.assertIsNone(h.report_window(1, "nosuchapp", "T", icon_key=None))
        self.assertIsNone(h.report_window(1, "nosuchapp", "T", icon_key=None))

    def test_an_app_that_LOSES_its_icon_is_not_asked_forever(self):
        # ⚠️ Found by a mutation sweep, which is the only reason this case
        # exists. Removing the `icon_key is None` guard is INERT for an app that
        # never had art — None != None is already False — so the obvious test
        # passes either way. The guard earns its keep on the TRANSITION: once a
        # key is stored, a later report carrying none would compare "abc" != None
        # and ask on every single report, for an icon the forwarder just said it
        # does not have.
        h = _handler()
        h.report_window(1, "gimp", "GIMP", icon_key="abc123", icon=ICON)
        self.assertIsNone(h.report_window(1, "gimp", "GIMP", icon_key=None))
        self.assertIsNone(h.report_window(1, "gimp", "GIMP", icon_key=None))

    def test_display_NAMES_are_stored_without_any_icon(self):
        # The names alone fix the catalog lookup, and they work even when the
        # keyboard machine is an OS that has no notion of the sender's icons.
        h = _handler()
        h.report_window(1, "gnome-text-edit", "x", names=("Text Editor",))
        self.assertEqual(h.forwarded_identity("gnome-text-edit")["names"],
                         ("Text Editor",))

    def test_an_unknown_app_has_NO_identity(self):
        self.assertIsNone(_handler().forwarded_identity("never-seen"))


class ReceiverDecidesTest(_ShortcutsOff, unittest.TestCase):
    """The three ways a sender-side 'already sent it' flag goes stale."""

    def test_a_RESTARTED_daemon_asks_again(self):
        # The forwarder still believes it delivered the icon. A fresh handler is
        # a fresh cache, and it says so on the very next report.
        old = _handler()
        old.report_window(1, "gimp", "GIMP", icon_key="abc123", icon=ICON)
        self.assertIsNone(old.report_window(1, "gimp", "GIMP", icon_key="abc123"))

        restarted = _handler()
        self.assertEqual(restarted.report_window(1, "gimp", "GIMP",
                                                 icon_key="abc123"),
                         {"want_icon": True})

    def test_a_DIFFERENT_machine_asks_again(self):
        # --host-file can repoint the forwarder mid-session; WindowReportSession
        # reconnects for exactly that. The new host never saw the icon.
        first, second = _handler(), _handler()
        first.report_window(1, "gimp", "GIMP", icon_key="abc123", icon=ICON)
        self.assertEqual(second.report_window(1, "gimp", "GIMP",
                                              icon_key="abc123"),
                         {"want_icon": True})

    def test_an_EVICTED_app_asks_again(self):
        h = _handler()
        h.report_window(1, "gimp", "GIMP", icon_key="abc123", icon=ICON)
        for i in range(MAX_FORWARDED_APPS + 2):
            h.report_window(1, "filler%d" % i, "t", icon_key="k%d" % i)
        self.assertEqual(h.report_window(1, "gimp", "GIMP", icon_key="abc123"),
                         {"want_icon": True})

    def test_the_cache_stays_BOUNDED(self):
        # ⚠️ On the network path the app name is attacker-shaped, so an
        # unbounded dict keyed on it leaks memory in the process that owns the
        # HID device.
        h = _handler()
        for i in range(MAX_FORWARDED_APPS * 3):
            h.report_window(1, "app%d" % i, "t", icon_key="k%d" % i)
        self.assertLessEqual(len(h._forwarded_identity), MAX_FORWARDED_APPS)


class IconDecodeTest(unittest.TestCase):
    """`window.report` is the only method on the NETWORK endpoint, so its params
    are the sole attacker-shaped input the daemon parses."""

    def test_valid_base64_round_trips(self):
        blob = base64.b64encode(ICON).decode("ascii")
        self.assertEqual(WindowReportServer._decode_icon(blob), ICON)

    def test_absent_or_empty_is_simply_None(self):
        self.assertIsNone(WindowReportServer._decode_icon(None))
        self.assertIsNone(WindowReportServer._decode_icon(""))

    def test_an_OVERSIZED_blob_is_refused_before_decoding(self):
        # Refused on LENGTH, so the daemon never materialises the payload.
        with self.assertRaises(ValueError) as cm:
            WindowReportServer._decode_icon("A" * (MAX_ICON_B64 + 4))
        self.assertIn("too large", str(cm.exception))

    def test_junk_is_refused_rather_than_silently_truncated(self):
        with self.assertRaises(ValueError):
            WindowReportServer._decode_icon("not valid base64 !!!")

    def test_a_non_string_is_refused(self):
        with self.assertRaises(ValueError):
            WindowReportServer._decode_icon(12345)


class WantShortcutsTest(unittest.TestCase):
    """The same receiver-decides contract, for the app's SHORTCUTS.

    Its accelerators come out of an accessibility tree in a process on the
    forwarder's machine, so this side cannot read them at all — asking the local
    backend walks the wrong tree, finds nothing, and reports "exposes no
    accelerators" for an app that exposes sixteen.
    """

    def setUp(self):
        on = patch.object(shortcut_fetcher, "enabled", return_value=True)
        on.start()
        self.addCleanup(on.stop)

    def test_the_first_sighting_of_an_app_ASKS(self):
        self.assertEqual(_handler().report_window(1, "gimp", "GIMP"),
                         {"want_shortcuts": True})

    def test_once_they_ARRIVE_it_stops_asking(self):
        h = _handler()
        self.assertIsNone(h.report_window(1, "gimp", "GIMP", shortcuts=SHORTCUTS))
        self.assertIsNone(h.report_window(1, "gimp", "GIMP"))
        self.assertEqual(h.forwarded_shortcuts("gimp"), SHORTCUTS)

    def test_an_EMPTY_harvest_is_an_answer_and_stops_the_asking(self):
        # ⚠️ The one that would loop forever if `()` were read as "no answer":
        # most applications expose nothing, so this is the COMMON case, and
        # re-asking would re-walk a proven-empty tree on the other machine on
        # every report.
        h = _handler()
        self.assertIsNone(h.report_window(1, "gedit", "gedit", shortcuts=()))
        self.assertIsNone(h.report_window(1, "gedit", "gedit"))
        self.assertEqual(h.forwarded_shortcuts("gedit"), ())

    def test_UNASKED_and_EMPTY_are_different_answers(self):
        h = _handler()
        self.assertIsNone(h.forwarded_shortcuts("gimp"))
        h.report_window(1, "gimp", "GIMP", shortcuts=())
        self.assertEqual(h.forwarded_shortcuts("gimp"), ())

    def test_the_SETTING_being_off_never_asks(self):
        # Off means no application's accessibility tree is read ANYWHERE: the
        # forwarder harvests only when asked, so not asking is what carries the
        # privacy switch across the machine boundary.
        with patch.object(shortcut_fetcher, "enabled", return_value=False):
            self.assertIsNone(_handler().report_window(1, "gimp", "GIMP"))

    def test_a_RESTARTED_daemon_asks_again(self):
        # The sender cannot know this happened — the whole reason the answer
        # comes from here rather than from a forwarder-side "already sent" flag.
        _handler().report_window(1, "gimp", "GIMP", shortcuts=SHORTCUTS)
        self.assertEqual(_handler().report_window(1, "gimp", "GIMP"),
                         {"want_shortcuts": True})

    def test_an_EVICTED_app_asks_again(self):
        h = _handler()
        h.report_window(1, "gimp", "GIMP", shortcuts=SHORTCUTS)
        for i in range(MAX_FORWARDED_APPS + 1):
            h.report_window(2, "app%d" % i, "t", shortcuts=())
        self.assertEqual(h.report_window(1, "gimp", "GIMP"),
                         {"want_shortcuts": True})

    def test_the_cache_stays_BOUNDED(self):
        # The app name is attacker-shaped on the network path, so an unbounded
        # dict keyed on it is a slow memory leak against the process that owns
        # the HID device.
        h = _handler()
        for i in range(MAX_FORWARDED_APPS * 3):
            h.report_window(1, "app%d" % i, "t", shortcuts=SHORTCUTS)
        self.assertLessEqual(len(h._forwarded_shortcuts), MAX_FORWARDED_APPS)

    def test_shortcuts_do_NOT_make_an_empty_record_read_as_an_IDENTITY(self):
        """⚠️ Why they live in their own dict rather than beside the identity.

        `forwarded_identity` answers `known or None` precisely so an empty
        record does not read as "the identity arrived" — a caller that latched
        one would never look again, and the real identity 300 ms later would be
        ignored for the life of the process. Putting a shortcut list in that
        record would make every record non-empty and re-open exactly that bug.
        """
        h = _handler()
        h.report_window(1, "gimp", "GIMP", shortcuts=SHORTCUTS)
        self.assertIsNone(h.forwarded_identity("gimp"))

    def test_both_asks_can_ride_ONE_reply(self):
        self.assertEqual(
            _handler().report_window(1, "gimp", "GIMP", icon_key="abc123"),
            {"want_icon": True, "want_shortcuts": True})


if __name__ == "__main__":
    unittest.main()


class LruOrderTest(_ShortcutsOff, unittest.TestCase):
    """The cache must keep what is USED, not what arrived first."""

    def test_a_REPEATEDLY_seen_app_survives_pressure(self):
        # ⚠️ The regression this exists for: refreshing the LRU only when the
        # entry is CREATED means the app you actually use never moves, so it
        # ages out while apps seen once sit at the fresh end. Exactly backwards.
        h = _handler()
        h.report_window(1, "gimp", "GIMP", icon_key="abc123", icon=ICON)
        # ⚠️ MORE than the bound, or nothing is ever evicted and the test passes
        # against the broken version too — which is exactly what it did on the
        # first cut, caught by re-running the mutation rather than by the green
        # suite.
        for i in range(MAX_FORWARDED_APPS + 10):
            h.report_window(1, "filler%d" % i, "t", icon_key="k%d" % i)
            h.report_window(1, "gimp", "GIMP", icon_key="abc123")   # keep using it
        self.assertIsNotNone(h.forwarded_identity("gimp"))
        self.assertIsNone(h.report_window(1, "gimp", "GIMP", icon_key="abc123"),
                          "the icon should still be cached, so no re-ask")


class NameKeyTest(_ShortcutsOff, unittest.TestCase):
    """The cache key and the lookup key must be the SAME normalisation."""

    def test_a_windows_exe_name_round_trips(self):
        # ⚠️ The regression: `report_window` filed the identity under the raw
        # "Code.exe" while `RemoteHandler.name` — what the matcher and
        # `focused_app()` use — is "code". The forwarded identity was then
        # invisible for every app whose name has a dot or a capital, which is
        # every Windows app. It agreed by luck for "gnome-text-edit".
        h = _handler()
        h.report_window(1, "Code.exe", "main.py", names=("Visual Studio Code",),
                        icon_key="k1", icon=ICON)
        self.assertIsNotNone(h.forwarded_identity("code"))
        self.assertEqual(h.forwarded_identity("code")["icon"], ICON)

    def test_the_want_icon_answer_uses_the_same_key(self):
        h = _handler()
        h.report_window(1, "Code.exe", "t", icon_key="k1", icon=ICON)
        # Same app, reported again — must NOT ask for the icon a second time.
        self.assertIsNone(h.report_window(1, "Code.exe", "t", icon_key="k1"))


class EmptyRecordIsNotAnIdentityTest(_ShortcutsOff, unittest.TestCase):
    """The first report arrives BEFORE the forwarder has resolved anything.

    ⚠️ `_note_identity` creates the record on that first report, so
    `forwarded_identity` used to answer `{}` -- which is not None, so a caller
    testing `identity is not None` latched it as "the identity arrived" and
    never looked again. The real one, 300 ms later, was ignored for the life of
    the process.

    Measured 2026-09-17: GNOME Text Editor, Nautilus and Calculator all logged
    `OS names: <none>` this way, while VS Code and Chrome worked -- because
    those two ALSO run locally on the keyboard machine, so their first lookup
    came from the local window with a genuinely None identity and the remote one
    was still the first real one. Same code, and the apps that happened to exist
    on both machines were the ones that worked.
    """

    def test_a_report_with_nothing_resolved_yields_NO_identity(self):
        h = _handler()
        h.report_window(1, "gnome-text-edit", "t")
        self.assertIsNone(h.forwarded_identity("gnome-text-edit"))

    def test_names_alone_ARE_an_identity(self):
        h = _handler()
        h.report_window(1, "gnome-text-edit", "t", names=("Text Editor",))
        self.assertEqual(h.forwarded_identity("gnome-text-edit")["names"],
                         ("Text Editor",))

    def test_an_icon_key_ALONE_is_deliberately_not_recorded(self):
        # ⚠️ Not an oversight, and I asserted the opposite first. The key names
        # the icon we HOLD, so recording it before the art arrives would make
        # `want_icon` false forever and the icon would never be requested at
        # all. A key with no names and no icon therefore leaves nothing to
        # report -- and the report that carries it always carries the names too,
        # because the forwarder resolves both in one lookup.
        h = _handler()
        h.report_window(1, "gimp", "t", icon_key="abc123")
        self.assertIsNone(h.forwarded_identity("gimp"))
        self.assertEqual(h.report_window(1, "gimp", "t", icon_key="abc123"),
                         {"want_icon": True}, "and it must still ask for it")

    def test_an_empty_report_after_a_real_one_does_not_erase_it(self):
        h = _handler()
        h.report_window(1, "gimp", "t", names=("GIMP",), icon_key="abc123")
        h.report_window(1, "gimp", "t")
        self.assertEqual(h.forwarded_identity("gimp")["names"], ("GIMP",))

