"""Tests for the single-consumer HID worker thread (Phase B of the refactor).

Each test maps to a semantics bullet in docs/hid-worker-refactor.md. All
synchronization is via threading.Event with generous timeouts — never
time.sleep — so the suite stays deterministic and fast.
"""
import threading
import unittest

from polyhost.device.hid_worker import HidWorker, Job

# Generous upper bound for any single wait; failures here mean a real hang.
WAIT = 5.0


class WorkerTestBase(unittest.TestCase):

    def setUp(self):
        self.worker = HidWorker()
        self.worker.start()

    def tearDown(self):
        self.worker.stop(timeout=WAIT)

    def submit_and_wait(self, *args, **kwargs):
        job = self.worker.submit(*args, **kwargs)
        self.assertTrue(job.done.wait(WAIT), "job did not finish")
        return job


class TestSubmitBasics(WorkerTestBase):

    def test_submit_executes_fn_and_delivers_result_to_on_done(self):
        seen = {}
        done = threading.Event()

        def on_done(name, result):
            seen["name"] = name
            seen["result"] = result
            done.set()

        job = self.worker.submit("compute", lambda cancel: 21 * 2, on_done=on_done)
        self.assertTrue(done.wait(WAIT))
        self.assertEqual(job.result, 42)
        self.assertEqual(seen, {"name": "compute", "result": 42})

    def test_on_done_runs_on_worker_thread(self):
        box = {}
        done = threading.Event()

        def on_done(name, result):
            box["thread"] = threading.current_thread()
            done.set()

        self.worker.submit("t", lambda cancel: None, on_done=on_done)
        self.assertTrue(done.wait(WAIT))
        self.assertIsNot(box["thread"], threading.current_thread())
        self.assertEqual(box["thread"].name, "HidWorker")


class TestOrdering(WorkerTestBase):

    def test_jobs_run_fifo(self):
        order = []
        gate = threading.Event()
        started = threading.Event()

        # First job blocks on a gate so we can queue the rest deterministically.
        def first(cancel):
            started.set()
            gate.wait(WAIT)
            order.append("a")

        self.worker.submit("a", first)
        self.assertTrue(started.wait(WAIT))  # 'a' is now in flight
        self.worker.submit("b", lambda c: order.append("b"))
        last = self.worker.submit("c", lambda c: order.append("c"))
        gate.set()
        self.assertTrue(last.done.wait(WAIT))
        self.assertEqual(order, ["a", "b", "c"])

    def test_front_runs_next(self):
        order = []
        gate = threading.Event()
        started = threading.Event()

        def first(cancel):
            started.set()
            gate.wait(WAIT)
            order.append("a")

        self.worker.submit("a", first)
        self.assertTrue(started.wait(WAIT))  # 'a' is in flight; queue is empty
        self.worker.submit("b", lambda c: order.append("b"))
        last = self.worker.submit("c", lambda c: order.append("c"), front=True)
        gate.set()
        self.assertTrue(last.done.wait(WAIT))
        # c jumped ahead of b
        self.assertEqual(order, ["a", "c", "b"])


class TestCoalescing(WorkerTestBase):

    def test_queued_duplicates_dropped_without_on_done(self):
        on_done_calls = []
        gate = threading.Event()

        # Block the worker so duplicates pile up in the queue.
        self.worker.submit("blocker", lambda c: gate.wait(WAIT))

        dropped = self.worker.submit(
            "ov", lambda c: "first", coalesce_key="ov",
            on_done=lambda n, r: on_done_calls.append("first"))
        survivor = self.worker.submit(
            "ov", lambda c: "second", coalesce_key="ov",
            on_done=lambda n, r: on_done_calls.append("second"))

        # The dropped job's events are set, but its on_done is never called.
        self.assertTrue(dropped.done.wait(WAIT))
        self.assertTrue(dropped.cancel.is_set())
        gate.set()
        self.assertTrue(survivor.done.wait(WAIT))
        self.assertEqual(survivor.result, "second")
        self.assertEqual(on_done_calls, ["second"])

    def test_inflight_duplicate_is_cancelled(self):
        started = threading.Event()
        release = threading.Event()
        cancel_seen = {}

        def long_job(cancel):
            started.set()
            release.wait(WAIT)              # held until a duplicate arrives
            cancel_seen["was_set"] = cancel.is_set()
            return cancel.is_set()

        inflight = self.worker.submit("ov", long_job, coalesce_key="ov")
        self.assertTrue(started.wait(WAIT))

        # New job with same key cancels the in-flight one and queues itself.
        survivor = self.worker.submit("ov", lambda c: "new", coalesce_key="ov")
        # Let the in-flight job observe its cancel and return.
        release.set()
        self.assertTrue(inflight.done.wait(WAIT))
        self.assertTrue(cancel_seen["was_set"])
        self.assertIs(inflight.result, True)

        # The new job still took its normal place and ran.
        self.assertTrue(survivor.done.wait(WAIT))
        self.assertEqual(survivor.result, "new")


