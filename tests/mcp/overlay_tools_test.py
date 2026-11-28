"""MCP version 2: overlay sets and drawn keys, against the mock keyboard through a
real ControlServer (docs/mcp-server-plan.md, version 2), and the core's handling of
the user's "*" set."""
import base64
import os
import shutil
import tempfile
import threading
import unittest
import unittest.mock as mock

from polyhost.cli import polyctl
from polyhost.core.poly_core import PolyCore
from polyhost.handler.common import OverlayCommand
from polyhost.mcp import tools
from polyhost.mcp.server import McpServer
from polyhost.server import protocol as p
from polyhost.server.control_server import ControlServer
from polyhost.services import user_overlays
from polyhost.settings import PolySettings

BOX = [{"rect": [0, 0, 72, 40]}]


class OverlayToolsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="polykybd-uo-")
        real_get = PolySettings.get
        values = {"dev_mock_primary": True, "dev_mock_protocol": 0, "dev_force_hid_link": False,
                  p.MCP_SETTING: True, "generic_overlays_enabled": False}
        cls._patches = [
            mock.patch.object(PolySettings, "get",
                              lambda s, name: values[name] if name in values else real_get(s, name)),
            mock.patch.object(PolySettings, "save", lambda *a, **k: True),
            mock.patch.object(PolyCore, "_compute_daylight_value", lambda self: 20),
            mock.patch.object(user_overlays, "root_dir", lambda: cls.root),
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
        shutil.rmtree(cls.root, ignore_errors=True)

    def setUp(self):
        for s in user_overlays.list_sets(self.root):
            user_overlays.remove_set(s["app"], self.root)
        self.link = tools.HostLink(lambda: polyctl.connect(self.address, b"mcp-test"))
        self.addCleanup(self.link.close)

    def run_tool(self, name, **arguments):
        result, error = tools.call_tool(self.link, name, arguments)
        self.assertIsNone(error, f"{name}: {error}")
        self.assertLessEqual(set(result), tools.RESULT_FIELDS[name], name)
        return result

    def test_draw_a_physical_key_for_one_app(self):
        done = self.run_tool("draw_key", app="Blender", key="L:1.1", drawing=BOX, legend=False)
        self.assertEqual(done["key"], "KC_ESCAPE")
        self.assertEqual(done["shows_on"], ["L:1.1"])
        self.assertFalse(done["legend"])
        self.assertEqual(self.run_tool("list_user_overlays")["sets"],
                         [{"app": "blender", "keys": 1}])
        # The core laid it over the shipped Blender entry, last in the list.
        key = [k for k in self.core.mapping if "blender" in k.split(",")][0]
        self.assertTrue(str(self.core.mapping[key]["overlay"][-1]).endswith("user_blender.mods.png"))
        self.assertIsNotNone(self.core._pending_mapping)

    def test_a_keycode_on_two_keys_names_both(self):
        done = self.run_tool("draw_key", app="*", key={"base": "KC_ESC"}, drawing=BOX)
        self.assertEqual(done["shows_on"], ["L:1.1"])
        done = self.run_tool("draw_key", app="*", key="L:6.5", drawing=BOX)
        self.assertEqual(done["shows_on"], ["L:6.5", "R:6.5"])     # both space bars
        self.assertEqual(len(user_overlays.star_files(self.root)), 1)

    def test_draw_key_adds_and_create_overlay_replaces(self):
        self.run_tool("draw_key", app="x", key="KC_Q", drawing=BOX)
        self.run_tool("draw_key", app="x", key="KC_W", drawing=BOX, mods=["CTRL"])
        self.assertEqual(self.run_tool("list_user_overlays")["sets"], [{"app": "x", "keys": 2}])
        made = self.run_tool("create_overlay", app="x",
                             bindings=[{"key": "KC_E", "drawing": BOX}])
        self.assertEqual(made["placed"], [{"key": "KC_E", "mods": [], "legend": True}])
        self.assertEqual(self.run_tool("list_user_overlays")["sets"], [{"app": "x", "keys": 1}])

    def test_draw_key_reports_the_modifiers_it_wrote(self):
        self.run_tool("draw_key", app="x", key="KC_Q", drawing=BOX)
        done = self.run_tool("draw_key", app="x", key="KC_Q", drawing=BOX, mods=["CTRL"])
        self.assertEqual(done["mods"], ["CTRL"])

    def test_concurrent_merges_lose_no_binding(self):
        keys = ["KC_Q", "KC_W", "KC_E", "KC_R", "KC_T", "KC_Y"]
        threads = [threading.Thread(target=self.core.user_overlay_set,
                                    args=("x", [{"key": k, "drawing": BOX}]),
                                    kwargs={"merge": True}) for k in keys]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        self.assertEqual(len(user_overlays.load_set("x", self.root)["bindings"]), len(keys))

    def test_the_mapping_is_rebuilt_while_the_write_still_holds_the_lock(self):
        # Two edits then publish their mappings in the order they wrote their sets.
        held = []
        rebuild = self.core._apply_user_overlays
        def record():
            held.append(self.core._user_overlay_lock.locked())
            rebuild()
        self.core._apply_user_overlays = record
        self.core.user_overlay_set("x", [{"key": "KC_Q", "drawing": BOX}], merge=True)
        self.core.user_overlay_clear("x", "KC_Q")
        self.core.user_overlay_clear("x", "KC_Q")      # removes nothing: no rebuild
        self.assertEqual(held, [True, True])

    def test_clear_key_and_delete_overlay(self):
        self.run_tool("draw_key", app="x", key="KC_Q", drawing=BOX)
        self.run_tool("draw_key", app="x", key="KC_W", drawing=BOX)
        self.assertTrue(self.run_tool("clear_key", app="x", key="KC_Q")["removed"])
        self.assertFalse(self.run_tool("clear_key", app="x", key="KC_Q")["removed"])
        self.assertTrue(self.run_tool("delete_overlay", app="x")["removed"])
        self.assertEqual(self.run_tool("list_user_overlays")["sets"], [])

    def test_preview_is_a_png_image_item(self):
        self.run_tool("draw_key", app="blender", key="L:1.1", drawing=BOX)
        server = McpServer(self.link)
        reply = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                               "params": {"name": "preview_overlay",
                                          "arguments": {"app": "blender"}}})
        content = reply["result"]["content"]
        self.assertEqual(content[0]["type"], "image")
        self.assertEqual(content[0]["mimeType"], "image/png")
        self.assertTrue(base64.b64decode(content[0]["data"]).startswith(b"\x89PNG"))
        self.assertNotIn("image", content[1]["text"])

    def test_list_overlay_keys_and_find_icons(self):
        keys = {k["keycode"]: k["on_layer_0"] for k in self.run_tool("list_overlay_keys")["keys"]}
        self.assertEqual(keys["KC_ESCAPE"], ["L:1.1"])
        self.assertEqual(keys["KC_F5"], [])      # only on another layer: still drawable
        self.assertEqual(len(keys), 90)
        self.assertNotIn("MO(5)", keys)
        self.assertTrue(self.run_tool("find_icons", query="copy")["icons"])

    def test_follow_key_draws_on_one_physical_key_even_a_layer_key(self):
        # L:1.3 sends MO(5): no keycode image can reach it, a physical-key one can.
        done = self.run_tool("draw_key", app="*", key="L:1.3", follow="key", drawing=BOX,
                             legend=False)
        self.assertEqual((done["key"], done["shows_on"]), ("L:1.3", ["L:1.3"]))
        bindings = user_overlays.load_set("*", self.root)["bindings"]
        self.assertEqual(bindings[0]["follow"], "key")
        self.assertTrue(any(f.endswith(".keys.png") for f in user_overlays.star_files(self.root)))
        result, error = tools.call_tool(self.link, "preview_overlay", {"app": "*"})
        self.assertIsNone(error)
        self.assertTrue(result["image"])
        self.assertTrue(self.run_tool("clear_key", app="*", key="L:1.3", follow="key")["removed"])
        self.assertEqual(user_overlays.list_sets(self.root), [])

    def test_clear_key_takes_every_reference_form_draw_key_takes(self):
        self.run_tool("draw_key", app="*", key="L:1.1", follow="key", drawing=BOX)
        table = tools._table(self.link)
        row, col = next(pos for pos, name in table.by_pos.items() if name == "L:1.1")
        done = self.run_tool("clear_key", app="*", key={"row": row, "col": col}, follow="key")
        self.assertEqual((done["key"], done["removed"]), ("L:1.1", True))

    def test_clear_key_refuses_an_unknown_follow_and_removes_nothing(self):
        self.run_tool("draw_key", app="*", key="KC_Q", drawing=BOX)
        for follow in ("keys", "", None):
            result, error = tools.call_tool(self.link, "clear_key",
                                            {"app": "*", "key": "KC_Q", "follow": follow})
            self.assertIsNone(result, follow)
            self.assertIn("follow", error)
        self.assertEqual(len(user_overlays.load_set("*", self.root)["bindings"]), 1)

    def test_a_physical_clear_takes_the_same_limits_as_the_physical_draw(self):
        self.run_tool("draw_key", app="*", key="L:1.1", follow="key", drawing=BOX)
        for arguments in ({"app": "*", "key": "L:1.1", "follow": "key", "mods": ["CTRL"]},
                          {"app": "blender", "key": "L:1.1", "follow": "key"}):
            result, error = tools.call_tool(self.link, "clear_key", arguments)
            self.assertIsNone(result, arguments)
            self.assertTrue(error, arguments)
        self.assertEqual(len(user_overlays.load_set("*", self.root)["bindings"]), 1)

    def test_follow_key_refusals(self):
        for arguments in ({"app": "blender", "key": "L:1.1", "follow": "key", "drawing": BOX},
                          {"app": "*", "key": "KC_Q", "follow": "key", "drawing": BOX},
                          {"app": "*", "key": "L:1.1", "follow": "key", "drawing": BOX,
                           "mods": ["CTRL"]},
                          {"app": "*", "key": "L:5.5", "follow": "key", "drawing": BOX}):
            result, error = tools.call_tool(self.link, "draw_key", arguments)
            self.assertIsNone(result, arguments)
            self.assertTrue(error, arguments)

    def test_refusals_are_tool_errors_and_write_nothing(self):
        for name, arguments in (
                ("draw_key", {"app": "x", "key": "L:1.3", "drawing": BOX}),    # MO(5)
                ("draw_key", {"app": "x", "key": "KC_Q", "drawing": BOX, "follow": "key"}),
                ("draw_key", {"app": "x", "key": "KC_Q", "drawing": BOX, "follow": "other"}),
                ("draw_key", {"app": "x", "key": "KC_Q", "drawing": [{"text": "Ω"}]}),
                ("draw_key", {"app": "../x", "key": "KC_Q", "drawing": BOX}),
                ("create_overlay", {"app": "x", "bindings": []}),
                ("create_overlay", {"app": "x", "bindings": [{"key": "KC_Q", "drawing": BOX,
                                                             "file": "/etc/passwd"}]})):
            result, error = tools.call_tool(self.link, name, arguments)
            self.assertIsNone(result, name)
            self.assertTrue(error, name)
        self.assertEqual(user_overlays.list_sets(self.root), [])


