# SPDX-License-Identifier: GPL-3.0-or-later
# PolyKybd Reporter: tells the local PolyKybdHost which main screen of the
# Godot editor is open (2D, 3D, Script, Game, Asset Store), so the keycaps
# show that screen's shortcuts. See ../../README.md; the wire format is in
# reporter_core.gd.
#
# * EditorPlugin.main_screen_changed gives the screen on every change.
# * The screen that is open when the plugin starts is read once from the
#   editor (`_initial_screen()`), because no signal comes for it.
# * _process() polls every 0.2 s: it sends on a change and as a keep-alive
#   every 3 s. HTTPRequest sends on its own thread, so the editor never
#   waits for the host.
# * When Godot loses OS focus (another app, or the running game's own window)
#   it sends `url: null, focused: false`, and the same when the plugin is
#   disabled or the editor quits.
@tool
extends EditorPlugin

const Core := preload("reporter_core.gd")

const SETTING_ENABLED := "polykybd/reporter/enabled"
const SETTING_PORT := "polykybd/reporter/port"
const SETTING_TOKEN := "polykybd/reporter/token"

var _http: HTTPRequest
var _screen := ""             # token of the current main screen, "" = unknown
var _focused := true
var _last_url = null
var _last_sent = null         # seconds (Time.get_ticks_msec() / 1000.0)
var _last_input = null        # seconds of the newest key or mouse event
var _reported := false        # a screen was sent since the last withdrawal
var _pending := ""            # body waiting while a request is in flight
var _pending_port := 0
var _since_poll := 0.0


func _enter_tree() -> void:
	_add_settings()
	_http = HTTPRequest.new()
	_http.timeout = Core.HTTP_TIMEOUT_S
	_http.use_threads = true
	_http.request_completed.connect(_on_request_completed)
	add_child(_http)
	main_screen_changed.connect(_on_main_screen_changed)
	_screen = _initial_screen()
	set_process(true)
	set_process_input(true)


func _exit_tree() -> void:
	if main_screen_changed.is_connected(_on_main_screen_changed):
		main_screen_changed.disconnect(_on_main_screen_changed)
	_withdraw_now()
	if _http != null:
		_http.queue_free()
		_http = null


func _on_main_screen_changed(screen_name: String) -> void:
	_screen = Core.screen_token(screen_name)
	_tick()


func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		_focused = false
		_withdraw()
	elif what == NOTIFICATION_APPLICATION_FOCUS_IN:
		_focused = true
		_last_url = null          # report again at once
		_tick()


func _input(event: InputEvent) -> void:
	# Only the time is kept: no key, no position.
	if event is InputEventKey or event is InputEventMouseButton or event is InputEventMouseMotion:
		_last_input = _now()


func _process(delta: float) -> void:
	_since_poll += delta
	if _since_poll < Core.POLL_S:
		return
	_since_poll = 0.0
	_tick()


func _tick() -> void:
	if not _setting(SETTING_ENABLED, true):
		_withdraw()
		return
	if not _focused:
		return
	var url = Core.context_url(_screen)
	var now := _now()
	if not Core.due(url, _last_url, _last_sent, now):
		return
	var age = null if _last_input == null else now - float(_last_input)
	_send(Core.payload(url, _setting(SETTING_TOKEN, ""), OS.get_process_id(), age, true))
	_last_url = url
	_last_sent = now
	_reported = true


# Tell the host this instance stopped reporting, once, so the keyboard leaves
# the screen's keys at once instead of after the 8 s freshness window.
func _withdraw() -> void:
	if not _reported:
		return
	_send(Core.payload(null, _setting(SETTING_TOKEN, ""), OS.get_process_id(), null, false))
	_reported = false
	_last_url = null
	_last_sent = null


