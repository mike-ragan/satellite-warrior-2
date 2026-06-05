extends Node2D

func _ready() -> void:
	queue_redraw()

func _draw() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 12345
	var vp := get_viewport_rect().size
	for i in 200:
		var x := rng.randf_range(0.0, vp.x)
		var y := rng.randf_range(0.0, vp.y)
		var b := rng.randf_range(0.25, 1.0)
		var sz := 2.0 if rng.randf() > 0.92 else 1.0
		draw_rect(Rect2(x, y, sz, sz), Color(b, b, b, 1.0))