class FollowKeyNeedsV40Test(unittest.TestCase):

    def test_older_firmware_is_named_in_the_refusal(self):
        from tests.mcp.tools_test import FakeClient
        client = FakeClient({p.M_STATUS_GET: {"name": "Split72", "protocol": 39}})
        result, error = tools.call_tool(tools.HostLink(connect=lambda: client), "draw_key",
                                        {"app": "*", "key": "L:1.1", "follow": "key",
                                         "drawing": BOX})
        self.assertIsNone(result)
        self.assertIn("protocol 40", error)
        self.assertNotIn(p.M_USER_OVERLAY_SET, [m for m, _ in client.calls])


class StarSetCoreTest(unittest.TestCase):
    """The core puts the "*" set in front of every send, and sends it alone where
    a window with no overlay would otherwise get a DISABLE."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="polykybd-uo-")
        self.addCleanup(shutil.rmtree, self.root, True)
        patch = mock.patch.object(user_overlays, "root_dir", lambda: self.root)
        patch.start()
        self.addCleanup(patch.stop)

    def _core(self):
        core = PolyCore.__new__(PolyCore)
        core.log = mock.MagicMock()
        core._pending_mapping_lock = threading.Lock()   # as __init__ builds it
        return core

    def test_the_star_set_goes_first_and_only_once(self):
        user_overlays.save_set("*", [{"key": "KC_Q", "drawing": BOX}])
        star = user_overlays.star_files()
        core = self._core()
        self.assertEqual(core._with_star_set(["a.mods.png"]), star + ["a.mods.png"])
        self.assertEqual(core._with_star_set(star + ["a.mods.png"]), star + ["a.mods.png"])
        user_overlays.remove_set("*")
        self.assertEqual(core._with_star_set(["a.mods.png"]), ["a.mods.png"])

    def _pending(self, core, template):
        core._shipped_mapping = {"app": {"overlay": ["a.mods.png"]}}
        core._generic_on_device = ("sig",)
        core.connected, core.safe_mode = True, False
        core.send_overlay_files = mock.MagicMock(return_value=bool(user_overlays.star_files()))
        core.submit_overlay_cmd = mock.MagicMock()
        core._note_overlay_state = mock.MagicMock()
        core._apply_user_overlays()
        handler = mock.MagicMock()
        handler.get_overlay_data.return_value = ["a.mods.png"] if template else None
        return handler

    def test_a_changed_star_set_is_sent_at_once_where_no_template_is_up(self):
        user_overlays.save_set("*", [{"key": "KC_Q", "drawing": BOX}])
        core = self._core()
        core._take_pending_mapping(self._pending(core, template=False))
        core.send_overlay_files.assert_called_once_with([])
        core.submit_overlay_cmd.assert_not_called()

    def test_a_removed_star_set_comes_down_where_no_template_is_up(self):
        core = self._core()
        core._take_pending_mapping(self._pending(core, template=False))
        core.submit_overlay_cmd.assert_called_once_with(OverlayCommand.DISABLE)

    def test_a_template_resend_carries_the_star_set_so_nothing_else_is_sent(self):
        user_overlays.save_set("*", [{"key": "KC_Q", "drawing": BOX}])
        core = self._core()
        core._take_pending_mapping(self._pending(core, template=True))
        core.send_overlay_files.assert_not_called()
        core.submit_overlay_cmd.assert_not_called()

    def test_a_new_mapping_keeps_the_handlers_device_state(self):
        from tests.handler.lab_tools_routing_test import _overlay_handler_class
        OverlayHandler = _overlay_handler_class()   # skips without a display
        handler = OverlayHandler.__new__(OverlayHandler)
        handler.overlays_enabled = True
        handler.remote_handler = mock.MagicMock()
        handler.annotate = lambda items, return_copy=True: dict(items)
        handler.force_resend = lambda: setattr(handler, "overlays_enabled", False)
        handler.set_mapping({"a": {"overlay": ["x.mods.png"]}})
        self.assertTrue(handler.overlays_enabled)   # a later DISABLE still goes out

    def test_the_pending_mapping_reaches_the_handler_on_the_tick(self):
        core = self._core()
        handler = self._pending(core, template=True)
        core._take_pending_mapping(handler)
        handler.set_mapping.assert_called_once_with(core.mapping)
        self.assertIsNone(core._generic_on_device)
        core._take_pending_mapping(handler)          # nothing new: no second call
        handler.set_mapping.assert_called_once()

    def _tick(self, core):
        handler = mock.MagicMock()
        handler.handle_active_window.return_value = (None, OverlayCommand.DISABLE)
        handler.focused_app.return_value = ("", "")
        core.overlay_handler = handler
        core.connected, core.safe_mode = True, False
        core._generic_on_device = None
        core._pending_mapping = None
        core.poly_settings = mock.MagicMock()
        core.poly_settings.get.return_value = False
        core.send_overlay_files = mock.MagicMock()
        core.submit_overlay_cmd = mock.MagicMock()
        for name in ("_track_active_os", "_track_keycap_face", "_track_midi_guide",
                     "_note_overlay_state"):
            setattr(core, name, mock.MagicMock())
        core._tick_window_tracking(250, 500)

    def test_no_overlay_with_a_star_set_sends_the_star_set(self):
        user_overlays.save_set("*", [{"key": "KC_Q", "drawing": BOX}])
        core = self._core()
        self._tick(core)
        core.send_overlay_files.assert_called_once_with([])
        core.submit_overlay_cmd.assert_not_called()

    def test_no_overlay_without_a_star_set_still_disables(self):
        core = self._core()
        self._tick(core)
        core.send_overlay_files.assert_not_called()
        core.submit_overlay_cmd.assert_called_once_with(OverlayCommand.DISABLE)


if __name__ == "__main__":
    unittest.main()
