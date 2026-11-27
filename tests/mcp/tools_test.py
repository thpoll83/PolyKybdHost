"""The MCP server's allow-list, its refusals and its result fields
(docs/mcp-server-plan.md -> Tests).

The allow-list tests use a fake connection. The tool tests run every tool against
a real PolyCore with the mock keyboard as its device (`dev_mock_primary`), behind a
real ControlServer on a temp socket, through polyctl's RpcClient: the same path
`polyctl mcp` takes.
"""
import os
import shutil
import tempfile
import threading
import unittest
import unittest.mock as mock

from polyhost.cli import polyctl
from polyhost.core.poly_core import PolyCore
from polyhost.mcp import tools
from polyhost.mcp.server import McpServer
from polyhost.server import protocol as p
from polyhost.server.control_server import ControlServer
from polyhost.settings import PolySettings

# The frozen allow-list. Adding a method to the MCP server fails here until this
# list is changed on purpose, after a look at docs/mcp-server-plan.md -> Security.
FROZEN_TOOL_METHODS = {
    "get_status": {"status.get"},
    "list_languages": {"lang.list"},
    "get_keymap": {"status.get", "keymap.layer_count", "keymap.buffer"},
    "list_app_overlays": set(),
    "list_keys": {"status.get", "keymap.layer_count", "keymap.buffer"},
    "show_layout": {"status.get", "keymap.layer_count", "keymap.buffer"},
    "set_language": {"lang.list", "lang.set"},
    "set_brightness": {"brightness.set", "settings.get", "brightness.daylight_refresh"},
    "set_idle_style": {"idle.style.set"},
    "set_glyph_script": {"glyph.script.set"},
    "set_key": {"status.get", "keymap.layer_count", "keymap.buffer", "keymap.set"},
    "set_overlays": {"overlay.enable", "overlay.disable"},
}

# docs/mcp-server-plan.md -> Not exposed, on purpose.
EXCLUDED_METHODS = [
    p.M_FW_FLASH, p.M_FW_APPLY_STAGED, p.M_ACTIVATE_BOOTLOADER, p.M_SET_HANDEDNESS,
    p.M_SET_HANDEDNESS_BOARD, p.M_FONTPACK_FLASH, p.M_FONTPACK_SYNC, p.M_FONTPACK_WIPE,
    p.M_DOOM_INSTALL, p.M_DOOM_INSTALL_PACK, p.M_UPDATE_INSTALL, p.M_HOST_SHUTDOWN,
    p.M_RESET_DYNAMIC_KEYMAP, p.M_COMMANDS_EXECUTE, p.M_SETTINGS_SET, p.M_SETTINGS_LIST,
    p.M_OVERLAY_MAPPING_SEND, p.M_OVERLAY_RESET, p.M_OVERLAY_RESET_BUFFERS,
    p.M_OVERLAY_RESET_MAPPING, p.M_OVERLAY_RESET_USAGE, p.M_OVERLAY_SET_ALL_USAGE,
    p.M_WINDOW_REPORT, p.M_AGENTS_LIST, p.M_AGENTS_REPORT, p.M_AGENTS_CLOUD_JOIN_CODE,
    p.M_TELEMETRY_SET, p.M_TELEMETRY_SEND, p.M_TELEMETRY_PREVIEW,
]


class FakeClient:
    def __init__(self, replies=None, fail=None):
        self.replies = replies or {}
        self.fail = fail
        self.calls = []
        self.closed = False

    def call(self, method, params=None):
        if method == p.M_CLIENT_IDENTIFY and method not in self.replies:
            return {"client": "mcp", "allowed": True}
        self.calls.append((method, params))
        if self.fail:
            exc, self.fail = self.fail, None
            raise exc
        reply = self.replies[method]
        return reply(params) if callable(reply) else reply

    def close(self):
        self.closed = True


