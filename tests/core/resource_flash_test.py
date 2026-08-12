"""The three resource-flash entry points that ride the font-pack transport.

``flash_fontpack`` / ``install_doomwad`` / ``install_doompack`` were three
near-identical ~35-line blocks differing only in four things: the "cannot read"
noun, the validator, the flasher, and the ``kind`` tag on the events. These pin
the behaviour every one of them must keep — the gating, the fail-fast
validation, the cancel relay into the flash engine, and the ``kind``-tagged
event stream ``polyctl`` and the tray render their wording from — so the shared
implementation cannot quietly change one of them.
"""
import logging
import threading
import unittest
from unittest import mock

from polyhost.core import events, poly_core
from polyhost.core.poly_core import PolyCore


def make_core(*, connected=True, device_present=True, paused=False):
    core = PolyCore.__new__(PolyCore)
    core.log = logging.getLogger("test.polycore.resflash")
    core.connected = connected
    core.device_present = device_present
    core.paused = paused
    core._observers = []
    core._observers_lock = threading.Lock()
    core.worker = mock.MagicMock()
    core.keeb = mock.MagicMock()
    core.telemetry = mock.MagicMock()
    return core


def _events(core):
    seen = []
    core.subscribe(lambda n, p: seen.append((n, p)))
    return seen


def _run_submitted_job(core, cancel_set=False):
    """Invoke the job the core handed to worker.submit, as the worker would."""
    core.worker.submit.assert_called_once()
    _name, job = core.worker.submit.call_args[0]
    cancel = threading.Event()
    if cancel_set:
        cancel.set()
    job(cancel)


# (method, kwargs, read-error noun, validator, flasher, expected kind)
CASES = [
    ("flash_fontpack", {}, "font-pack file",
     "validate_fontpack", "flash_fontpack", events.FLASH_KIND_FONTPACK),
    ("install_doomwad", {}, "game-data file",
     "validate_doomwad", "flash_doomwad", events.FLASH_KIND_DOOMWAD),
    ("install_doompack", {}, "engine-pack file",
     "validate_doompack", "flash_doompack", events.FLASH_KIND_DOOMPACK),
]


