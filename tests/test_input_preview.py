from xml.etree import ElementTree as ET

import pytest

from scc.gui.controller_image import ControllerImage
from scc.gui.input_test import (
	INPUT_TEST_COLOR,
	analog_hilight_color,
	color_test_cursor_svg,
	rotate_input_vector,
	set_observed_hilight,
)
from scc.gui.svg_widget import SVGEditor


def test_input_preview_rotation_uses_svg_coordinate_direction():
	assert rotate_input_vector(100, 0, 90) == pytest.approx((0, 100))
	assert rotate_input_vector(0, 100, 90) == pytest.approx((100, 0))
	assert rotate_input_vector(100, 0, -90) == pytest.approx((0, -100))


def test_cursor_svg_uses_the_shared_input_test_color():
	svg = '<stop style="stop-color:#000000;stop-opacity:0.9" />'

	assert "#" + INPUT_TEST_COLOR[-6:] in color_test_cursor_svg(svg)
	assert "stop-opacity:0.9" in color_test_cursor_svg(svg)


def test_analog_hilight_color_scales_alpha_and_clamps_input():
	color = "#FF60A0FF"

	assert analog_hilight_color(color, 0, 255) is None
	assert analog_hilight_color(color, 127.5, 255) == ("60A0FF", 0.5)
	assert analog_hilight_color(color, 255, 255) == ("60A0FF", 1.0)
	assert analog_hilight_color(color, 999, 255) == ("60A0FF", 1.0)
	assert analog_hilight_color(color, -1, 255) is None


@pytest.mark.parametrize(
	"color, maximum",
	[
		("#60A0FF", 255),
		("#FF60A0FF", 0),
	],
)
def test_analog_hilight_color_rejects_invalid_arguments(color, maximum):
	with pytest.raises(ValueError):
		analog_hilight_color(color, 1, maximum)


def test_svg_inversion_includes_cursor_gradient_stops():
	color = INPUT_TEST_COLOR[-6:].lower()
	tree = ET.fromstring('<svg><stop style="stop-color:%s" /></svg>' % color)

	SVGEditor.invert_colors(tree)

	assert "stop-color:%s" % SVGEditor._invert_color("#" + color) in tree[0].attrib["style"]


def test_svg_inversion_treats_omitted_shape_fill_as_black():
	tree = ET.fromstring('<svg><path d="M0 0" /></svg>')

	SVGEditor.invert_colors(tree)

	assert "fill:%s" % SVGEditor._invert_color("#000000") in tree[0].attrib["style"]


def test_svg_inversion_preserves_explicit_none_fill():
	tree = ET.fromstring('<svg><path style="fill:none" d="M0 0" /></svg>')

	SVGEditor.invert_colors(tree)

	assert tree[0].attrib["style"] == "fill:none"


def test_svg_blend_recolor_interpolates_from_base_to_highlight():
	element = ET.fromstring('<path style="fill:#204060;stroke:#000000" />')

	SVGEditor.blend_recolor(element, "#60a0ff", 0.5)

	assert "fill:#4070b0" in element.attrib["style"]
	assert "stroke:#000000" in element.attrib["style"]


def test_svg_blend_recolor_matches_normal_highlight_at_full_press():
	blended = ET.fromstring('<path style="fill:#204060;stroke:#000000;fill-opacity:0.3" />')
	highlighted = ET.fromstring('<path style="fill:#204060;stroke:#000000;fill-opacity:0.3" />')

	SVGEditor.blend_recolor(blended, "#60a0ff", 1.0)
	SVGEditor.recolor(highlighted, "#FF60a0ff")

	assert blended.attrib["style"] == highlighted.attrib["style"]


def test_controller_image_renders_temporary_stick_motion():
	image = ControllerImage.__new__(ControllerImage)
	image.current_svg = """<svg width=\"100\" height=\"100\">
		<circle id=\"STICK\" cx=\"50\" cy=\"50\" />
	</svg>"""
	image.axis_positions = {"STICK": (16383.5, -16383.5)}
	image.get_axis_region = lambda axis: (0, 0, 100, 100)

	tree = ET.fromstring(image.get_render_svg())
	stick = SVGEditor.get_element(tree, "STICK")
	assert stick.attrib["transform"] == "translate(10.0,10.0) "
	assert image.get_render_cache_id() != "sticks:()|"
	assert "transform" not in ET.fromstring(image.current_svg)[0].attrib


def test_observed_hilight_replaces_only_the_observed_color():
	selected = "#FF00FF00"
	base = "#FF60A0FF"
	hilights = {selected: {"LT"}, base: {"RT"}}
	observed = {"LT": base}

	assert set_observed_hilight(hilights, observed, "LT", "#8060A0FF")
	assert hilights[selected] == {"LT"}
	assert "LT" not in hilights[base]
	assert hilights["#8060A0FF"] == {"LT"}

	assert set_observed_hilight(hilights, observed, "LT", None)
	assert "LT" not in hilights["#8060A0FF"]
	assert "LT" not in observed
