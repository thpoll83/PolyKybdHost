"""The Binary Ninja plugin's Qt-free core (binaryninja-plugin/polykybd_mode_reporter/core.py)."""
import contextlib
import enum
import io
import importlib.util
import json
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from polyhost.handler.browser_url import DEFAULT_MAX_AGE_S
from polyhost.server.browser_report_server import DEFAULT_BROWSER_REPORT_PORT

_CORE = (Path(__file__).resolve().parents[2] / "binaryninja-plugin"
         / "polykybd_mode_reporter" / "core.py")
_spec = importlib.util.spec_from_file_location("polykybd_binja_core", _CORE)
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)


class FunctionGraphType(enum.IntEnum):
    """The shape of binaryninja.enums.FunctionGraphType (binaryninjacore.h)."""
    NormalFunctionGraph = 0
    LowLevelILFunctionGraph = 1
    LiftedILFunctionGraph = 2
    LowLevelILSSAFormFunctionGraph = 3
    MediumLevelILFunctionGraph = 4
    MediumLevelILSSAFormFunctionGraph = 5
    MappedMediumLevelILFunctionGraph = 6
    MappedMediumLevelILSSAFormFunctionGraph = 7
    HighLevelILFunctionGraph = 8
    HighLevelILSSAFormFunctionGraph = 9
    HighLevelLanguageRepresentationFunctionGraph = 10


def _fvt(view_type, name=None):
    """The shape of binaryninja.function.FunctionViewType."""
    return SimpleNamespace(view_type=view_type, name=name)


class ViewTokenTest(unittest.TestCase):
    def test_known_views(self):
        self.assertEqual(core.view_token("Linear:ELF"), "linear")
        self.assertEqual(core.view_token("Graph:PE"), "graph")
        self.assertEqual(core.view_token("Hex:Raw"), "hex")
        self.assertEqual(core.view_token("Bytes:Mach-O"), "bytes")
        self.assertEqual(core.view_token("Triage:ELF"), "triage")

    def test_other_views_send_no_name(self):
        # A plugin's own view type name is not sent.
        self.assertEqual(core.view_token("Linear MLIL:ELF"), "other")
        self.assertEqual(core.view_token("My Secret View:Raw"), "other")

    def test_no_view(self):
        self.assertIsNone(core.view_token(None))
        self.assertIsNone(core.view_token(""))


class IlTokenTest(unittest.TestCase):
    def test_every_graph_type(self):
        want = ["disasm", "llil", "lifted", "llil_ssa", "mlil", "mlil_ssa", "mapped_mlil",
                "mapped_mlil_ssa", "hlil", "hlil_ssa", "pseudo_c"]
        for t, w in zip(FunctionGraphType, want):
            self.assertEqual(core.il_token(_fvt(t)), w, t)
            self.assertEqual(core.il_token(t), w, t)
            self.assertEqual(core.il_token(int(t)), w, t)

    def test_core_struct_shape(self):
        self.assertEqual(core.il_token(SimpleNamespace(type=8, name=None)), "hlil")

    def test_pseudo_languages(self):
        hlr = FunctionGraphType.HighLevelLanguageRepresentationFunctionGraph
        self.assertEqual(core.il_token(_fvt(hlr, "Pseudo C")), "pseudo_c")
        self.assertEqual(core.il_token(_fvt(hlr, "Pseudo Rust")), "pseudo_rust")
        self.assertEqual(core.il_token(_fvt(hlr, "Pseudo Python")), "pseudo_python")
        # A third-party language's name is not sent.
        self.assertEqual(core.il_token(_fvt(hlr, "Pseudo Secret")), "pseudo")

    def test_unknown_is_none(self):
        self.assertIsNone(core.il_token(None))
        self.assertIsNone(core.il_token(-1))
        self.assertIsNone(core.il_token(42))
        self.assertIsNone(core.il_token(True))


