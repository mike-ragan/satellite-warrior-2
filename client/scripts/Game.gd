extends Node2D

const COMP_COLORS := {
	"head":       Color(0.65, 0.65, 0.70),
	"toroid":     Color(0.65, 0.65, 0.70),
	"grabber":    Color(1.00, 0.55, 0.00),
	"missile":    Color(1.00, 0.55, 0.00),
	"plasma_gun": Color(1.00, 0.55, 0.00),
	"armor":      Color(0.10, 0.80, 0.35),
	"ecm":        Color(0.10, 0.80, 0.35),
	"shield":     Color(0.10, 0.80, 0.35),
}

var _my_id:     String     = ""
var _state:     Dictionary = {}
var _setup_done := false

# Top bar
@onready var phase_label:  Label = $UI/TopBar/PhaseLabel
@onready var player_info:  Label = $UI/TopBar/PlayerInfo
@onready var ai_info:      Label = $UI/TopBar/AIInfo

# Action panel — phase containers
@onready var trading_panel:  VBoxContainer = $UI/ActionPanel/TradingPanel
@onready var deploy_panel:   VBoxContainer = $UI/ActionPanel/DeployPanel
@onready var combat_panel:   VBoxContainer = $UI/ActionPanel/CombatPanel
@onready var gameover_panel: VBoxContainer = $UI/ActionPanel/GameOverPanel
@onready var ready_btn:      Button        = $UI/ActionPanel/ReadyBtn

# Trading
@onready var alien_label:   Label = $UI/ActionPanel/TradingPanel/AlienLabel
@onready var my_sat_label:  Label = $UI/ActionPanel/TradingPanel/MySatLabel
var _comp_rows:   Array = []
var _comp_icons:  Array = []
var _comp_names:  Array = []
var _comp_prices: Array = []
var _comp_btns:   Array = []

# Deployment
@onready var deploy_info: Label = $UI/ActionPanel/DeployPanel/DeployInfo
@onready var sat_status:  Label = $UI/ActionPanel/DeployPanel/SatStatus

# Combat
@onready var combat_info: Label = $UI/ActionPanel/CombatPanel/CombatInfo

# Game over
@onready var winner_label:   Label  = $UI/ActionPanel/GameOverPanel/WinnerLabel
@onready var play_again_btn: Button = $UI/ActionPanel/GameOverPanel/PlayAgainBtn

# Bottom
@onready var status_label: Label = $UI/StatusLabel

# Planet
@onready var planet_poly: Polygon2D = $MoonMap/Planet

# Moons
var _moons: Dictionary = {}  # moon_id -> Moon node


func _ready() -> void:
	_my_id = GameClient.player_id

	# Generate planet circle
	var pts := PackedVector2Array()
	for i in 64:
		pts.append(Vector2(cos(i * TAU / 64.0), sin(i * TAU / 64.0)) * 115.0)
	planet_poly.polygon = pts

	GameClient.state_updated.connect(_on_state)
	GameClient.error_received.connect(func(m: String) -> void:
		status_label.text = m
	)

	for i in 3:
		var base := "UI/ActionPanel/TradingPanel/"
		var row   := get_node(base + "CompRow%d" % i) as HBoxContainer
		_comp_rows.append(row)
		_comp_icons.append(row.get_node("CompIcon%d" % i) as ColorRect)
		_comp_names.append(row.get_node("CompName%d" % i) as Label)
		_comp_prices.append(row.get_node("CompPrice%d" % i) as Label)
		var btn := row.get_node("BuyBtn%d" % i) as Button
		_comp_btns.append(btn)
		var idx := i
		btn.pressed.connect(func() -> void: _on_buy(idx))

	ready_btn.pressed.connect(func() -> void:
		GameClient.send({"type": "ready"})
	)
	play_again_btn.pressed.connect(func() -> void:
		get_tree().change_scene_to_file("res://scenes/Lobby.tscn")
	)

	for mid in ["m0", "m1", "m2", "m3", "m4"]:
		var moon_node = $MoonMap.get_node("Moon_" + mid)
		_moons[mid] = moon_node
		moon_node.moon_clicked.connect(_on_moon_clicked)


func _on_state(state: Dictionary) -> void:
	_state = state

	if not _setup_done and state.get("phase") != "waiting":
		_setup_moons(state)
		_setup_done = true

	_refresh(state)


func _setup_moons(state: Dictionary) -> void:
	for moon_data in state.get("moons", []):
		var mid: String = moon_data["id"]
		var moon_node   = _moons.get(mid)
		if moon_node:
			moon_node.setup(mid, moon_data["name"], moon_data["resource_amount"], _my_id)