class TestResourceFlashCommon(unittest.TestCase):
    """Run the same contract against all three entry points."""

    def test_gating_blocks_when_absent(self):
        for name, kwargs, *_ in CASES:
            with self.subTest(method=name):
                core = make_core(connected=False, device_present=False)
                ok, msg = getattr(core, name)("f.bin", **kwargs)
                self.assertFalse(ok)
                self.assertIn("No PolyKybd present", msg)
                core.worker.submit.assert_not_called()

    def test_gating_blocks_when_paused(self):
        for name, kwargs, *_ in CASES:
            with self.subTest(method=name):
                core = make_core(paused=True)
                ok, _ = getattr(core, name)("f.bin", **kwargs)
                self.assertFalse(ok)
                core.worker.submit.assert_not_called()

    def test_unreadable_file_fails_fast_with_its_own_noun(self):
        for name, kwargs, noun, *_ in CASES:
            with self.subTest(method=name):
                core = make_core()
                ok, msg = getattr(core, name)("/no/such/file", **kwargs)
                self.assertFalse(ok)
                self.assertIn(noun, msg)
                core.worker.submit.assert_not_called()

    def test_invalid_payload_fails_before_queueing(self):
        for name, kwargs, _noun, validator, _flasher, _kind in CASES:
            with self.subTest(method=name):
                core = make_core()
                with mock.patch("builtins.open", mock.mock_open(read_data=b"x")), \
                     mock.patch.object(poly_core.hid_fontpack, validator,
                                       return_value=(False, "bad magic")):
                    ok, msg = getattr(core, name)("f.bin", **kwargs)
                self.assertFalse(ok)
                self.assertEqual(msg, "bad magic")
                core.worker.submit.assert_not_called()

    def test_valid_payload_queues_an_uncoalesced_job(self):
        """A flash must never be superseded by a later job — so no coalesce_key."""
        for name, kwargs, _noun, validator, flasher, _kind in CASES:
            with self.subTest(method=name):
                core = make_core()
                with mock.patch("builtins.open", mock.mock_open(read_data=b"x")), \
                     mock.patch.object(poly_core.hid_fontpack, validator,
                                       return_value=(True, "")), \
                     mock.patch.object(poly_core.hid_fontpack, flasher,
                                       return_value=(True, "done")):
                    ok, payload = getattr(core, name)("f.bin", **kwargs)
                    self.assertTrue(ok)
                    self.assertEqual(payload, {"queued": True})
                    self.assertEqual(core.worker.submit.call_args.kwargs, {})

    def test_progress_and_done_events_carry_the_right_kind(self):
        for name, kwargs, _noun, validator, flasher, kind in CASES:
            with self.subTest(method=name):
                core = make_core()
                seen = _events(core)

                def _flash(*a, progress_cb=None, **kw):
                    progress_cb(10, "erasing")
                    progress_cb(100, "written")
                    return True, "ok"

                with mock.patch("builtins.open", mock.mock_open(read_data=b"x")), \
                     mock.patch.object(poly_core.hid_fontpack, validator,
                                       return_value=(True, "")), \
                     mock.patch.object(poly_core.hid_fontpack, flasher,
                                       side_effect=_flash):
                    getattr(core, name)("f.bin", **kwargs)
                    _run_submitted_job(core)

                names = [n for n, _ in seen]
                self.assertEqual(names, ["fontpack_flash_progress",
                                         "fontpack_flash_progress",
                                         "fontpack_flash_done"])
                for _n, payload in seen:
                    self.assertEqual(payload["kind"], kind)
                self.assertEqual(seen[0][1], {"pct": 10, "msg": "erasing", "kind": kind})
                self.assertEqual(seen[-1][1], {"ok": True, "msg": "ok", "kind": kind})

    def test_failure_is_reported_on_the_done_event(self):
        for name, kwargs, _noun, validator, flasher, kind in CASES:
            with self.subTest(method=name):
                core = make_core()
                seen = _events(core)
                with mock.patch("builtins.open", mock.mock_open(read_data=b"x")), \
                     mock.patch.object(poly_core.hid_fontpack, validator,
                                       return_value=(True, "")), \
                     mock.patch.object(poly_core.hid_fontpack, flasher,
                                       return_value=(False, "NACK")):
                    getattr(core, name)("f.bin", **kwargs)
                    _run_submitted_job(core)
                self.assertEqual(seen[-1], ("fontpack_flash_done",
                                            {"ok": False, "msg": "NACK", "kind": kind}))

    def test_a_set_cancel_event_is_relayed_into_the_flash_engine(self):
        """worker supersede/suspend reaches hid_fontpack through cancel_flag[0]."""
        for name, kwargs, _noun, validator, flasher, _kind in CASES:
            with self.subTest(method=name):
                core = make_core()
                captured = {}

                def _flash(*a, progress_cb=None, cancel_flag=None, **kw):
                    progress_cb(5, "starting")
                    captured["flag"] = list(cancel_flag)
                    return False, "cancelled"

                with mock.patch("builtins.open", mock.mock_open(read_data=b"x")), \
                     mock.patch.object(poly_core.hid_fontpack, validator,
                                       return_value=(True, "")), \
                     mock.patch.object(poly_core.hid_fontpack, flasher,
                                       side_effect=_flash):
                    getattr(core, name)("f.bin", **kwargs)
                    _run_submitted_job(core, cancel_set=True)
                self.assertEqual(captured["flag"], [True])

    def test_cancel_flag_stays_clear_while_the_worker_is_not_cancelling(self):
        for name, kwargs, _noun, validator, flasher, _kind in CASES:
            with self.subTest(method=name):
                core = make_core()
                captured = {}

                def _flash(*a, progress_cb=None, cancel_flag=None, **kw):
                    progress_cb(5, "starting")
                    captured["flag"] = list(cancel_flag)
                    return True, "ok"

                with mock.patch("builtins.open", mock.mock_open(read_data=b"x")), \
                     mock.patch.object(poly_core.hid_fontpack, validator,
                                       return_value=(True, "")), \
                     mock.patch.object(poly_core.hid_fontpack, flasher,
                                       side_effect=_flash):
                    getattr(core, name)("f.bin", **kwargs)
                    _run_submitted_job(core)
                self.assertEqual(captured["flag"], [False])


