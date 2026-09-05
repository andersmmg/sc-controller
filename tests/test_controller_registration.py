"""
Tests for axis test-region geometry (SVGWidget.get_axis_region).

Uses only synthetic SVGs so the tests stay independent of the bundled
controller images.
"""
import pytest

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Rsvg", "2.0")
from scc.gui.svg_widget import SVGWidget

SVG_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"
	version="1.1" id="svg2">
	<rect id="AREA_%s" x="%g" y="%g" width="%g" height="%g"
		style="fill:none" />
	%s
</svg>
"""


def _widget_with_areas(tmp_path, name, base, test):
	fn = tmp_path / name
	fn.write_text(SVG_TEMPLATE % (base + test[0], test[1], test[2],
		test[3], test[4], ""))
	return SVGWidget(str(fn))


def test_square_test_area_used_directly(tmp_path):
	w = _widget_with_areas(tmp_path, "square.svg", "DPAD",
		("TEST", 105, 205, 50, 50))
	assert w.get_axis_region("DPAD") == (105.0, 205.0, 50.0, 50.0)


def test_line_test_area_makes_centered_square(tmp_path):
	w = _widget_with_areas(tmp_path, "line.svg", "STICK",
		("TEST", 30, 168, 72, 1))
	x, y, cw, ch = w.get_axis_region("STICK")
	assert (x, cw, ch) == (30.0, 72.0, 72.0)
	assert y + ch * 0.5 == pytest.approx(168.5, abs=0.6)
	assert y == pytest.approx(168.5 - 36.0, abs=0.6)


def test_thin_but_not_line_test_area_counts_as_square(tmp_path):
	w = _widget_with_areas(tmp_path, "thin.svg", "LPAD",
		("TEST", 5, 5, 80, 3))
	assert w.get_axis_region("LPAD") == (5.0, 5.0, 80.0, 3.0)


def test_missing_test_area_raises(tmp_path):
	w = _widget_with_areas(tmp_path, "missing.svg", "LPAD",
		("", 0, 0, 10, 10))
	with pytest.raises(ValueError):
		w.get_axis_region("STICK")


def test_passing_full_test_name_raises(tmp_path):
	# get_axis_region() takes the base name and appends "TEST" itself;
	# callers must not pass an already-suffixed name
	w = _widget_with_areas(tmp_path, "named.svg", "STICK",
		("TEST", 10, 20, 60, 1))
	with pytest.raises(ValueError):
		w.get_axis_region("STICKTEST")
