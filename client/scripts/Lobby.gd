extends Node2D

@onready var name_input: LineEdit   = $UI/VBox/NameInput
@onready var create_btn: Button     = $UI/VBox/CreateBtn
@onready var solo_btn: Button       = $UI/VBox/SoloBtn
@onready var game_id_label: Label   = $UI/VBox/GameIdLabel
@onready var join_input: LineEdit   = $UI/VBox/JoinInput
@onready var join_btn: Button       = $UI/VBox/JoinBtn
@onready var status_label: Label    = $UI/VBox/StatusLabel


func _ready() -> void:
	GameClient.state_updated.connect(_on_state)
	GameClient.error_received.connect(_on_error)
	create_btn.pressed.connect(_on_create)
	solo_btn.pressed.connect(_on_solo)
	join_btn.pressed.connect(_on_join)


func _on_solo() -> void:
	var name := name_input.text.strip_edges()
	if name.is_empty():
		name = "Player"
	status_label.text = "Starting solo game..."
	GameClient.create_solo_game(name)


func _on_create() -> void:
	var name := name_input.text.strip_edges()
	if name.is_empty():
		name = "Player 1"
	status_label.text = "Creating game..."
	GameClient.create_game(name)


func _on_join() -> void:
	var gid := join_input.text.strip_edges().to_upper()
	var name := name_input.text.strip_edges()
	if gid.is_empty():
		status_label.text = "Enter a game code first"
		return
	if name.is_empty():
		name = "Player 2"
	status_label.text = "Joining game..."
	GameClient.join_game(gid, name)


func _on_state(_state: Dictionary) -> void:
	var gid := GameClient.game_id
	game_id_label.text = "Game code: %s  (share with opponent)" % gid
	game_id_label.visible = true
	status_label.text = "Connected — waiting for opponent..." if _state.get("phase") == "waiting" else "Starting..."
	if _state.get("phase") != "waiting":
		get_tree().change_scene_to_file("res://scenes/Game.tscn")


func _on_error(msg: String) -> void:
	status_label.text = "Error: " + msg