class AllowListTest(unittest.TestCase):

    def test_the_tool_methods_are_the_frozen_list(self):
        self.assertEqual({k: set(v) for k, v in tools.TOOL_METHODS.items()}, FROZEN_TOOL_METHODS)
        self.assertEqual(tools.ALLOWED_METHODS, frozenset().union(*FROZEN_TOOL_METHODS.values()))

    def test_tools_methods_and_result_fields_name_the_same_tools(self):
        self.assertEqual(set(tools.TOOLS), set(tools.TOOL_METHODS))
        self.assertEqual(set(tools.TOOLS), set(tools.RESULT_FIELDS))
        self.assertEqual([t["name"] for t in tools.tool_list()], list(tools.TOOLS))

    def test_no_excluded_method_is_allowed(self):
        self.assertFalse(set(EXCLUDED_METHODS) & tools.ALLOWED_METHODS)

    def test_each_excluded_method_is_refused_before_anything_is_sent(self):
        for method in EXCLUDED_METHODS:
            client = FakeClient()
            link = tools.HostLink(connect=lambda c=client: c)
            with self.assertRaises(tools.MethodNotAllowed, msg=method):
                link.call(method, {})
            self.assertEqual(client.calls, [], method)

    def test_settings_get_reads_only_the_daylight_setting(self):
        client = FakeClient({p.M_SETTINGS_GET: True})
        link = tools.HostLink(connect=lambda: client)
        for key in ("window_report_network_enabled", "telemetry_enabled", None):
            with self.assertRaises(tools.MethodNotAllowed):
                link.call(p.M_SETTINGS_GET, {"key": key})
        self.assertEqual(client.calls, [])
        self.assertTrue(link.call(p.M_SETTINGS_GET, {"key": tools.DAYLIGHT_SETTING}))

    def test_read_tools_are_read_only_and_write_tools_say_what_they_do(self):
        reads = {"get_status", "list_languages", "get_keymap", "list_app_overlays",
                 "list_keys", "show_layout"}
        for entry in tools.tool_list():
            ann = entry["annotations"]
            if entry["name"] in reads:
                self.assertIs(ann["readOnlyHint"], True, entry["name"])
            else:
                self.assertIs(ann["readOnlyHint"], False, entry["name"])
                self.assertTrue("destructiveHint" in ann or "idempotentHint" in ann)
        set_key = next(t for t in tools.tool_list() if t["name"] == "set_key")
        self.assertIs(set_key["annotations"]["destructiveHint"], True)


class HostLinkTest(unittest.TestCase):

    def test_the_connection_names_itself_first(self):
        client = FakeClient({p.M_CLIENT_IDENTIFY: {"client": "mcp", "allowed": True},
                             p.M_LANG_LIST: []})
        tools.HostLink(connect=lambda: client).call(p.M_LANG_LIST)
        self.assertEqual([m for m, _ in client.calls], [p.M_CLIENT_IDENTIFY, p.M_LANG_LIST])

    def test_a_host_without_client_identify_still_works(self):
        def identify(params):
            raise polyctl.RpcError(p.ERR_METHOD_NOT_FOUND, "unknown method")
        client = FakeClient({p.M_CLIENT_IDENTIFY: identify, p.M_LANG_LIST: ["enUS"]})
        self.assertEqual(tools.HostLink(connect=lambda: client).call(p.M_LANG_LIST), ["enUS"])

    def test_no_host_running_is_a_tool_error_not_a_crash(self):
        def refuse():
            raise FileNotFoundError("no socket")
        server = McpServer(tools.HostLink(connect=refuse))
        reply = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                               "params": {"name": "get_status", "arguments": {}}})
        self.assertTrue(reply["result"]["isError"])
        self.assertEqual(reply["result"]["content"][0]["text"], tools.NOT_RUNNING)

    def test_a_restarted_host_is_reconnected_once(self):
        first = FakeClient({p.M_LANG_LIST: ["enUS"]}, fail=EOFError())
        second = FakeClient({p.M_LANG_LIST: ["enUS", "deDE"]})
        clients = iter([first, second])
        link = tools.HostLink(connect=lambda: next(clients))
        self.assertEqual(link.call(p.M_LANG_LIST), ["enUS", "deDE"])
        self.assertTrue(first.closed)

    def test_a_host_of_another_version_is_named_not_reported_missing(self):
        def mismatch():
            raise polyctl.RpcError(p.ERR_VERSION_MISMATCH, "control protocol mismatch")
        _result, error = tools.call_tool(tools.HostLink(connect=mismatch), "get_status", {})
        self.assertEqual(error, "control protocol mismatch")

    def test_a_host_error_reaches_the_assistant_as_text(self):
        client = FakeClient(fail=polyctl.RpcError(p.ERR_DEVICE, "firmware too old"))
        link = tools.HostLink(connect=lambda: client)
        result, error = tools.call_tool(link, "list_languages", {})
        self.assertIsNone(result)
        self.assertEqual(error, "firmware too old")