func _refresh(state: Dictionary) -> void:
	var phase:   String     = state.get("phase", "waiting")
	var players: Dictionary = state.get("players", {})

	var me: Dictionary = players.get(_my_id, {})
	var ai: Dictionary = {}
	for pid in players:
		if pid != _my_id:
			ai = players[pid]

	player_info.text = "CREDIT+%04d\n%s" % [me.get("cash", 0), me.get("name", "?").to_upper()]
	ai_info.text     = "%s\nCREDIT+%04d" % [ai.get("name", "?").to_upper(), ai.get("cash", 0)]
	phase_label.text = phase.replace("_", " ").to_upper()

	for moon_data in state.get("moons", []):
		var moon_node = _moons.get(moon_data["id"])
		if moon_node:
			moon_node.refresh(moon_data, players)

	trading_panel.visible  = phase == "trading"
	deploy_panel.visible   = phase == "deployment"
	combat_panel.visible   = phase == "combat"
	gameover_panel.visible = phase == "game_over"
	ready_btn.visible      = phase in ["trading", "deployment", "combat"]

	var can_deploy := phase == "deployment" and _has_deployable_sat(me)
	for moon_node in _moons.values():
		moon_node.set_deployable(can_deploy)

	match phase:
		"trading":    _refresh_trading(state, me)
		"deployment": _refresh_deploy(me)
		"combat":     _refresh_combat(state)
		"game_over":  winner_label.text = "%s\nWINS!" % state.get("winner", "?").to_upper()


func _refresh_trading(state: Dictionary, me: Dictionary) -> void:
	var offer: Variant = state.get("alien_offer")
	if not offer is Dictionary:
		alien_label.text = "NO ALIEN THIS TURN"
		for i in 3:
			_comp_rows[i].visible = false
		return

	var atype: String = offer.get("alien_type", "?").to_upper()
	alien_label.text = "%s DEALER" % atype

	var comps:  Array      = offer.get("components", [])
	var prices: Dictionary = offer.get("prices", {})

	for i in 3:
		if i < comps.size():
			var comp: String = comps[i]
			_comp_rows[i].visible   = true
			_comp_icons[i].color    = COMP_COLORS.get(comp, Color.WHITE)
			_comp_names[i].text     = comp.replace("_", " ").to_upper()
			_comp_prices[i].text    = "$%d" % int(prices.get(comp, 0))
		else:
			_comp_rows[i].visible = false

	my_sat_label.text = _sat_summary(me)


func _refresh_deploy(me: Dictionary) -> void:
	if _has_deployable_sat(me):
		deploy_info.text = "CLICK A MOON TO DEPLOY\nYOUR SATELLITE."
	else:
		deploy_info.text = "BUY A TOROID TO GIVE\nYOUR SATELLITE MOBILITY."
	sat_status.text = _sat_summary(me)


func _refresh_combat(state: Dictionary) -> void:
	var log: Array = state.get("combat_log", [])
	if log.is_empty():
		combat_info.text = "NO BATTLES THIS TURN."
		return
	var text := ""
	for entry in log:
		var winner_name := _name_of(entry.get("winner_id", ""), state).to_upper()
		var moon_name   := _moon_name(entry.get("moon_id", ""), state).to_upper()
		var rounds: Array = entry.get("rounds", [])
		text += "%s\n  WINNER: %s  (%d ROUNDS)\n\n" % [moon_name, winner_name, rounds.size()]
	combat_info.text = text.strip_edges()


func _on_buy(index: int) -> void:
	var offer: Variant = _state.get("alien_offer")
	if not offer is Dictionary:
		return
	var comps: Array = offer.get("components", [])
	if index < comps.size():
		GameClient.send({"type": "buy", "component": comps[index], "qty": 1})


func _on_moon_clicked(moon_id: String) -> void:
	var me:   Dictionary = _state.get("players", {}).get(_my_id, {})
	var sats: Array      = me.get("satellites", [])
	if sats.is_empty():
		return
	var sat_id := ""
	for sat in sats:
		if not sat.get("moon_id"):
			sat_id = sat["id"]
			break
	if sat_id.is_empty():
		sat_id = sats[0]["id"]
	GameClient.send({"type": "deploy", "satellite_id": sat_id, "moon_id": moon_id})


func _has_deployable_sat(me: Dictionary) -> bool:
	for sat in me.get("satellites", []):
		if "toroid" in sat.get("components", []):
			return true
		if sat.get("moon_id"):
			return true
	return false


func _sat_summary(me: Dictionary) -> String:
	var lines := ""
	for sat in me.get("satellites", []):
		var loc: String = sat.get("moon_id") if sat.get("moon_id") else "RESERVE"
		var comps: Array = sat.get("components", [])
		var hp: int      = sat.get("stability", 100)
		lines += "[%s] %s  HP:%d\n%s\n\n" % [
			sat.get("id", "?").substr(0, 4).to_upper(), loc.to_upper(), hp,
			", ".join(PackedStringArray(comps)).to_upper()
		]
	return lines.strip_edges() if lines else "NO SATELLITES"


func _name_of(pid: String, state: Dictionary) -> String:
	return state.get("players", {}).get(pid, {}).get("name", "?")


func _moon_name(mid: String, state: Dictionary) -> String:
	for moon in state.get("moons", []):
		if moon["id"] == mid:
			return moon["name"]
	return mid
