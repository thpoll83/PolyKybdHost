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


class _Meta:
    """A Qt meta-object: className() and superClass()."""

    def __init__(self, *names):
        self._names = names

    def className(self):  # noqa: N802 -- Qt API name
        return self._names[0]

    def superClass(self):  # noqa: N802 -- Qt API name
        return _Meta(*self._names[1:]) if len(self._names) > 1 else None


class _Widget:
    """A focused widget: its meta-object chain and its parent."""

    def __init__(self, names, parent=None):
        self._meta = _Meta(*names)
        self._parent = parent

    def metaObject(self):  # noqa: N802 -- Qt API name
        return self._meta

    def parentWidget(self):  # noqa: N802 -- Qt API name
        return self._parent


def _chain(*levels):
    """The focus widget first, then its parents up to the window."""
    w = None
    for names in reversed(levels):
        w = _Widget(names, w)
    return w


_WINDOW = ("MainWindow", "QMainWindow", "QWidget", "QObject")
_FRAME = ("ViewFrame", "QWidget", "QObject")


class FocusUrlTest(unittest.TestCase):
    def test_console_command_line(self):
        w = _chain(("ScriptingConsoleEdit", "QTextEdit", "QWidget", "QObject"),
                   ("Splitter", "QSplitter", "QWidget", "QObject"),
                   ("ScriptingConsole", "SidebarWidget", "QWidget", "QObject"),
                   ("GlobalArea", "QWidget", "QObject"), _WINDOW)
        self.assertEqual(core.focus_url(w), "binaryninja://console")

    def test_console_viewport_child(self):
        # Qt gives the focus to the edit; a child under it still counts.
        w = _chain(("QWidget", "QObject"),
                   ("ScriptingConsoleEdit", "QTextEdit", "QWidget", "QObject"), _WINDOW)
        self.assertEqual(core.focus_url(w), "binaryninja://console")

    def test_console_subclass_by_meta_chain(self):
        w = _chain(("MyConsoleEdit", "ScriptingConsoleEdit", "QTextEdit", "QObject"))
        self.assertEqual(core.focus_url(w), "binaryninja://console")

    def test_console_output_is_not_the_command_line(self):
        w = _chain(("ScriptingConsoleOutput", "QPlainTextEdit", "QWidget", "QObject"),
                   ("ScriptingConsole", "SidebarWidget", "QWidget", "QObject"), _WINDOW)
        self.assertIsNone(core.focus_url(w))

    def test_xrefs_tree_table_and_filter(self):
        pane = ("CrossReferenceWidget", "SidebarWidget", "QWidget", "QObject")
        for inner in (("CrossReferenceTree", "QTreeView", "QWidget", "QObject"),
                      ("CrossReferenceTable", "QTableView", "QWidget", "QObject"),
                      ("QLineEdit", "QWidget", "QObject")):
            w = _chain(inner, ("ExpandableGroup", "QWidget", "QObject"), pane, _WINDOW)
            self.assertEqual(core.focus_url(w), "binaryninja://xrefs", inner[0])

    def test_code_view_and_no_focus(self):
        w = _chain(("LinearView", "QAbstractScrollArea", "QWidget", "QObject"), _FRAME, _WINDOW)
        self.assertIsNone(core.focus_url(w))
        self.assertIsNone(core.focus_url(None))

    def test_nearest_match_decides(self):
        # A console edit inside an xrefs pane (not a real layout): the nearer wins.
        w = _chain(("ScriptingConsoleEdit", "QTextEdit"),
                   ("CrossReferenceWidget", "SidebarWidget"))
        self.assertEqual(core.focus_url(w), "binaryninja://console")

    def test_python_type_names_without_meta_object(self):
        class CrossReferenceWidget:
            def parentWidget(self):  # noqa: N802 -- Qt API name
                return None
        self.assertEqual(core.focus_url(CrossReferenceWidget()), "binaryninja://xrefs")

    def test_a_failing_widget_reads_as_no_match(self):
        class Broken:
            def metaObject(self):  # noqa: N802 -- Qt API name
                raise RuntimeError("deleted C++ object")

            def parentWidget(self):  # noqa: N802 -- Qt API name
                raise RuntimeError("deleted C++ object")
        self.assertIsNone(core.focus_url(Broken()))

    def test_a_parent_loop_ends(self):
        w = _Widget(("QWidget",))
        w._parent = w
        self.assertIsNone(core.focus_url(w))

    def test_the_tokens_carry_no_name(self):
        self.assertEqual({core.CONSOLE_URL, core.XREFS_URL},
                         {"binaryninja://console", "binaryninja://xrefs"})


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
