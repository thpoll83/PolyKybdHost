"""PolyCore's hardware-ID reads for the telemetry ping (cmd 50, protocol v37).

Pins what the review of PolyKybdHost#987 found: a new connection never reports
the previous keyboard's IDs, a read for an earlier connection cannot fill the
cache, safe mode sends no cmd 50, a failed read is retried a bounded number of
times, a missing other half is read again when GET_ID's counter moves, and the
emulated primary sends no IDs.
"""
import logging
import threading
import unittest
from unittest import mock

from polyhost.core.poly_core import PolyCore

A = {"own": "e66038b7c32f5a2c", "other": "e66038b7c3284d26"}


def make_core(*, supports=True, safe_mode=False):
    core = PolyCore.__new__(PolyCore)
    core.log = logging.getLogger("test.polycore.hwid")
    core.connected, core.safe_mode, core.paused = True, safe_mode, False
    core.worker = mock.MagicMock()
    core.keeb = mock.MagicMock()
    core.keeb.supports.return_value = supports
    core.keeb.state_generation = 5
    core.keeb.get_hw_ids.return_value = (True, dict(A))
    core.get_status = lambda: {"connected": True}
    core._mock_primary = False
    core._start_hw_id_reads()
    return core


def run_jobs(core):
    """Run every job handed to worker.submit since the last call, as the worker would."""
    calls = list(core.worker.submit.call_args_list)
    core.worker.submit.reset_mock()
    for call in calls:
        call.args[1](threading.Event())
    return len(calls)


class HwIdCoreTest(unittest.TestCase):
    def test_a_connect_reads_once_and_the_snapshot_sends_both(self):
        core = make_core()
        core._submit_hw_id_read()
        self.assertEqual(run_jobs(core), 1)
        status, _ = core._telemetry_snapshot()
        self.assertEqual(status["hw_ids"], [A["own"], A["other"]])

    def test_a_new_connection_forgets_the_previous_keyboard(self):
        core = make_core()
        core._submit_hw_id_read()
        run_jobs(core)
        core._start_hw_id_reads()
        self.assertEqual(core._telemetry_snapshot()[0]["hw_ids"], [])

    def test_a_read_for_an_earlier_connection_is_dropped(self):
        core = make_core()
        core._submit_hw_id_read()
        core._start_hw_id_reads()           # another keyboard before the job ran
        run_jobs(core)
        self.assertIsNone(core._hw_ids)

    def test_a_connect_during_the_read_drops_its_result(self):
        core = make_core()

        def read_then_reconnect():
            core._start_hw_id_reads()       # the probe thread sees a new keyboard
            return True, dict(A)
        core.keeb.get_hw_ids.side_effect = read_then_reconnect
        core._submit_hw_id_read()
        run_jobs(core)
        self.assertIsNone(core._hw_ids)

    def test_safe_mode_sends_no_cmd_50(self):
        core = make_core(safe_mode=True)
        core._submit_hw_id_read()
        self.assertEqual(run_jobs(core), 0)
        core = make_core()
        core._submit_hw_id_read()
        core.safe_mode = True               # changed between submit and run
        run_jobs(core)
        core.keeb.get_hw_ids.assert_not_called()

    def test_old_firmware_is_not_asked(self):
        core = make_core(supports=False)
        core._submit_hw_id_read()
        self.assertEqual(run_jobs(core), 0)

    def test_a_failed_read_is_retried_a_bounded_number_of_times(self):
        core = make_core()
        core.keeb.get_hw_ids.return_value = (False, "timeout")
        core._submit_hw_id_read()
        reads = run_jobs(core)
        for _ in range(10):
            core._recheck_hw_ids(steady=True)
            reads += run_jobs(core)
        self.assertEqual(reads, PolyCore.HW_ID_READS_PER_CONNECTION)

    def test_no_second_read_while_one_is_queued(self):
        core = make_core()
        core._submit_hw_id_read()
        core._recheck_hw_ids(steady=True)
        self.assertEqual(core.worker.submit.call_count, 1)

    def test_a_missing_other_half_is_read_when_the_counter_moves(self):
        core = make_core()
        core.keeb.get_hw_ids.return_value = (True, {"own": A["own"], "other": None})
        core._submit_hw_id_read()
        run_jobs(core)
        core._recheck_hw_ids(steady=True)               # counter did not move
        self.assertEqual(run_jobs(core), 0)
        core.keeb.get_hw_ids.return_value = (True, dict(A))
        core.keeb.state_generation = 6                  # the slave linked up
        core._recheck_hw_ids(steady=True)
        self.assertEqual(run_jobs(core), 1)
        self.assertEqual(core._telemetry_snapshot()[0]["hw_ids"], [A["own"], A["other"]])

    def test_complete_ids_are_not_read_again(self):
        core = make_core()
        core._submit_hw_id_read()
        run_jobs(core)
        core.keeb.state_generation = 9
        core._recheck_hw_ids(steady=True)
        self.assertEqual(run_jobs(core), 0)

    def test_the_emulated_primary_sends_no_ids(self):
        core = make_core()
        core._submit_hw_id_read()
        run_jobs(core)
        core._mock_primary = True
        self.assertEqual(core._telemetry_snapshot()[0]["hw_ids"], [])


if __name__ == "__main__":
    unittest.main()