class ContextUrlTest(unittest.TestCase):
    def test_il_only_for_code_views(self):
        hlil = FunctionGraphType.HighLevelILFunctionGraph
        self.assertEqual(core.context_url("Graph:ELF", _fvt(hlil)), "binaryninja://graph/hlil")
        self.assertEqual(core.context_url("Linear:PE", _fvt(0)), "binaryninja://linear/disasm")
        self.assertEqual(core.context_url("Hex:Raw", _fvt(hlil)), "binaryninja://hex")
        self.assertEqual(core.context_url("Linear:PE", None), "binaryninja://linear")

    def test_no_view_sends_nothing(self):
        self.assertIsNone(core.context_url(None, None))

    def test_url_holds_only_known_tokens(self):
        url = core.context_url("Custom:/home/me/secret.bin", _fvt(4))
        self.assertEqual(url, "binaryninja://other")


class SendPolicyTest(unittest.TestCase):
    def test_change_and_keepalive(self):
        p = core.SendPolicy(keepalive_s=3.0)
        self.assertTrue(p.due("u1", 0.0))
        p.sent("u1", 0.0)
        self.assertFalse(p.due("u1", 2.9))
        self.assertTrue(p.due("u2", 1.0))
        self.assertTrue(p.due("u1", 3.0))
        self.assertFalse(p.due(None, 99.0))

    def test_keepalive_keeps_the_host_report_fresh(self):
        self.assertLess(core.KEEPALIVE_S * 2, DEFAULT_MAX_AGE_S)

    def test_default_port_is_the_hosts(self):
        self.assertEqual(core.DEFAULT_PORT, DEFAULT_BROWSER_REPORT_PORT)


class PayloadTest(unittest.TestCase):
    def test_carries_the_view_only(self):
        body = json.loads(core.payload("binaryninja://hex"))
        self.assertEqual(body, {"app": "binaryninja", "url": "binaryninja://hex",
                                "focused": True})
        self.assertEqual(json.loads(core.payload("u", "t"))["token"], "t")
        body = json.loads(core.payload("u", pid=7, input_age=1.234))
        self.assertEqual((body["pid"], body["input_age"]), (7, 1.2))

    def test_withdrawal_is_an_unfocused_report_without_url(self):
        body = json.loads(core.payload(None, pid=7, focused=False))
        self.assertEqual((body["url"], body["focused"], body["pid"]), (None, False, 7))


class SenderTest(unittest.TestCase):
    def test_submit_never_blocks_and_latest_wins(self):
        gate, got = threading.Event(), []

        def slow_post(port, body):
            gate.wait(2)
            got.append(json.loads(body)["url"])

        s = core.Sender(post=slow_post)
        t0 = time.monotonic()
        for i in range(5):
            s.submit(50164, f"binaryninja://u{i}")
        self.assertLess(time.monotonic() - t0, 0.1)
        gate.set()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and (not got or got[-1] != "binaryninja://u4"):
            time.sleep(0.01)
        s.stop()
        self.assertEqual(got[-1], "binaryninja://u4")
        self.assertLessEqual(len(got), 2)

    def test_stop_waits_for_the_withdrawal(self):
        got = []
        s = core.Sender(post=lambda port, body: got.append(json.loads(body)["focused"]))
        s.submit(1, None, focused=False)
        s.stop(wait_s=2)
        self.assertFalse(s._thread.is_alive())
        self.assertEqual(got, [False])

    def test_a_failing_post_does_not_kill_the_thread(self):
        posted = threading.Semaphore(0)

        def boom(port, body):
            posted.release()
            raise OSError("refused")

        with contextlib.redirect_stderr(io.StringIO()):
            s = core.Sender(post=boom)
            s.submit(1, "a")
            self.assertTrue(posted.acquire(timeout=2))
            s.submit(1, "b")
            self.assertTrue(posted.acquire(timeout=2))
            s.stop()


if __name__ == "__main__":
    unittest.main()
