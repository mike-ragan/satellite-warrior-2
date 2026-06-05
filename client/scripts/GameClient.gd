extends Node

signal state_updated(state: Dictionary)
signal error_received(message: String)
signal connected

const SERVER_HTTP := "http://localhost:8000"
const SERVER_WS   := "ws://localhost:8000/ws/"

var player_id: String = ""
var game_id: String = ""
var session_token: String = ""

var _ws := WebSocketPeer.new()
var _ws_active := false


func create_game(player_name: String) -> void:
	_post("/games", {"player_name": player_name}, _on_session_response)


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