class TestRunSync(WorkerTestBase):

    def test_happy_path_returns_value(self):
        self.assertEqual(self.worker.run_sync("calc", lambda c: 7 + 5), 12)

    def test_exception_propagates_to_caller(self):
        def boom(cancel):
            raise ValueError("nope")

        with self.assertRaises(ValueError) as ctx:
            self.worker.run_sync("boom", boom)
        self.assertEqual(str(ctx.exception), "nope")

    def test_timeout_raises_and_sets_cancel(self):
        gate = threading.Event()
        captured = {}

        def slow(cancel):
            captured["cancel"] = cancel
            gate.wait(WAIT)               # outlives the run_sync timeout

        with self.assertRaises(TimeoutError):
            self.worker.run_sync("slow", slow, timeout=0.05)
        # The job's cancel event was set on timeout.
        self.assertTrue(captured["cancel"].wait(WAIT))
        gate.set()

    def test_run_sync_while_suspended_raises_runtime_error(self):
        self.worker.suspend()
        try:
            with self.assertRaises(RuntimeError):
                self.worker.run_sync("x", lambda c: 1)
        finally:
            self.worker.resume()


class TestPeriodic(WorkerTestBase):

    def test_periodic_fires_repeatedly(self):
        count = {"n": 0}
        reached = threading.Event()

        def tick(cancel):
            count["n"] += 1
            if count["n"] >= 3:
                reached.set()

        self.worker.add_periodic("tick", 0.02, tick)
        self.assertTrue(reached.wait(WAIT))
        self.assertGreaterEqual(count["n"], 3)

    def test_periodic_does_not_fire_while_suspended_and_resumes(self):
        ran = threading.Event()
        # Use a flag we can reset to detect runs across the suspend window.
        runs = []

        def tick(cancel):
            runs.append(1)
            ran.set()

        self.worker.add_periodic("tick", 0.02, tick)
        self.assertTrue(ran.wait(WAIT))   # confirm it runs at all

        self.worker.suspend()
        before = len(runs)
        ran.clear()
        # Bounded wait spanning several 0.02 s intervals: the periodic must
        # NOT fire while suspended.
        self.assertFalse(ran.wait(0.15), "periodic fired while suspended")
        self.assertEqual(len(runs), before)
        # Resume and confirm periodics fire again.
        self.worker.resume()
        self.assertTrue(ran.wait(WAIT))
        self.assertGreater(len(runs), before)

    def test_periodic_runs_between_queued_jobs(self):
        # A busy queue must not starve periodics: they run between jobs, not
        # only when the worker goes idle. order is appended exclusively on the
        # worker thread (periodics and jobs alike), so it needs no lock.
        order = []
        done = threading.Event()
        self.worker.add_periodic("tick", 0.01, lambda c: order.append("tick"))

        def busy_job(cancel):
            order.append("job")
            cancel.wait(0.03)   # each job outlasts the periodic interval

        for _ in range(4):
            self.worker.submit("busy", busy_job)
        self.worker.submit("last", lambda c: done.set())
        self.assertTrue(done.wait(WAIT))
        # The queue never drained during the burst, so a tick before the
        # final busy job proves periodics run between jobs, not only on idle.
        last_job_idx = max(i for i, e in enumerate(order) if e == "job")
        self.assertIn("tick", order[:last_job_idx],
                      "periodic starved while the queue stayed busy")

    def test_periodic_cancel_event_set_on_suspend_cleared_on_resume(self):
        seen = []
        observed = threading.Event()

        def tick(cancel):
            seen.append(cancel.is_set())
            observed.set()

        self.worker.add_periodic("tick", 0.02, tick)
        self.assertTrue(observed.wait(WAIT))   # ran at least once (cancel clear)
        self.assertIn(False, seen)             # saw a not-cancelled invocation

        # Suspend sets the periodic's cancel event even though it won't run.
        self.worker.suspend()
        self.assertTrue(self.worker._periodics[0].cancel.is_set())

        # Resume clears it and the task fires again uncancelled.
        observed.clear()
        seen.clear()
        self.worker.resume()
        self.assertFalse(self.worker._periodics[0].cancel.is_set())
        self.assertTrue(observed.wait(WAIT))
        self.assertIn(False, seen)

    def test_periodic_exception_keeps_schedule(self):
        count = {"n": 0}
        reached = threading.Event()

        def tick(cancel):
            count["n"] += 1
            if count["n"] >= 3:
                reached.set()
            raise RuntimeError("periodic boom")

        self.worker.add_periodic("tick", 0.02, tick)
        # Despite raising every time, it keeps firing.
        self.assertTrue(reached.wait(WAIT))


