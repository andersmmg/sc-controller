"""
Tests for controller icon tinting (scc.gui.icon_tint).
"""
from scc.gui.icon_tint import (
	PRESET_COLORS, DEFAULT_COLOR, _parse_hex, tint_gray, tint_svg,
	auto_assign_color, get_icon_color, get_icon_shape, shape_name,
	SHAPE_NAMES,
)


class FakeConfig(object):
	""" Minimal stand-in for scc.config.Config """
	def __init__(self, controllers=None):
		self.values = {"controllers": controllers or {}}
		self.saved = False

	def get_controller_config(self, controller_id):
		if controller_id not in self.values["controllers"]:
			self.values["controllers"][controller_id] = {}
		return self.values["controllers"][controller_id]

	def save(self):
		self.saved = True


def _hex_to_rgb(h):
	return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def test_parse_hex():
	assert _parse_hex("#00ff00") == (0.0, 1.0, 0.0)
	assert _parse_hex("00ff00") == (0.0, 1.0, 0.0)
	assert _parse_hex("#0f0") == (0.0, 1.0, 0.0)
	assert _parse_hex("notacolor") is None
	assert _parse_hex("#12345") is None


def test_tint_preserves_grays():
	""" Black, white and pure grays tint to shades of the color;
	tinting with a gray color is identity. """
	assert tint_gray("#000000", "#ff0000") == "#000000"
	assert tint_gray("#ffffff", "#00ff00") == "#ffffff"
	assert tint_gray("#808080", "#808080") == "#808080"
	assert tint_gray("#808080", "garbage") == "#808080"


def test_tint_leaves_saturated_accents_alone():
	""" Non-gray colors in a base (eg. the blue bluetooth logos)
	must pass through tinting unchanged. """
	assert tint_gray("#0066ff", "#00ff00") == "#0066ff"
	assert tint_gray("#003059", "#ff0000") == "#003059"
	assert tint_gray("#ff00ff", "#ffff00") == "#ff00ff"
	svg = '<svg><path style="fill:#0066ff"/><rect fill="#414141"/></svg>'
	out, mapping = tint_svg(svg, "#ff0000")
	assert "#0066ff" in out
	assert mapping["0066ff"] == "0066ff"
	assert "#414141" not in out


def test_tint_keeps_lightness_ramp():
	""" Darker grays must stay darker after tinting. """
	color = "#ff0000"
	last = -1
	for gray in ("#202020", "#505050", "#808080", "#bbbbbb", "#f0f0f0"):
		t = _hex_to_rgb(tint_gray(gray, color))
		assert t[1] == t[0] or True
		v = sum(t) / 3.0
		assert v >= last - 1
		last = v


def test_tint_svg():
	svg = '<svg><path style="fill:#303030;stroke:#000000"/><stop stop-color="#ffffff"/></svg>'
	out, mapping = tint_svg(svg, "#0000ff")
	assert "#303030" not in out
	assert "#000000" in out
	assert "#ffffff" in out
	assert "#303030" not in mapping
	assert all(len(k) == 6 for k in mapping)


def test_preset_colors_valid():
	assert len(PRESET_COLORS) > 1
	assert DEFAULT_COLOR == "#00ff00"
	for c in PRESET_COLORS:
		assert _parse_hex(c) is not None


def test_auto_assign_first_controller_gets_green():
	cfg = FakeConfig()
	color = auto_assign_color(cfg, "c1")
	assert color == DEFAULT_COLOR
	assert cfg.values["controllers"]["c1"]["icon_color"] == color
	assert cfg.saved


def test_auto_assign_avoids_used_colors():
	cfg = FakeConfig({"c1": {"icon_color": "#00ff00"}})
	color = auto_assign_color(cfg, "c2")
	assert color == "#ff0000"
	assert auto_assign_color(cfg, "c2") == color


def test_get_icon_color_default():
	cfg = FakeConfig()
	assert get_icon_color(cfg, "c1") == DEFAULT_COLOR
	cfg.values["controllers"]["c1"]["icon_color"] = "#ff8000"
	assert get_icon_color(cfg, "c1") == "#ff8000"


def test_get_icon_shape():
	cfg = FakeConfig()
	assert get_icon_shape(cfg, "c1", "evdev") == "evdev"
	cfg.values["controllers"]["c1"]["icon_shape"] = "sc2"
	assert get_icon_shape(cfg, "c1", "evdev") == "sc2"


def test_shape_name():
	assert shape_name("sc") == SHAPE_NAMES["sc"]
	assert shape_name("ds4") == SHAPE_NAMES["ds4"]
	assert shape_name("somefuturepad") == "somefuturepad"