class ResultFieldTest(unittest.TestCase):

    def test_status_returns_its_fields_only(self):
        status = {"connected": True, "name": "Split72", "current_lang": "enUS",
                  "window_title": "secret.txt - Editor", "url": "https://example.com/x",
                  "pipe": {"port": "/dev/ttyACM0"}, "window_backend": "x11"}
        link = tools.HostLink(connect=lambda: FakeClient({p.M_STATUS_GET: status}))
        result, _ = tools.call_tool(link, "get_status", {})
        self.assertLessEqual(set(result), tools.RESULT_FIELDS["get_status"])
        self.assertNotIn("secret", repr(result))
        self.assertNotIn("example.com", repr(result))

    def test_a_split42_is_refused_by_the_key_tools(self):
        link = tools.HostLink(connect=lambda: FakeClient({p.M_STATUS_GET: {"name": "Split42"}}))
        for name in ("get_keymap", "list_keys", "show_layout"):
            result, error = tools.call_tool(link, name, {})
            self.assertIsNone(result)
            self.assertIn("split72 only", error)
        _result, error = tools.call_tool(link, "set_key", {"key": "L:1.1", "keycode": "KC_A"})
        self.assertIn("split72 only", error)


class _RecordingLink(tools.HostLink):
    def __init__(self, connect):
        super().__init__(connect)
        self.methods = []

    def call(self, method, params=None):
        self.methods.append(method)
        return super().call(method, params)


