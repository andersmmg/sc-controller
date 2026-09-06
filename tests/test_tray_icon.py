"""
Tests for tray icon dark/light mode support.
"""

import os
import xml.etree.ElementTree as ET

import pytest

from scc.gui.statusicon import StatusIcon
from scc.gui.svg_widget import SVGWidget

IMAGES = os.path.join(os.path.dirname(__file__), "..", "images")


class FakeApp(object):
	def __init__(self, mode, tmpdir):
		from scc.gui.app import App

		self.imagepath = IMAGES
		self.status = "alive"
		self._tray_needs_dark = None
		self._cached_tray_icons = {}
		self.config = {"gui": {"tray_icon_mode": mode}}
		self.get_tray_icon_file = App.get_tray_icon_file.__get__(self)
		self.is_dark_theme = App.is_dark_theme.__get__(self)


@pytest.fixture(autouse=True)
def cache_path(tmp_path, monkeypatch):
	import scc.gui.app

	monkeypatch.setattr(scc.gui.app, "get_cache_path", lambda: str(tmp_path))
	return tmp_path


def test_invert_svg_file_to_string():
	"""Inverting scc-alive.svg turns black fills into light ones"""
	data = SVGWidget.invert_svg_file_to_string(os.path.join(IMAGES, "scc-alive.svg"))
	assert data is not None
	tree = ET.fromstring(data)
	fills = [
		p.split(":", 1)[1]
		for el in tree.iter()
		if "style" in el.attrib
		for p in el.attrib["style"].split(";")
		if p.startswith("fill:#")
	]
	assert fills, "no hex fills found in inverted SVG"
	assert all(f.lower() != "#000000" for f in fills)


def test_invert_svg_file_missing():
	assert (
		SVGWidget.invert_svg_file_to_string(
			os.path.join(IMAGES, "scc-doesnotexist.svg")
		)
		is None
	)


def _paint_values(data):
	tree = ET.fromstring(data)
	vals = set()
	for el in tree.iter():
		for k in ("fill", "stroke"):
			v = el.attrib.get(k)
			if v:
				vals.add(v)
		if "style" in el.attrib:
			for part in el.attrib["style"].split(";"):
				if ":" in part:
					k, v = part.split(":", 1)
					if k in ("fill", "stroke"):
						vals.add(v)
	return vals


def test_invert_statusicon_current_color():
	data = SVGWidget.invert_svg_file_to_string(
		os.path.join(IMAGES, "scc-statusicon-alive.svg")
	)
	assert data is not None
	vals = _paint_values(data)
	assert "none" in vals
	assert "currentColor" not in vals
	assert any(v.startswith("#") and int(v[1:3], 16) > 128 for v in vals), (
		"stroke was not inverted: %s" % vals
	)


def test_tray_icon_light_mode_uses_original(tmp_path):
	app = FakeApp("light", tmp_path)
	assert app.get_tray_icon_file() == os.path.join(IMAGES, "scc-statusicon-alive.svg")
	assert app._tray_needs_dark is False


def test_tray_icon_dark_mode_creates_inverted_copy(tmp_path):
	app = FakeApp("dark", tmp_path)
	path = app.get_tray_icon_file()
	assert app._tray_needs_dark is True
	assert path.startswith(str(tmp_path))
	assert os.path.isfile(path)
	# Second call must reuse the cached file
	assert app.get_tray_icon_file() == path


def test_tray_icon_cache_reused_across_sessions(tmp_path):
	import time

	app = FakeApp("dark", tmp_path)
	path = app.get_tray_icon_file()
	assert os.path.isfile(path)
	t0 = os.path.getmtime(path)

	time.sleep(0.01)
	app = FakeApp("dark", tmp_path)  # fresh session, same artwork
	assert app.get_tray_icon_file() == path
	assert os.path.getmtime(path) == t0, "cache rewritten needlessly"


def test_tray_icon_cache_filename_tracks_artwork(tmp_path):
	"""Editing the artwork must change the cache filename"""
	app = FakeApp("dark", tmp_path)
	path1 = app.get_tray_icon_file()

	svg_path = os.path.join(IMAGES, "scc-statusicon-alive.svg")
	with open(svg_path, "r") as fh:
		orig = fh.read()
	with open(svg_path, "w") as fh:
		fh.write(orig.replace("</svg>", "<rect width='1' height='1'/></svg>"))
	try:
		app = FakeApp("dark", tmp_path)
		path2 = app.get_tray_icon_file()
		assert path2 != path1, "filename did not change after artwork edit"
		assert os.path.isfile(path2)
	finally:
		with open(svg_path, "w") as fh:
			fh.write(orig)


def test_tray_icon_system_mode_without_gtk_theme(tmp_path):
	app = FakeApp("system", tmp_path)
	path = app.get_tray_icon_file()
	assert path == os.path.join(IMAGES, "scc-statusicon-alive.svg")
	assert app._tray_needs_dark is not True


def test_tray_icon_falls_back_to_plain_icon(tmp_path):
	app = FakeApp("light", tmp_path)
	imgdir = tmp_path / "images"
	imgdir.mkdir()
	(imgdir / "scc-foo.svg").write_text("<svg/>")
	app.imagepath = str(imgdir)
	app.status = "foo"
	assert app.get_tray_icon_file() == str(imgdir / "scc-foo.svg")


def test_is_dark_theme_without_settings_or_window():
	app = FakeApp("system", None)
	assert app.is_dark_theme() is False


def test_is_dark_theme_prefers_dark_flag(monkeypatch):
	"""gtk-application-prefer-dark-theme=True forces dark"""
	import gi
	from gi.repository import Gtk

	class FakeSettings(object):
		@classmethod
		def get_default(cls):
			return cls()

		def get_property(self, name):
			assert name == "gtk-application-prefer-dark-theme"
			return True

	class FakeGtk(object):
		Settings = FakeSettings
		StateFlags = Gtk.StateFlags

		@staticmethod
		def get_default_settings():
			return FakeSettings()

	app = FakeApp("system", None)
	monkeypatch.setattr("scc.gui.app.Gtk", FakeGtk)
	assert app.is_dark_theme() is True


def test_tray_icon_unknown_status(tmp_path):
	app = FakeApp("dark", tmp_path)
	app.status = "doesnotexist"
	assert app.get_tray_icon_file() is None


def test_statusicon_icon_file_resolution(tmp_path):
	"""_get_icon_file resolves bundled SVGs and passes absolute paths through"""
	icon_dir = tmp_path / "icons"
	icon_dir.mkdir()
	(icon_dir / "scc-alive.svg").write_text("<svg/>")

	si = StatusIcon(str(icon_dir), None)
	assert si._get_icon_file("scc-alive") == str(icon_dir / "scc-alive.svg")
	assert si._get_icon_file("scc-missing") is None
	absolute = str(tmp_path / "dark.svg")
	assert si._get_icon_file(absolute) == absolute
