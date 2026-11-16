# SPDX-License-Identifier: GPL-3.0-or-later
# The editor-free half of the PolyKybd Reporter: the screen token, the
# pseudo-URL, the JSON body and the send policy. Pure functions, so
# tests/test_reporter_core.gd runs them in a headless Godot without an editor.
#
# What is sent, and nothing else:
#
#     POST http://127.0.0.1:<port>/report      Content-Type: application/json
#     {"app": "godot", "url": "godot://script", "focused": true,
#      "pid": 4242, "input_age": 0.4, "token": "<only if one is set>"}
#
# The URL names the editor's main screen only. No scene, script or project
# name, no window title: the host routes on these tokens alone.
@tool
extends RefCounted

const APP := "godot"
const DEFAULT_PORT := 50164        # PolyKybdHost `browser_report_port`
# The host drops a report older than 8 s (browser_url.py DEFAULT_MAX_AGE_S).
# A keep-alive every 3 s keeps it fresh even if two are lost.
const KEEPALIVE_S := 3.0
const POLL_S := 0.2                # how often the plugin looks for a change
const HTTP_TIMEOUT_S := 0.5

# The name `main_screen_changed` passes (EditorPlugin._get_plugin_name() of the
# built-in screens) -> the token in the URL. "AssetLib" up to Godot 4.6,
# "Asset Store" from 4.7. A screen added by another plugin is "other": its
# name is the plugin's own text and is not sent.
const SCREEN_TOKENS := {
	"2D": "2d",
	"3D": "3d",
	"Script": "script",
	"Game": "game",
	"AssetLib": "assetlib",
	"Asset Store": "assetlib",
}

# Editor classes of the built-in main screens, for the screen that is already
# open when the plugin starts (no signal has been emitted yet).
const SCREEN_CLASSES := {
	"CanvasItemEditor": "2d",
	"Node3DEditor": "3d",
	"ScriptEditor": "script",
	"GameView": "game",
	"EditorAssetLibrary": "assetlib",
}


static func screen_token(screen_name) -> String:
	if typeof(screen_name) != TYPE_STRING and typeof(screen_name) != TYPE_STRING_NAME:
		return ""
	var s := String(screen_name)
	if s.is_empty():
		return ""
	return SCREEN_TOKENS.get(s, "other")


static func class_token(cls: String) -> String:
	return SCREEN_CLASSES.get(cls, "")


## `godot://<token>`, or null when the screen is not known.
static func context_url(token: String):
	if token.is_empty():
		return null
	return "godot://" + token


## One report. `focused` false with a null URL withdraws this instance, so
## the host stops showing the screen's keys when Godot loses focus or the
## plugin is disabled.
static func payload(url, token := "", pid = null, input_age = null, focused := true) -> String:
	var body := {"app": APP, "url": url, "focused": focused}
	if pid != null:
		body["pid"] = int(pid)
	if input_age != null:
		body["input_age"] = snappedf(maxf(0.0, float(input_age)), 0.1)
	if not String(token).is_empty():
		body["token"] = String(token)
	return JSON.stringify(body)


static func report_url(port: int) -> String:
	return "http://127.0.0.1:%d/report" % port


## Send on a change of URL, and as a keep-alive while nothing changes.
static func due(url, last_url, last_sent, now: float, keepalive_s := KEEPALIVE_S) -> bool:
	if url == null:
		return false
	if url != last_url or last_sent == null:
		return true
	return now - float(last_sent) >= keepalive_s
