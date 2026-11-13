# SPDX-License-Identifier: GPL-3.0-or-later
# Unit tests of reporter_core.gd. No editor needed:
#
#     godot --headless --script godot-plugin/tests/test_reporter_core.gd
#
# Prints one line per failure and exits 1 if any failed, 0 otherwise.
# tests/godot_plugin/reporter_core_test.py runs this when a `godot` binary is
# found (POLYKYBD_GODOT or PATH).
extends SceneTree

const Core := preload("../addons/polykybd_reporter/reporter_core.gd")

var _failures := 0
var _checks := 0


func _init() -> void:
	_test_screen_tokens()
	_test_context_url()
	_test_payload()
	_test_due()
	print("reporter_core: %d checks, %d failed" % [_checks, _failures])
	quit(1 if _failures > 0 else 0)


func _eq(got, want, what: String) -> void:
	_checks += 1
	if typeof(got) != typeof(want) or got != want:
		_failures += 1
		printerr("FAIL %s: got %s, want %s" % [what, var_to_str(got), var_to_str(want)])


func _test_screen_tokens() -> void:
	_eq(Core.screen_token("2D"), "2d", "2D")
	_eq(Core.screen_token("3D"), "3d", "3D")
	_eq(Core.screen_token("Script"), "script", "Script")
	_eq(Core.screen_token("Game"), "game", "Game")
	_eq(Core.screen_token("AssetLib"), "assetlib", "AssetLib (up to 4.6)")
	_eq(Core.screen_token("Asset Store"), "assetlib", "Asset Store (4.7)")
	# Another plugin's screen: its name is not sent.
	_eq(Core.screen_token("My Secret Tool"), "other", "plugin screen")
	_eq(Core.screen_token(""), "", "empty")
	_eq(Core.screen_token(null), "", "null")
	_eq(Core.class_token("ScriptEditor"), "script", "class ScriptEditor")
	_eq(Core.class_token("Node3DEditor"), "3d", "class Node3DEditor")
	_eq(Core.class_token("Label"), "", "class Label")


func _test_context_url() -> void:
	_eq(Core.context_url("script"), "godot://script", "url")
	_eq(Core.context_url("other"), "godot://other", "url other")
	_eq(Core.context_url(""), null, "url unknown")
	_eq(Core.report_url(50164), "http://127.0.0.1:50164/report", "report url")


func _test_payload() -> void:
	var p = JSON.parse_string(Core.payload("godot://2d", "", 4242, 0.44, true))
	_eq(p["app"], "godot", "payload app")
	_eq(p["url"], "godot://2d", "payload url")
	_eq(p["focused"], true, "payload focused")
	_eq(int(p["pid"]), 4242, "payload pid")
	_eq(p["input_age"], 0.4, "payload input_age rounded")
	_eq(p.has("token"), false, "no token unless set")
	_eq(p.keys().size(), 5, "no other keys")
	var w = JSON.parse_string(Core.payload(null, "s3cret", 7, null, false))
	_eq(w["url"], null, "withdrawal url")
	_eq(w["focused"], false, "withdrawal focused")
	_eq(w["token"], "s3cret", "token when set")
	_eq(w.has("input_age"), false, "no input_age when unknown")
	var neg = JSON.parse_string(Core.payload("godot://3d", "", null, -2.0, true))
	_eq(neg["input_age"], 0.0, "negative input_age clamped")
	_eq(neg.has("pid"), false, "no pid when unknown")


func _test_due() -> void:
	_eq(Core.due("godot://2d", null, null, 0.0), true, "first report")
	_eq(Core.due("godot://2d", "godot://2d", 0.0, 2.9), false, "inside keep-alive")
	_eq(Core.due("godot://2d", "godot://2d", 0.0, 3.0), true, "keep-alive")
	_eq(Core.due("godot://3d", "godot://2d", 0.0, 0.1), true, "change")
	_eq(Core.due(null, "godot://2d", 0.0, 9.0), false, "unknown screen sends nothing")
