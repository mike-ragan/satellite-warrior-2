extends Node2D

# Maps server arena coords (0-800, 0-500) to screen
const ARENA_OFFSET := Vector2(240, 110)
const SEND_RATE    := 0.05   # 20 fps input sends

var _my_id    := ""
var _send_tmr := 0.0
var _done     := false
var _bullets: Dictionary = {}   # bullet_id -> Polygon2D

@onready var combat_area:    Node2D    = $CombatArea
@onready var player_sat:     Polygon2D = $CombatArea/PlayerSat
@onready var ai_sat:         Polygon2D = $CombatArea/AISat
@onready var bullets_node:   Node2D    = $CombatArea/Bullets

@onready var player_name_lbl: Label    = $UI/TopBar/PlayerName
@onready var ai_name_lbl:     Label    = $UI/TopBar/AIName
@onready var moon_lbl:        Label    = $UI/TopBar/MoonLabel
@onready var player_hp_bg:    ColorRect = $UI/TopBar/PlayerHpBg
@onready var player_hp_fill:  ColorRect = $UI/TopBar/PlayerHpFill
@onready var ai_hp_bg:        ColorRect = $UI/TopBar/AIHpBg
@onready var ai_hp_fill:      ColorRect = $UI/TopBar/AIHpFill

@onready var winner_banner: Panel = $UI/WinnerBanner
@onready var winner_lbl:    Label = $UI/WinnerBanner/WinnerLabel
@onready var hint_lbl:      Label = $UI/WinnerBanner/HintLabel


func _ready() -> void:
	_my_id = GameClient.player_id

	var cross := _make_cross(18.0)
	player_sat.polygon = cross
	player_sat.color   = Color(0.15, 0.95, 0.25)
	ai_sat.polygon     = cross
	ai_sat.color       = Color(0.95, 0.15, 0.15)

	winner_banner.visible = false
	GameClient.combat_updated.connect(_on_combat_state)


func _process(delta: float) -> void:
	if _done:
		return
	_send_tmr -= delta
	if _send_tmr <= 0.0:
		_send_input()
		_send_tmr = SEND_RATE


func _send_input() -> void:
	var dx := 0.0
	var dy := 0.0
	if Input.is_action_pressed("ui_left"):  dx -= 1.0
	if Input.is_action_pressed("ui_right"): dx += 1.0
	if Input.is_action_pressed("ui_up"):    dy -= 1.0
	if Input.is_action_pressed("ui_down"):  dy += 1.0
	GameClient.send({
		"type": "combat_input",
		"dx":   dx,
		"dy":   dy,
		"fire": Input.is_action_pressed("ui_accept"),
	})


func _on_combat_state(state: Dictionary) -> void:
	if _done:
		return

	var moon_id: String = state.get("moon_id", "?").to_upper()
	moon_lbl.text = "COMBAT AT " + moon_id

	var sats: Dictionary = state.get("sats", {})
	for pid in sats:
		var sd: Dictionary = sats[pid]
		var is_me: bool    = (pid == _my_id)
		var sprite: Polygon2D = player_sat if is_me else ai_sat
		sprite.position = ARENA_OFFSET + Vector2(float(sd.get("x", 0)), float(sd.get("y", 0)))

		var name_lbl: Label     = player_name_lbl if is_me else ai_name_lbl
		var hp_bg:    ColorRect = player_hp_bg    if is_me else ai_hp_bg
		var hp_fill:  ColorRect = player_hp_fill  if is_me else ai_hp_fill
		name_lbl.text = sd.get("name", "?").to_upper()
		_set_hp_bar(hp_bg, hp_fill, sd.get("health", 0), sd.get("max_health", 100))

	# Bullets
	var bullet_list: Array     = state.get("bullets", [])
	var bullet_map:  Dictionary = {}
	for b in bullet_list:
		bullet_map[b["id"]] = b

	var to_remove: Array = []
	for bid in _bullets:
		if bid not in bullet_map:
			_bullets[bid].queue_free()
			to_remove.append(bid)
	for bid in to_remove:
		_bullets.erase(bid)

	for bid in bullet_map:
		var bdata: Dictionary = bullet_map[bid]
		if bid not in _bullets:
			var dot := Polygon2D.new()
			dot.polygon = PackedVector2Array([-3, -3, 3, -3, 3, 3, -3, 3])
			dot.color   = _bullet_color(bdata.get("weapon", "head"))
			bullets_node.add_child(dot)
			_bullets[bid] = dot
		(_bullets[bid] as Polygon2D).position = ARENA_OFFSET + Vector2(
			float(bdata.get("x", 0)), float(bdata.get("y", 0))
		)

	# Check for winner
	var winner_id: Variant = state.get("winner_id")
	if winner_id and not _done:
		_done = true
		var winner_data: Dictionary = sats.get(str(winner_id), {})
		winner_lbl.text = winner_data.get("name", "?").to_upper() + " WINS!"
		hint_lbl.text   = "RETURNING TO COMMAND..."
		winner_banner.visible = true
		await get_tree().create_timer(3.0).timeout
		get_tree().change_scene_to_file("res://scenes/Game.tscn")


func _set_hp_bar(bg: ColorRect, fill: ColorRect, hp: int, max_hp: int) -> void:
	var ratio := float(hp) / float(max_hp) if max_hp > 0 else 0.0
	fill.size.x = bg.size.x * ratio


func _bullet_color(weapon: String) -> Color:
	match weapon:
		"plasma_gun": return Color(0.1, 0.9, 1.0)
		"missile":    return Color(1.0, 0.4, 0.0)
		"grabber":    return Color(0.8, 0.1, 0.9)
		_:            return Color(0.9, 0.9, 0.2)


func _make_cross(s: float) -> PackedVector2Array:
	var t := s / 3.0
	return PackedVector2Array([
		Vector2(-t, -s), Vector2(t, -s), Vector2(t, -t),
		Vector2(s, -t),  Vector2(s, t),  Vector2(t, t),
		Vector2(t, s),   Vector2(-t, s), Vector2(-t, t),
		Vector2(-s, t),  Vector2(-s, -t), Vector2(-t, -t),
	])