class TestPerEntryPointSpecifics(unittest.TestCase):
    """The parts that legitimately differ between the three."""

    def _flash(self, core, name, *args, validator, flasher, **kwargs):
        with mock.patch("builtins.open", mock.mock_open(read_data=b"x")), \
             mock.patch.object(poly_core.hid_fontpack, validator, return_value=(True, "")), \
             mock.patch.object(poly_core.hid_fontpack, flasher,
                               return_value=(True, "ok")) as f:
            getattr(core, name)(*args, **kwargs)
            _run_submitted_job(core)
        return f

    def test_fontpack_passes_the_bundle_slot_through(self):
        core = make_core()
        f = self._flash(core, "flash_fontpack", "p.plyf",
                        validator="validate_fontpack", flasher="flash_fontpack",
                        bundle_id=3)
        self.assertEqual(f.call_args.kwargs["bundle_id"], 3)

    def test_fontpack_defaults_to_slot_zero(self):
        core = make_core()
        f = self._flash(core, "flash_fontpack", "p.plyf",
                        validator="validate_fontpack", flasher="flash_fontpack")
        self.assertEqual(f.call_args.kwargs["bundle_id"], 0)

    def test_only_the_fontpack_path_counts_telemetry(self):
        """The doom easter-egg installs are not part of the census."""
        core = make_core()
        self._flash(core, "flash_fontpack", "p.plyf",
                    validator="validate_fontpack", flasher="flash_fontpack")
        core.telemetry.note.assert_called_once_with("fontpack_flashes")

        for name, validator, flasher in (
                ("install_doomwad", "validate_doomwad", "flash_doomwad"),
                ("install_doompack", "validate_doompack", "flash_doompack")):
            with self.subTest(method=name):
                core = make_core()
                self._flash(core, name, "f.bin", validator=validator, flasher=flasher)
                core.telemetry.note.assert_not_called()

    def test_doom_flashers_receive_the_file_BYTES_not_the_path(self):
        """flash_doomwad/flash_doompack take the read bytes; flash_fontpack
        re-opens the path itself. Getting this backwards flashes nonsense."""
        for name, validator, flasher in (
                ("install_doomwad", "validate_doomwad", "flash_doomwad"),
                ("install_doompack", "validate_doompack", "flash_doompack")):
            with self.subTest(method=name):
                core = make_core()
                with mock.patch("builtins.open", mock.mock_open(read_data=b"PAYLOAD")), \
                     mock.patch.object(poly_core.hid_fontpack, validator,
                                       return_value=(True, "")), \
                     mock.patch.object(poly_core.hid_fontpack, flasher,
                                       return_value=(True, "ok")) as f:
                    getattr(core, name)("f.bin")
                    _run_submitted_job(core)
                self.assertEqual(f.call_args[0][1], b"PAYLOAD")

    def test_fontpack_flasher_receives_the_path(self):
        core = make_core()
        f = self._flash(core, "flash_fontpack", "some/path.plyf",
                        validator="validate_fontpack", flasher="flash_fontpack")
        self.assertEqual(f.call_args[0][1], "some/path.plyf")

    def test_each_uses_its_own_worker_job_name(self):
        for name, validator, flasher, job in (
                ("flash_fontpack", "validate_fontpack", "flash_fontpack", "fontpack_flash"),
                ("install_doomwad", "validate_doomwad", "flash_doomwad", "doomwad_install"),
                ("install_doompack", "validate_doompack", "flash_doompack", "doompack_install")):
            with self.subTest(method=name):
                core = make_core()
                with mock.patch("builtins.open", mock.mock_open(read_data=b"x")), \
                     mock.patch.object(poly_core.hid_fontpack, validator,
                                       return_value=(True, "")), \
                     mock.patch.object(poly_core.hid_fontpack, flasher,
                                       return_value=(True, "ok")):
                    getattr(core, name)("f.bin")
                self.assertEqual(core.worker.submit.call_args[0][0], job)


class TestFlashProgressRelay(unittest.TestCase):
    """The (progress_cb, cancel_flag) pair every font-pack-transport flash uses.

    ``cancel_flag`` is a one-element LIST on purpose: the flash engines poll it
    by reference between chunks, so a plain bool could never reach them. The
    only thing that ever sets it is a progress callback observing the worker's
    cancel Event — i.e. a supersede/suspend on the HID worker. Getting this
    wrong does not fail loudly; it just makes a flash uncancellable.
    """

    def setUp(self):
        self.core = make_core()
        self.seen = _events(self.core)

    def test_returns_a_callback_and_a_single_element_flag_list(self):
        cancel = threading.Event()
        cb, flag = poly_core.flash_progress_relay(self.core.emit, cancel, "somekind")
        self.assertTrue(callable(cb))
        self.assertEqual(flag, [False])

    def test_progress_emits_a_kind_tagged_event(self):
        cb, _flag = poly_core.flash_progress_relay(self.core.emit, threading.Event(), "somekind")
        cb(33, "writing")
        self.assertEqual(self.seen, [("fontpack_flash_progress",
                                      {"pct": 33, "msg": "writing", "kind": "somekind"})])

    def test_flag_stays_clear_while_the_worker_is_not_cancelling(self):
        cb, flag = poly_core.flash_progress_relay(self.core.emit, threading.Event(), "k")
        cb(1, "a")
        cb(2, "b")
        self.assertEqual(flag, [False])

    def test_a_set_cancel_event_raises_the_flag_in_place(self):
        """In place: the engine holds a reference to this exact list."""
        cancel = threading.Event()
        cb, flag = poly_core.flash_progress_relay(self.core.emit, cancel, "k")
        same_list = flag
        cancel.set()
        cb(1, "a")
        self.assertEqual(flag, [True])
        self.assertIs(flag, same_list)

    def test_the_event_is_still_emitted_when_cancelling(self):
        """The UI must see the last progress line, not go silent mid-flash."""
        cancel = threading.Event()
        cancel.set()
        cb, _flag = poly_core.flash_progress_relay(self.core.emit, cancel, "k")
        cb(50, "half")
        self.assertEqual(self.seen[0][0], "fontpack_flash_progress")

    def test_the_flag_is_latched_once_raised(self):
        cancel = threading.Event()
        cb, flag = poly_core.flash_progress_relay(self.core.emit, cancel, "k")
        cancel.set()
        cb(1, "a")
        cancel.clear()
        cb(2, "b")
        self.assertEqual(flag, [True])


if __name__ == "__main__":
    unittest.main()
