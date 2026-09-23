"""The Windows UIA backend's COM lifecycle, driven through fakes.

There is no Windows here, so comtypes and the two ole32 calls are faked. What
is pinned is the lifecycle that crashed the daemon in the field (2026-09-23):
the harvest thread exits after 30 s idle and a new one replaces it, and a
module-global IUIAutomation handed the first thread's COM object to every
later thread, which never initialized COM at all. The rules:

* each thread initializes COM and builds its OWN automation object;
* `release_thread()` drops the object BEFORE it leaves the apartment;
* it leaves only an apartment it entered (S_OK / S_FALSE), exactly once;
* on the thread whose `import comtypes` initialized COM, that import is the
  initialization -- a second CoInitializeEx there would never be undone.
"""

import sys
import threading
import types
import unittest
import weakref
from unittest.mock import patch

from polyhost.services import shortcut_source as ss
from polyhost.services.shortcut_source import uia


class _Automation:
    """Stands in for the IUIAutomation pointer; weak-referenceable."""


def _fake_comtypes(created):
    comtypes = types.ModuleType("comtypes")
    client = types.ModuleType("comtypes.client")
    client.GetModule = lambda _name: types.SimpleNamespace(IUIAutomation=object)

    def create(_clsid, interface=None):
        obj = _Automation()
        created.append(weakref.ref(obj))
        return obj

    client.CreateObject = create
    comtypes.client = client
    return {"comtypes": comtypes, "comtypes.client": client}


def on_thread(fn):
    """Run fn on a fresh thread and return its result (or raise its error)."""
    out = {}

    def run():
        try:
            out["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 -- re-raised below
            out["error"] = exc

    t = threading.Thread(target=run)
    t.start()
    t.join(5)
    if "error" in out:
        raise out["error"]
    return out.get("value")


class UiaThreadLifecycleTest(unittest.TestCase):

    def setUp(self):
        uia._local = threading.local()
        self.created = []
        self.calls = []
        modules = patch.dict(sys.modules, _fake_comtypes(self.created))
        modules.start()
        self.addCleanup(modules.stop)
        self.loaded = True
        for name, fn in (
                ("_comtypes_loaded", lambda: self.loaded),
                ("_co_initialize", self._init),
                ("_co_uninitialize", self._uninit)):
            p = patch.object(uia, name, side_effect=fn)
            p.start()
            self.addCleanup(p.stop)
        self.init_result = True

    def _init(self):
        self.calls.append("init")
        return self.init_result

    def _uninit(self):
        # The object must already be gone: releasing it after this point is
        # a call into a torn-down apartment.
        alive = [ref for ref in self.created if ref() is not None]
        self.calls.append("uninit(alive=%d)" % len(alive))

    def test_each_thread_builds_its_OWN_automation_object(self):
        first = on_thread(lambda: id(uia._uia()[1]))
        second = on_thread(lambda: id(uia._uia()[1]))
        self.assertEqual(len(self.created), 2)
        self.assertEqual(self.calls, ["init", "init"])
        del first, second

    def test_the_object_is_cached_within_one_thread(self):
        same = on_thread(lambda: uia._uia()[1] is uia._uia()[1])
        self.assertTrue(same)
        self.assertEqual(len(self.created), 1)

    def test_release_drops_the_object_BEFORE_leaving_the_apartment(self):
        def use_then_release():
            uia._uia()
            uia.release_thread()
        on_thread(use_then_release)
        self.assertEqual(self.calls, ["init", "uninit(alive=0)"])

    def test_release_leaves_only_an_apartment_it_entered(self):
        """RPC_E_CHANGED_MODE took no reference, so there is none to drop."""
        self.init_result = False

        def use_then_release():
            uia._uia()
            uia.release_thread()
        on_thread(use_then_release)
        self.assertEqual(self.calls, ["init"])

    def test_the_importing_thread_owns_the_import_time_initialization(self):
        """comtypes calls CoInitializeEx when first imported; calling it again
        on that thread would take a reference nothing ever drops."""
        self.loaded = False

        def use_then_release():
            uia._uia()
            uia.release_thread()
        on_thread(use_then_release)
        self.assertEqual(self.calls, ["uninit(alive=0)"])

    def test_release_twice_leaves_the_apartment_once(self):
        def use_then_release_twice():
            uia._uia()
            uia.release_thread()
            uia.release_thread()
        on_thread(use_then_release_twice)
        self.assertEqual(self.calls, ["init", "uninit(alive=0)"])

    def test_release_on_a_thread_that_never_used_it_does_nothing(self):
        on_thread(uia.release_thread)
        self.assertEqual(self.calls, [])

    def test_a_thread_can_use_it_again_after_releasing(self):
        def twice():
            uia._uia()
            uia.release_thread()
            uia._uia()
            uia.release_thread()
        on_thread(twice)
        self.assertEqual(self.calls, ["init", "uninit(alive=0)",
                                      "init", "uninit(alive=0)"])

    def test_release_never_raises(self):
        def use_then_release():
            uia._uia()
            with patch.object(uia, "_co_uninitialize",
                              side_effect=OSError("boom")):
                uia.release_thread()
        on_thread(use_then_release)     # must not raise


class ReleaseDispatchTest(unittest.TestCase):
    """`shortcut_source.release_thread()` is what the fetcher thread calls."""

    def test_it_reaches_the_active_backend(self):
        backend = types.SimpleNamespace(calls=[])
        backend.release_thread = lambda: backend.calls.append(1)
        with patch.object(ss, "backend_name", return_value="uia"), \
             patch.dict(sys.modules,
                        {"polyhost.services.shortcut_source.uia": backend}):
            ss.release_thread()
        self.assertEqual(backend.calls, [1])

    def test_a_backend_never_imported_is_not_imported_to_release_it(self):
        name = "polyhost.services.shortcut_source.atspi"
        saved = sys.modules.pop(name, None)
        try:
            with patch.object(ss, "backend_name", return_value="atspi"):
                ss.release_thread()
            self.assertNotIn(name, sys.modules)
        finally:
            if saved is not None:
                sys.modules[name] = saved

    def test_a_backend_without_the_hook_is_fine(self):
        with patch.object(ss, "backend_name", return_value="uia"), \
             patch.dict(sys.modules, {"polyhost.services.shortcut_source.uia":
                                      types.SimpleNamespace()}):
            ss.release_thread()         # must not raise

    def test_a_failing_release_never_raises(self):
        def boom():
            raise RuntimeError("boom")
        backend = types.SimpleNamespace(release_thread=boom)
        with patch.object(ss, "backend_name", return_value="uia"), \
             patch.dict(sys.modules,
                        {"polyhost.services.shortcut_source.uia": backend}):
            ss.release_thread()         # must not raise


if __name__ == "__main__":
    unittest.main()
