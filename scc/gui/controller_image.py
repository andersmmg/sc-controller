#!/usr/bin/env python3
"""
SC-Controller - Controller Image

Big, SVGWidget based widget with interchangeable controller and button images.
"""

import copy
import json
import logging
import os
from xml.etree import ElementTree as ET

from scc.constants import STICK_PAD_MAX, SCButtons
from scc.gui.svg_widget import XML_PARSER, SVGEditor, SVGWidget
from scc.tools import nameof

log = logging.getLogger("ContImage")


class ControllerImage(SVGWidget):
	DEFAULT = "sc"
	BUTTONS_WITH_IMAGES = (
		SCButtons.A,
		SCButtons.B,
		SCButtons.X,
		SCButtons.Y,
		SCButtons.BACK,
		SCButtons.C,
		SCButtons.START,
		SCButtons.DOTS,
	)

	DEFAULT_AXES = (
		# Shared between DS4 and Steam Controller
		"stick_x",
		"stick_y",
		"lpad_x",
		"lpad_x",
		"rpad_y",
		"rpad_y",
		"ltrig",
		"rtrig",
	)

	DEFAULT_BUTTONS = [nameof(x) for x in BUTTONS_WITH_IMAGES if x != SCButtons.DOTS] + [
		# Used only by Steam Controller
		nameof(SCButtons.LB),
		nameof(SCButtons.RB),
		nameof(SCButtons.LT),
		nameof(SCButtons.RT),
		nameof(SCButtons.STICKPRESS),
		nameof(SCButtons.RPAD),
		nameof(SCButtons.LPAD),
		nameof(SCButtons.LGRIP),
		nameof(SCButtons.RGRIP),
	]

	def __init__(self, app, config=None):
		self.app = app
		self.backup = None
		self.axis_positions = {}
		self.current = self._ensure_config({}, None)
		filename = self._make_controller_image_path(ControllerImage.DEFAULT)
		SVGWidget.__init__(self, filename)
		if config:
			self._controller_image.use_config(config)

	def _make_controller_image_path(self, img):
		return os.path.join(self.app.imagepath, "controller-images/%s.svg" % (img,))

	def get_config(self):
		"""
		Returns last used config
		"""
		return self.current

	def _ensure_config(self, data, controller):
		"""Ensure that required keys are present in config data"""
		data["gui"] = data.get("gui", {})
		data["gui"]["background"] = data["gui"].get("background", "sc")
		data["gui"]["buttons"] = data["gui"].get("buttons") or self._get_default_images()
		data["gui"]["no_buttons_in_gui"] = data["gui"].get("no_buttons_in_gui") or False
		data["buttons"] = data.get("buttons") or ControllerImage.DEFAULT_BUTTONS
		data["axes"] = data.get("axes") or ControllerImage.DEFAULT_AXES
		data["gyros"] = data.get("gyros", data["gui"]["background"] == "sc")
		return data

	@staticmethod
	def get_names(dict_or_tuple):
		"""
		There are three different ways how button and axis names are stored
		in config. This wrapper provides unified way to get list of them.
		"""
		if type(dict_or_tuple) in (list, tuple):
			return dict_or_tuple
		return [(x["axis"] if type(x) == dict else x) for x in dict_or_tuple.values()]

	def use_config(self, config, backup=None, controller=None):
		"""
		Loads controller settings from provided config, adding default values
		when needed. Returns same config.
		"""
		self.backup = backup
		self.current = self._ensure_config(config or {}, controller)
		self.axis_positions = {}
		self.set_image(
			os.path.join(self.app.imagepath, "controller-images/%s.svg" % (self.current["gui"]["background"],))
		)
		if not self.current["gui"]["no_buttons_in_gui"]:
			self._fill_button_images(self.current["gui"]["buttons"])
		self.hilight({})
		return self.current

	def set_axis_position(self, axis, x, y, redraw=True):
		"""Moves one analog-stick graphic to its normalized live position."""
		return self.set_axis_positions({axis: (x, y)}, redraw)

	def set_axis_positions(self, positions, redraw=True):
		"""Updates multiple stick positions and optionally renders one frame."""
		changed = False
		for axis, (x, y) in positions.items():
			position = (float(x), float(y))
			if self.axis_positions.get(axis) != position:
				self.axis_positions[axis] = position
				changed = True
		if changed and redraw:
			self.hilight(self._last_buttons)
		return changed

	def clear_axis_positions(self):
		"""Returns all animated sticks to their neutral artwork positions."""
		if self.axis_positions:
			self.axis_positions = {}
			self.hilight(self._last_buttons)

	def get_render_cache_id(self):
		return "sticks:%r|" % (tuple(sorted(self.axis_positions.items())),)

	def is_render_cacheable(self):
		return not self.axis_positions

	def get_render_svg(self):
		"""Applies temporary live stick translations without changing the SVG."""
		if not self.axis_positions:
			return self.current_svg
		tree = ET.fromstring(self.current_svg.encode("utf-8"), parser=XML_PARSER())
		SVGEditor.update_parents(tree)
		for axis, (x, y) in self.axis_positions.items():
			element = SVGEditor.get_element(tree, axis)
			if element is None:
				continue
			try:
				trash, trash, width, height = self.get_axis_region(axis)
			except ValueError:
				continue
			dx = x * width / STICK_PAD_MAX * 0.2
			dy = -y * height / STICK_PAD_MAX * 0.2
			parent_matrix = SVGEditor.IDENTITY
			parents = []
			parent = element.parent
			while parent is not None:
				parents.append(parent)
				parent = parent.parent
			for parent in reversed(parents):
				parent_matrix = SVGEditor.matrixmul(parent_matrix, SVGEditor.parse_transform(parent))
			a, b = parent_matrix[0][0], parent_matrix[1][0]
			c, d = parent_matrix[0][1], parent_matrix[1][1]
			determinant = a * d - b * c
			if determinant:
				dx, dy = ((d * dx - c * dy) / determinant, (-b * dx + a * dy) / determinant)
			transform = element.attrib.get("transform", "")
			element.attrib["transform"] = "translate(%s,%s) %s" % (dx, dy, transform)
		return ET.tostring(tree).decode("utf-8")

	def override_background(self, filename):
		"""
		Overrides background image setting. This changes config in place,
		so next time get_config is called, changed background is part of it.
		"""
		if self.backup is None:
			self.backup = copy.deepcopy(self.current)
		with open(os.path.join(self.app.imagepath, "%s.json" % (filename,))) as fh:
			data = json.loads(fh.read())
		self.current["gui"]["background"] = data["gui"]["background"]
		self.use_config(self.current, self.backup)

	def override_buttons(self, filename):
		"""
		Overrides button settings. This changes config in place,
		so next time get_config is called, changed background is part of it.
		"""
		if self.backup is None:
			self.backup = copy.deepcopy(self.current)
		with open(os.path.join(self.app.imagepath, "%s.json" % (filename,))) as fh:
			data = json.loads(fh.read())
		self.current["gui"]["buttons"] = data["gui"]["buttons"]
		self.current["buttons"] = data["buttons"]
		self.use_config(self.current, self.backup)

	def undo_override(self):
		"""Undoes override_* changes"""
		if self.backup is not None:
			self.use_config(self.backup, None)

	def get_button_groups(self):
		with open(os.path.join(self.app.imagepath, "button-images", "groups.json")) as fh:
			groups = json.loads(fh.read())
		return {x["key"]: x["buttons"] for x in groups if x["type"] == "buttons"}

	def _get_default_images(self):
		return self.get_button_groups()[ControllerImage.DEFAULT]

	def _fill_button_images(self, buttons):
		e = self.edit()
		SVGEditor.update_parents(e)
		target = SVGEditor.get_element(e, "controller")
		if target is None:
			log.warning("Controller image has no 'controller' element; skipping button overlays")
			e.commit()
			return
		target_x, target_y = SVGEditor.get_translation(target)
		no_glyph = self.current["gui"].get("no_glyph_buttons", [])
		for i in range(len(ControllerImage.BUTTONS_WITH_IMAGES)):
			b = nameof(ControllerImage.BUTTONS_WITH_IMAGES[i])
			if b in no_glyph:
				continue
			if b == "DOTS":
				# How did I managed to create this kind of special case? -_-
				i = 16
			path = None
			try:
				elm = SVGEditor.get_element(e, "AREA_%s" % (b,))
				if elm is None:
					if b in buttons:
						log.warning("Area for button %s not found", b)
					else:
						log.debug("Area for %s not found (button not in config)", b)
					continue
				x, y = SVGEditor.get_translation(elm)
				scale = 1.0
				if "scc-button-scale" in elm.attrib:
					w, h = SVGEditor.get_size(elm)
					scale = float(elm.attrib["scc-button-scale"])
					tw, th = w * scale, h * scale
					if scale < 1.0:
						x += (w - tw) * 0.5
						y += (h - th) * 0.5
					else:
						x -= (tw - w) * 0.25
						y -= (th - h) * 0.25
				path = os.path.join(self.app.imagepath, "button-images", "%s.svg" % (buttons[i],))
				img = SVGEditor.get_element(SVGEditor.load_from_file(path), "button")
				img.attrib["transform"] = "translate(%s, %s) scale(%s)" % (x - target_x, y - target_y, scale)
				img.attrib["id"] = b
				SVGEditor.add_element(target, img)
			except Exception as err:
				log.warning("Failed to add image for button %s (from %s)", b, path)
				log.exception(err)
		e.commit()
