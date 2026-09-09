"""Helpers shared by controller input-test previews."""

import re
from math import cos, sin, pi


INPUT_TEST_COLOR = "#FF003F9E"  # AARRGGBB


def rotate_input_vector(x, y, angle):
	"""Rotates an input vector by an SVG-space angle in degrees.

	Input coordinates use positive Y for up, while SVG uses positive Y for down.
	"""
	angle = float(angle) * pi / 180.0
	x, y = float(x), -float(y)
	return x * cos(angle) - y * sin(angle), x * sin(angle) + y * cos(angle)


def color_test_cursor_svg(svg, color=INPUT_TEST_COLOR):
	"""Colors black cursor artwork while retaining its gradient opacity."""
	if len(color) != 9 or not color.startswith("#"):
		raise ValueError("color must use #AARRGGBB format")
	return re.sub(r"#000000\b", "#" + color[-6:], svg, flags=re.IGNORECASE)


def render_test_cursor(filename, inverted=False, brightness=1.0):
	"""Renders a themed input-test cursor from its neutral black SVG source."""
	from scc.gui.svg_widget import SVGWidget
	with open(filename, "r") as fh:
		return SVGWidget.render_svg(color_test_cursor_svg(fh.read()), inverted, brightness)


def analog_hilight_color(color, value, maximum):
	"""Returns a base-to-highlight blend for an analog input value.
	"""
	if maximum <= 0:
		raise ValueError("maximum must be positive")
	if len(color) != 9 or not color.startswith("#"):
		raise ValueError("color must use #AARRGGBB format")
	amount = max(0.0, min(1.0, float(value) / maximum))
	return (color[-6:], amount) if amount else None


def set_observed_hilight(hilights, observed, what, color):
	"""Updates one observed input without disturbing non-observed highlights."""
	previous = observed.get(what)
	if previous == color:
		return False
	if previous is not None:
		hilights[previous].discard(what)
	if color is None:
		observed.pop(what, None)
	else:
		hilights.setdefault(color, set()).add(what)
		observed[what] = color
	return True