class TestExclusive(WorkerTestBase):

    def test_inflight_cancelled_and_finished_before_body(self):
        started = threading.Event()
        release = threading.Event()
        order = []

        def long_job(cancel):
            started.set()
            # Honor cancellation promptly once exclusive sets it.
            cancel.wait(WAIT)
            order.append("inflight-finished")

        self.worker.submit("ov", long_job)
        self.assertTrue(started.wait(WAIT))

        with self.worker.exclusive():
            order.append("in-body")
        # The in-flight job must have finished before the with-body ran.
        self.assertEqual(order, ["inflight-finished", "in-body"])
        release.set()

    def test_jobs_submitted_during_exclusive_run_after_exit(self):
        ran = threading.Event()
        with self.worker.exclusive():
            job = self.worker.submit("later", lambda c: ran.set())
            # Should not have run yet (suspended). We can't prove a negative
            # with sleeps, but done should still be unset right here.
            self.assertFalse(job.done.is_set())
        # After exit, it runs.
        self.assertTrue(ran.wait(WAIT))
        self.assertTrue(job.done.wait(WAIT))

    def test_exclusive_preserves_prior_suspend_state(self):
        # A worker the user already suspended (tray pause) must stay suspended
        # after an exclusive section (e.g. a firmware flash) exits.
        self.worker.suspend()
        with self.worker.exclusive():
            pass
        job = self.worker.submit("while_suspended", lambda c: None)
        self.assertFalse(job.done.wait(0.2))   # still suspended: job must not run
        self.worker.resume()
        self.assertTrue(job.done.wait(WAIT))   # resumes normally afterwards


class TestExceptionSafety(WorkerTestBase):

    def test_job_exception_does_not_kill_worker(self):
        results = {}

        def boom(cancel):
            raise ValueError("kaboom")

        bad = self.worker.submit(
            "bad", boom, on_done=lambda n, r: results.__setitem__("bad", r))
        self.assertTrue(bad.done.wait(WAIT))
        self.assertIsInstance(bad.result, ValueError)
        self.assertIsInstance(results["bad"], ValueError)

        # Next job still runs on the same worker thread.
        good = self.submit_and_wait("good", lambda c: 99)
        self.assertEqual(good.result, 99)

    def test_on_done_exception_does_not_kill_worker(self):
        def bad_on_done(name, result):
            raise RuntimeError("on_done boom")

        first = self.worker.submit("a", lambda c: 1, on_done=bad_on_done)
        self.assertTrue(first.done.wait(WAIT))
        good = self.submit_and_wait("b", lambda c: 2)
        self.assertEqual(good.result, 2)


class TestStop(unittest.TestCase):

    def test_stop_joins_promptly_with_long_cancellable_job(self):
        worker = HidWorker()
        worker.start()
        started = threading.Event()

        def long_job(cancel):
            started.set()
            cancel.wait(WAIT)   # respects cancellation
            return "done"

        worker.submit("long", long_job)
        self.assertTrue(started.wait(WAIT))
        worker.stop(timeout=WAIT)
        self.assertFalse(worker._thread.is_alive())

    def test_double_stop_is_idempotent(self):
        worker = HidWorker()
        worker.start()
        worker.stop(timeout=WAIT)
        worker.stop(timeout=WAIT)  # must not raise
        self.assertFalse(worker._thread.is_alive())

    def test_cannot_restart_after_stop(self):
        worker = HidWorker()
        worker.start()
        worker.stop(timeout=WAIT)
        with self.assertRaises(RuntimeError):
            worker.start()

    def test_submit_after_stop_does_not_run(self):
        worker = HidWorker()
        worker.start()
        worker.stop(timeout=WAIT)
        ran = []
        job = worker.submit("x", lambda c: ran.append(1))
        # Worker is gone; job is signalled complete without running.
        self.assertTrue(job.done.wait(WAIT))
        self.assertTrue(job.cancel.is_set())
        self.assertEqual(ran, [])


class TestJobRepr(unittest.TestCase):

    def test_repr_contains_name_and_key(self):
        job = Job("ov", lambda c: None, coalesce_key="overlay")
        self.assertIn("ov", repr(job))
        self.assertIn("overlay", repr(job))


if __name__ == "__main__":
    unittest.main()
