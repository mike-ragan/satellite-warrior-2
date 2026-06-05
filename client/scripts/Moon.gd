extends Area2D

signal moon_clicked(moon_id: String)

const RADIUS          := 45.0
const COLOR_UNCLAIMED := Color(0.35, 0.35, 0.42)
const COLOR_PLAYER    := Color(0.20, 0.45, 0.95)
const COLOR_AI        := Color(0.90, 0.22, 0.22)

var moon_id: String   = ""
var _player_id: String = ""
var _base_color        := COLOR_UNCLAIMED
var _deployable        := false

@onready var body:       Polygon2D = $Body
@onready var player_sat: Polygon2D = $PlayerSat
@onready var ai_sat:     Polygon2D = $AISat
@onready var name_lbl:   Label     = $NameLabel
@onready var res_lbl:    Label     = $ResLabel


func _ready() -> void:
	var pts := PackedVector2Array()
	for i in 48:
		pts.append(Vector2(cos(i * TAU / 48.0), sin(i * TAU / 48.0)) * RADIUS)
	body.polygon = pts
	player_sat.visible = false
	ai_sat.visible     = false
	input_pickable     = true
	mouse_entered.connect(_on_hover.bind(true))
	mouse_exited.connect(_on_hover.bind(false))


func setup(id: String, mname: String, resources: int, player_id: String) -> void:
	moon_id    = id
	_player_id = player_id
	name_lbl.text = mname
	res_lbl.text  = str(resources)


func set_deployable(val: bool) -> void:
	_deployable = val


func refresh(moon_data: Dictionary, players: Dictionary) -> void:
	var ctrl: String = moon_data.get("controlled_by") if moon_data.get("controlled_by") else ""
	if ctrl == _player_id:
		_base_color = COLOR_PLAYER
	elif ctrl != "":
		_base_color = COLOR_AI
	else:
		_base_color = COLOR_UNCLAIMED
	body.color = _base_color

	var hp := false
	var ha := false
	for pid in players:
		for sat in players[pid].get("satellites", []):
			if sat.get("moon_id") == moon_id:
				if pid == _player_id: hp = true
				else: ha = true
	player_sat.visible = hp
	ai_sat.visible     = ha


func _on_hover(entering: bool) -> void:
	if _deployable:
		body.color = _base_color.lightened(0.3) if entering else _base_color


func _input_event(_vp: Viewport, event: InputEvent, _idx: int) -> void:
	if event is InputEventMouseButton \
			and event.pressed \
			and event.button_index == MOUSE_BUTTON_LEFT \
			and _deployable:
		moon_clicked.emit(moon_id)