class MockKeyboardTest(unittest.TestCase):
    """Every tool against the mock keyboard, through a real ControlServer."""

    @classmethod
    def setUpClass(cls):
        real_get = PolySettings.get
        cls.values = values = {"dev_mock_primary": True, "dev_mock_protocol": 0,
                               "dev_force_hid_link": False, tools.DAYLIGHT_SETTING: False,
                               p.MCP_SETTING: True}
        cls._patches = [
            mock.patch.object(PolySettings, "get",
                              lambda s, name: values[name] if name in values else real_get(s, name)),
            mock.patch.object(PolySettings, "save", lambda *a, **k: True),
            mock.patch.object(PolyCore, "_compute_daylight_value", lambda self: 20),
        ]
        for patch in cls._patches:
            patch.start()
        cls.core = PolyCore(mock.MagicMock(), start_worker=False)
        cls.core.worker.start()
        cls.core.apply_reconnect(cls.core._reconnect_probe(threading.Event()))
        cls.tmp = tempfile.mkdtemp(prefix="polykybd-mcp-")
        cls.address = os.path.join(cls.tmp, "ctl.sock")
        cls.server = ControlServer(cls.core, "test", mock.MagicMock(),
                                   address=cls.address, authkey=b"mcp-test")
        cls.server.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        cls.core.shutdown()
        for patch in cls._patches:
            patch.stop()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.link = _RecordingLink(lambda: polyctl.connect(self.address, b"mcp-test"))
        self.addCleanup(self.link.close)

    def run_tool(self, name, **arguments):
        self.link.methods.clear()
        result, error = tools.call_tool(self.link, name, arguments)
        self.assertIsNone(error, f"{name}: {error}")
        self.assertLessEqual(set(result), tools.RESULT_FIELDS[name], name)
        self.assertLessEqual(set(self.link.methods), tools.TOOL_METHODS[name], name)
        return result

    def test_every_tool_runs_and_returns_its_fields_only(self):
        lang = self.run_tool("list_languages")["languages"][0]
        calls = [
            ("get_status", {}), ("get_keymap", {"layer": 0}), ("list_app_overlays", {}),
            ("list_keys", {"layer": 1}), ("show_layout", {}), ("set_language", {"lang": lang}),
            ("set_brightness", {"value": 12}), ("set_brightness", {"value": "default"}),
            ("set_idle_style", {"style": "jitter"}), ("set_glyph_script", {"script": "standard"}),
            ("set_overlays", {"enabled": True}),
        ]
        for name, arguments in calls:
            self.run_tool(name, **arguments)

    def test_list_keys_entries_have_their_fields_only(self):
        keys = self.run_tool("list_keys")["keys"]
        self.assertEqual(len(keys), 74)
        for entry in keys:
            self.assertEqual(set(entry), tools.LIST_KEYS_FIELDS)
        esc = next(k for k in keys if k["key"] == "L:1.1")
        self.assertEqual((esc["row"], esc["col"], esc["keycode"]), (0, 0, "KC_ESCAPE"))
        self.assertFalse(next(k for k in keys if k["key"] == "R:8.3")["has_display"])

    def test_set_key_writes_returns_previous_and_undoes(self):
        before = self.run_tool("get_keymap", layer=1)["keys"]["R:8.4"]
        done = self.run_tool("set_key", layer=1, key="L:9.4", keycode="KC_VOLU")
        self.assertEqual((done["key"], done["previous"]), ("R:8.4", before))
        self.assertEqual(self.run_tool("get_keymap", layer=1)["keys"]["R:8.4"], done["keycode"])
        self.run_tool("set_key", layer=1, key="R:8.4", keycode=done["previous"])
        self.assertEqual(self.run_tool("get_keymap", layer=1)["keys"]["R:8.4"], before)

    def test_the_setting_off_refuses_every_tool_and_on_allows_again(self):
        self.values[p.MCP_SETTING] = False
        try:
            for name in ("get_status", "list_languages", "set_overlays"):
                result, error = tools.call_tool(self.link, name, {"enabled": True}
                                                if name == "set_overlays" else {})
                self.assertIsNone(result, name)
                self.assertIn("turned off", error)
        finally:
            self.values[p.MCP_SETTING] = True
        self.run_tool("get_status")  # the same connection, no restart

    def test_the_host_refuses_an_mcp_connection_a_method_off_the_list(self):
        # A changed or older MCP server that skips its own check meets the host's.
        client = polyctl.connect(self.address, b"mcp-test")
        self.addCleanup(client.close)
        self.assertEqual(client.call(p.M_CLIENT_IDENTIFY, {"client": "mcp"}),
                         {"client": "mcp", "allowed": True})
        for method, params in ((p.M_RESET_DYNAMIC_KEYMAP, {}), (p.M_SETTINGS_LIST, {}),
                               (p.M_SETTINGS_GET, {"key": "telemetry_enabled"})):
            with self.assertRaises(polyctl.RpcError, msg=method) as ctx:
                client.call(method, params)
            self.assertEqual(ctx.exception.code, p.ERR_METHOD_NOT_FOUND)
        self.assertIsInstance(client.call(p.M_STATUS_GET), dict)

    def test_a_connection_that_does_not_identify_is_not_gated(self):
        # polyctl and the tray app: the setting does not touch them.
        self.values[p.MCP_SETTING] = False
        try:
            client = polyctl.connect(self.address, b"mcp-test")
            self.addCleanup(client.close)
            self.assertIsInstance(client.call(p.M_SETTINGS_LIST), dict)
            with self.assertRaises(polyctl.RpcError):
                client.call(p.M_CLIENT_IDENTIFY, {"client": "other"})
        finally:
            self.values[p.MCP_SETTING] = True

    def test_bad_arguments_are_tool_errors(self):
        for name, arguments in (
                ("set_language", {"lang": "xxXX"}), ("set_brightness", {"value": 51}),
                ("set_brightness", {"value": True}), ("set_idle_style", {"style": "disco"}),
                ("set_glyph_script", {"script": "klingon"}), ("set_overlays", {"enabled": "no"}),
                ("get_keymap", {"layer": 99}), ("set_key", {"key": "L:5.5", "keycode": "KC_A"}),
                ("set_key", {"key": "L:1.1", "keycode": "KC_NOT_A_KEY"})):
            result, error = tools.call_tool(self.link, name, arguments)
            self.assertIsNone(result, name)
            self.assertTrue(error, name)


if __name__ == "__main__":
    unittest.main()