# The same on disable or quit, when the HTTPRequest node is about to go: a
# short blocking request (loopback, at most HTTP_TIMEOUT_S).
func _withdraw_now() -> void:
	if not _reported:
		return
	_reported = false
	var body := Core.payload(null, _setting(SETTING_TOKEN, ""), OS.get_process_id(), null, false)
	var client := HTTPClient.new()
	if client.connect_to_host("127.0.0.1", int(_setting(SETTING_PORT, Core.DEFAULT_PORT))) != OK:
		return
	var deadline := Time.get_ticks_msec() + int(Core.HTTP_TIMEOUT_S * 1000.0)
	var sent := false
	while Time.get_ticks_msec() < deadline:
		client.poll()
		var status := client.get_status()
		if status == HTTPClient.STATUS_CONNECTED and not sent:
			client.request(HTTPClient.METHOD_POST, "/report",
					["Content-Type: application/json"], body)
			sent = true
		elif sent and (status == HTTPClient.STATUS_BODY or status == HTTPClient.STATUS_CONNECTED):
			break
		elif status in [HTTPClient.STATUS_CANT_CONNECT, HTTPClient.STATUS_CANT_RESOLVE,
				HTTPClient.STATUS_CONNECTION_ERROR, HTTPClient.STATUS_DISCONNECTED]:
			break
		OS.delay_msec(5)
	client.close()


func _send(body: String) -> void:
	var port := int(_setting(SETTING_PORT, Core.DEFAULT_PORT))
	if _http == null:
		return
	if _http.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		# One request at a time: keep only the newest report.
		_pending = body
		_pending_port = port
		return
	var err := _http.request(Core.report_url(port),
			PackedStringArray(["Content-Type: application/json"]),
			HTTPClient.METHOD_POST, body)
	if err == ERR_BUSY:
		_pending = body
		_pending_port = port


func _on_request_completed(_result: int, _code: int, _headers: PackedStringArray,
		_body: PackedByteArray) -> void:
	# Failures are silent: PolyKybdHost may not be running. The next change or
	# keep-alive tries again.
	if _pending.is_empty() or _http == null:
		return
	var body := _pending
	var port := _pending_port
	_pending = ""
	_http.request(Core.report_url(port),
			PackedStringArray(["Content-Type: application/json"]),
			HTTPClient.METHOD_POST, body)


# The main screen that is open now. Godot 4.5 and later name it on the main
# screen's container for screen readers (EditorMainScreen sets its
# accessibility name to the plugin name); before that, the visible editor
# control tells it.
func _initial_screen() -> String:
	var vbox := EditorInterface.get_editor_main_screen()
	if vbox == null:
		return ""
	var parent := vbox.get_parent()
	if parent != null and "accessibility_name" in parent:
		var token := Core.screen_token(parent.get("accessibility_name"))
		if not token.is_empty():
			return token
	for child in vbox.get_children():
		if child is Control and child.visible:
			var token := Core.class_token(child.get_class())
			if not token.is_empty():
				return token
	return ""


func _add_settings() -> void:
	var es := EditorInterface.get_editor_settings()
	_add_setting(es, SETTING_ENABLED, true, TYPE_BOOL, PROPERTY_HINT_NONE, "")
	_add_setting(es, SETTING_PORT, Core.DEFAULT_PORT, TYPE_INT, PROPERTY_HINT_RANGE, "1,65535")
	_add_setting(es, SETTING_TOKEN, "", TYPE_STRING, PROPERTY_HINT_PASSWORD, "")


func _add_setting(es: EditorSettings, name: String, value, type: int, hint: int, hint_string: String) -> void:
	if not es.has_setting(name):
		es.set_setting(name, value)
	es.set_initial_value(name, value, false)
	es.add_property_info({"name": name, "type": type, "hint": hint, "hint_string": hint_string})


func _setting(name: String, default):
	var es := EditorInterface.get_editor_settings()
	return es.get_setting(name) if es.has_setting(name) else default


func _now() -> float:
	return Time.get_ticks_msec() / 1000.0
