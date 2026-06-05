extends Node

signal state_updated(state: Dictionary)
signal combat_updated(state: Dictionary)
signal error_received(message: String)
signal connected

const SERVER_HTTP := "http://localhost:8000"
const SERVER_WS   := "ws://localhost:8000/ws/"

var player_id: String = ""
var game_id: String = ""
var session_token: String = ""

var _ws := WebSocketPeer.new()
var _ws_active := false


func _ready() -> void:
	_setup_theme()


func _setup_theme() -> void:
	var theme := Theme.new()

	var GREEN       := Color(0.10, 0.92, 0.18)
	var GREEN_HOVER := Color(0.45, 1.00, 0.45)
	var DARK_RED    := Color(0.28, 0.01, 0.01)
	var MED_RED     := Color(0.42, 0.02, 0.02)
	var BRIGHT_RED  := Color(0.55, 0.05, 0.05)

	var panel := StyleBoxFlat.new()
	panel.bg_color = DARK_RED
	panel.set_border_width_all(2)
	panel.border_color = GREEN
	theme.set_stylebox("panel", "Panel", panel)

	var btn_n := StyleBoxFlat.new()
	btn_n.bg_color = Color(0.14, 0.00, 0.00)
	btn_n.set_border_width_all(1)
	btn_n.border_color = GREEN
	var btn_h := StyleBoxFlat.new()
	btn_h.bg_color = MED_RED
	btn_h.set_border_width_all(1)
	btn_h.border_color = GREEN_HOVER
	var btn_p := StyleBoxFlat.new()
	btn_p.bg_color = BRIGHT_RED
	btn_p.set_border_width_all(1)
	btn_p.border_color = GREEN
	var btn_f := StyleBoxFlat.new()
	btn_f.draw_center = false
	btn_f.set_border_width_all(1)
	btn_f.border_color = Color(0.1, 0.9, 0.1, 0.4)
	theme.set_stylebox("normal",  "Button", btn_n)
	theme.set_stylebox("hover",   "Button", btn_h)
	theme.set_stylebox("pressed", "Button", btn_p)
	theme.set_stylebox("focus",   "Button", btn_f)
	theme.set_color("font_color",          "Button", GREEN)
	theme.set_color("font_hover_color",    "Button", GREEN_HOVER)
	theme.set_color("font_pressed_color",  "Button", Color(1.0, 1.0, 0.2))
	theme.set_color("font_disabled_color", "Button", Color(0.1, 0.4, 0.1))

	theme.set_color("font_color", "Label", GREEN)

	var le_n := StyleBoxFlat.new()
	le_n.bg_color = Color(0.03, 0.03, 0.03)
	le_n.set_border_width_all(1)
	le_n.border_color = GREEN
	var le_f := StyleBoxFlat.new()
	le_f.bg_color = Color(0.06, 0.06, 0.06)
	le_f.set_border_width_all(1)
	le_f.border_color = GREEN_HOVER
	theme.set_stylebox("normal", "LineEdit", le_n)
	theme.set_stylebox("focus",  "LineEdit", le_f)
	theme.set_color("font_color",      "LineEdit", GREEN)
	theme.set_color("caret_color",     "LineEdit", GREEN)
	theme.set_color("selection_color", "LineEdit", Color(0.1, 0.4, 0.1, 0.5))

	theme.set_color("color", "HSeparator", Color(0.1, 0.9, 0.1, 0.35))

	get_tree().root.theme = theme


func create_game(player_name: String) -> void:
	_post("/games", {"player_name": player_name}, _on_session_response)


func create_solo_game(player_name: String) -> void:
	_post("/games/solo", {"player_name": player_name}, _on_session_response)


func join_game(gid: String, player_name: String) -> void:
	_post("/games/" + gid + "/join", {"player_name": player_name}, _on_session_response)


func send(action: Dictionary) -> void:
	if _ws.get_ready_state() == WebSocketPeer.STATE_OPEN:
		_ws.send_text(JSON.stringify(action))


func _on_session_response(data: Dictionary) -> void:
	player_id = data.get("player_id", "")
	game_id = data.get("game_id", "")
	session_token = data.get("session_token", "")
	_connect_ws()


func _connect_ws() -> void:
	var err := _ws.connect_to_url(SERVER_WS + session_token)
	if err != OK:
		emit_signal("error_received", "Could not connect to server")
	else:
		_ws_active = true


func _process(_delta: float) -> void:
	if not _ws_active:
		return
	_ws.poll()
	match _ws.get_ready_state():
		WebSocketPeer.STATE_OPEN:
			while _ws.get_available_packet_count() > 0:
				var text := _ws.get_packet().get_string_from_utf8()
				var msg: Variant = JSON.parse_string(text)
				if msg is Dictionary:
					_handle(msg)
		WebSocketPeer.STATE_CLOSED:
			_ws_active = false


func _handle(msg: Dictionary) -> void:
	match msg.get("type"):
		"state":
			emit_signal("state_updated", msg.get("state", {}))
			if not is_connected("connected", Callable()):
				emit_signal("connected")
		"combat_state":
			emit_signal("combat_updated", msg)
		"error":
			emit_signal("error_received", msg.get("message", "Unknown error"))


func _post(path: String, body: Dictionary, callback: Callable) -> void:
	var http := HTTPRequest.new()
	add_child(http)
	http.request_completed.connect(func(result, code, _h, raw):
		http.queue_free()
		if code < 200 or code >= 300:
			emit_signal("error_received", "HTTP %d from %s" % [code, path])
			return
		var data: Variant = JSON.parse_string(raw.get_string_from_utf8())
		if data is Dictionary:
			callback.call(data)
	)
	http.request(
		SERVER_HTTP + path,
		["Content-Type: application/json"],
		HTTPClient.METHOD_POST,
		JSON.stringify(body)
	)
