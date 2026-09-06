import gi
gi.require_version("Gtk", "3.0")

import os
from scc.gui.svg_widget import SVGWidget

IMG = os.path.join("images", "scc-alive.svg")


def setup_function(function):
	SVGWidget._pixbuf_cache.clear()


def teardown_function(function):
	SVGWidget._pixbuf_cache.clear()


def test_render_svg_file_cached():
	p1 = SVGWidget.render_svg_file(IMG, False, 1.0)
	p2 = SVGWidget.render_svg_file(IMG, False, 1.0)
	assert p1 is p2, "same file and args should return cached pixbuf"


def test_render_svg_file_args_separated():
	p1 = SVGWidget.render_svg_file(IMG, True, 0.9)
	p2 = SVGWidget.render_svg_file(IMG, False, 1.0)
	assert p1 is not p2
	assert len(SVGWidget._pixbuf_cache) == 2


def test_render_cropped_svg_file_cached():
	p1 = SVGWidget.render_cropped_svg_file(IMG, height=24, tint="#ff0000")
	p2 = SVGWidget.render_cropped_svg_file(IMG, height=24, tint="#ff0000")
	assert p1 is p2
	assert p1.get_width() > 0


def test_cropped_and_plain_do_not_share_entry():
	p1 = SVGWidget.render_svg_file(IMG, False, 1.0, size=(256, 256))
	p2 = SVGWidget.render_cropped_svg_file(IMG, height=24)
	assert p1 is not p2
	assert len(SVGWidget._pixbuf_cache) == 2


def test_mtime_change_invalidates(tmp_path):
	src = tmp_path / "icon.svg"
	src.write_text(ET_SVG)
	p = str(src)

	p1 = SVGWidget.render_svg_file(p, False, 1.0)
	t0 = os.stat(p).st_mtime_ns
	os.utime(p, ns=(t0 + 10_000_000, t0 + 10_000_000))
	p2 = SVGWidget.render_svg_file(p, False, 1.0)
	assert p1 is not p2, "modified file must be re-rendered"


def test_cache_bounded_and_lru():
	old = SVGWidget.PIXBUF_CACHE_SIZE
	SVGWidget.PIXBUF_CACHE_SIZE = 5
	try:
		for i in range(5):
			SVGWidget._cached_render(("k", i), lambda: "fake")
		SVGWidget._cached_render(("k", 0), lambda: "fake")  # touch oldest
		for i in range(4):
			SVGWidget._cached_render(("n", i), lambda: "fake")
		assert len(SVGWidget._pixbuf_cache) == 5
		assert ("k", 0) in SVGWidget._pixbuf_cache, "touched key should survive"
		assert ("k", 1) not in SVGWidget._pixbuf_cache, "oldest key should be evicted"
	finally:
		SVGWidget.PIXBUF_CACHE_SIZE = old


def test_failed_render_not_cached():
	calls = []

	def failing():
		calls.append(1)
		raise OSError("boom")

	try:
		SVGWidget._cached_render(("bad",), failing)
	except OSError:
		pass
	assert ("bad",) not in SVGWidget._pixbuf_cache
	assert len(calls) == 1


ET_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">
	<rect x="1" y="1" width="14" height="14" style="fill:#000000"/>
</svg>
"""
