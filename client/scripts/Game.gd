extends Node2D

@onready var phase_label: Label      = $UI/VBox/PhaseLabel
@onready var turn_label: Label       = $UI/VBox/TurnLabel
@onready var player_label: Label     = $UI/VBox/HBox/Left/PlayerLabel
@onready var moons_label: Label      = $UI/VBox/HBox/Mid/MoonsLabel
@onready var alien_label: Label      = $UI/VBox/HBox/Right/AlienLabel
@onready var comp_input: LineEdit    = $UI/VBox/HBox/Right/CompInput
@onready var qty_input: SpinBox      = $UI/VBox/HBox/Right/QtyInput
@onready var buy_btn: Button         = $UI/VBox/HBox/Right/BuyBtn
@onready var sat_input: LineEdit     = $UI/VBox/HBox/Right/SatInput
@onready var moon_input: LineEdit    = $UI/VBox/HBox/Right/MoonInput
@onready var deploy_btn: Button      = $UI/VBox/HBox/Right/DeployBtn
@onready var ready_btn: Button       = $UI/VBox/ReadyBtn
@onready var status_label: Label     = $UI/VBox/StatusLabel

var _my_id: String = ""
var _last_state: Dictionary = {}


func _ready() -> void:
	_my_id = GameClient.player_id
	GameClient.state_updated.connect(_refresh)
	GameClient.error_received.connect(func(msg): status_label.text = "! " + msg)
	buy_btn.pressed.connect(_on_buy)
	deploy_btn.pressed.connect(_on_deploy)
	ready_btn.pressed.connect(func(): GameClient.send({"type": "ready"}))


func _refresh(state: Dictionary) -> void:
	_last_state = state
	var phase: String = state.get("phase", "")
	var turn: int     = state.get("turn_number", 0)

	phase_label.text = "Phase: %s" % phase.to_upper()
	turn_label.text  = "Turn %d" % turn

	# Player panel
	var me: Dictionary = state.get("players", {}).get(_my_id, {})
	var sat_lines := ""
	for sat in me.get("satellites", []):
		var loc: String = sat.get("moon_id", "reserve") if sat.get("moon_id") else "reserve"
		sat_lines += "\n  [%s] @ %s  HP:%d\n    %s" % [
			sat["id"], loc, sat["stability"],
			", ".join(PackedStringArray(sat.get("components", [])))
		]
	player_label.text = "%s\nCash: %d%s" % [
		me.get("name", "?"), me.get("cash", 0), sat_lines
	]

	# Moons panel
	var moon_lines := ""
	for moon in state.get("moons", []):
		var owner: String = moon.get("controlled_by") if moon.get("controlled_by") else "unclaimed"
		moon_lines += "\n%s [%s]  res:%d  → %s" % [
			moon["name"], moon["id"], moon["resource_amount"], owner
		]
	moons_label.text = "MOONS:" + moon_lines

	# Alien market panel
	var offer: Variant = state.get("alien_offer")
	if offer is Dictionary:
		var price_lines := ""
		for comp in offer.get("components", []):
			price_lines += "\n  %s: %d" % [comp, offer["prices"].get(comp, 0)]
		alien_label.text = "ALIEN (%s):%s" % [offer.get("alien_type", "?"), price_lines]
	else:
		alien_label.text = "No alien visit this phase"

	# Combat log
	var log: Array = state.get("combat_log", [])
	if log.size() > 0:
		var summary := "COMBAT:\n"
		for entry in log:
			summary += "  Moon %s — winner: %s\n" % [entry["moon_id"], entry["winner_id"]]
		status_label.text = summary
	elif phase == "game_over":
		status_label.text = "GAME OVER — Winner: %s" % state.get("winner", "?")
	else:
		status_label.text = ""

	# Ready button visibility
	ready_btn.visible = phase in ["trading", "deployment", "combat"]
	buy_btn.visible   = phase == "trading"
	deploy_btn.visible = phase == "deployment"


func _on_buy() -> void:
	GameClient.send({
		"type": "buy",
		"component": comp_input.text.strip_edges().to_lower(),
		"qty": int(qty_input.value),
	})


func _on_deploy() -> void:
	GameClient.send({
		"type": "deploy",
		"satellite_id": sat_input.text.strip_edges(),
		"moon_id": moon_input.text.strip_edges().to_lower(),
	})
