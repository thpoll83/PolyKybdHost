"""Observable — the subscribe/emit seam PolyCore and RemoteCore both expose.

Both classes carried an identical copy of this (an ``_observers`` list, a lock,
a snapshot-then-fire ``emit`` with a per-observer exception guard). The guard is
the part worth pinning: it is what stops one broken GUI observer from killing
the core's worker thread mid-event, and it is exactly the sort of detail that
gets dropped when a second copy is written by hand.
"""
import threading
import unittest

from polyhost.util.observable import Observable


class FakeLog:
    def __init__(self):
        self.exceptions = []

    def exception(self, fmt, *a):
        self.exceptions.append(fmt % a if a else fmt)


class TestObservable(unittest.TestCase):

    def setUp(self):
        self.log = FakeLog()
        self.obs = Observable(self.log)

    def test_emit_with_no_observers_is_a_no_op(self):
        self.obs.emit("evt", {"a": 1})

    def test_subscriber_receives_name_and_payload(self):
        seen = []
        self.obs.subscribe(lambda n, p: seen.append((n, p)))
        self.obs.emit("status_changed", {"connected": True})
        self.assertEqual(seen, [("status_changed", {"connected": True})])

    def test_every_subscriber_is_called_in_registration_order(self):
        order = []
        self.obs.subscribe(lambda n, p: order.append("first"))
        self.obs.subscribe(lambda n, p: order.append("second"))
        self.obs.emit("e", None)
        self.assertEqual(order, ["first", "second"])

    def test_a_raising_observer_does_not_stop_the_others(self):
        seen = []

        def boom(name, payload):
            raise RuntimeError("observer is broken")

        self.obs.subscribe(boom)
        self.obs.subscribe(lambda n, p: seen.append(n))
        self.obs.emit("e", None)
        self.assertEqual(seen, ["e"])
        self.assertEqual(len(self.log.exceptions), 1)

    def test_a_raising_observer_is_logged_with_the_event_name(self):
        self.obs.subscribe(lambda n, p: 1 / 0)
        self.obs.emit("fw_flash_done", None)
        self.assertIn("fw_flash_done", self.log.exceptions[0])

    def test_a_raising_observer_stays_subscribed(self):
        calls = []

        def boom(name, payload):
            calls.append(name)
            raise RuntimeError("still broken")

        self.obs.subscribe(boom)
        self.obs.emit("a", None)
        self.obs.emit("b", None)
        self.assertEqual(calls, ["a", "b"])

    def test_subscribing_during_an_emit_does_not_deadlock_or_mutate_mid_fire(self):
        """emit() snapshots under the lock, then fires outside it — an observer
        that subscribes another observer must not blow up the iteration."""
        seen = []

        def adder(name, payload):
            self.obs.subscribe(lambda n, p: seen.append("late"))
            seen.append("adder")

        self.obs.subscribe(adder)
        self.obs.emit("e", None)
        self.assertEqual(seen, ["adder"])       # the late one is not fired now
        self.obs.emit("e", None)
        self.assertEqual(seen, ["adder", "adder", "late"])

    def test_concurrent_subscribe_and_emit_is_safe(self):
        errors = []

        def subscriber_thread():
            try:
                for _ in range(200):
                    self.obs.subscribe(lambda n, p: None)
            except Exception as e:  # pragma: no cover
                errors.append(e)

        def emitter_thread():
            try:
                for _ in range(200):
                    self.obs.emit("e", None)
            except Exception as e:  # pragma: no cover
                errors.append(e)

        threads = [threading.Thread(target=subscriber_thread),
                   threading.Thread(target=emitter_thread)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        # join(timeout=) returns silently on timeout, so without this a deadlock
        # (emit firing observers while holding the lock) would still pass.
        for t in threads:
            self.assertFalse(t.is_alive(),
                             "subscribe/emit blocked — lock held during fire")
        self.assertEqual(errors, [])


class TestCoresUseIt(unittest.TestCase):
    """Both cores must keep the same observer contract after the extraction."""

    def test_poly_core_exposes_subscribe_and_emit(self):
        from polyhost.core.poly_core import PolyCore
        self.assertTrue(callable(PolyCore.subscribe))
        self.assertTrue(callable(PolyCore.emit))

    def test_remote_core_exposes_subscribe_and_emit(self):
        from polyhost.client.remote_core import RemoteCore
        self.assertTrue(callable(RemoteCore.subscribe))
        self.assertTrue(callable(RemoteCore.emit))

    def test_remote_core_emit_guards_a_broken_observer(self):
        """RemoteCore fans daemon events out to Qt slots — one that raises must
        not kill the event-pump thread and strand the tray."""
        from polyhost.client.remote_core import RemoteCore
        rc = RemoteCore.__new__(RemoteCore)
        Observable.__init__(rc, FakeLog())
        seen = []
        rc.subscribe(lambda n, p: 1 / 0)
        rc.subscribe(lambda n, p: seen.append(n))
        rc.emit("status_changed", {})
        self.assertEqual(seen, ["status_changed"])


if __name__ == "__main__":
    unittest.main()
