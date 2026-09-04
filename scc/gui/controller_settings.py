#!/usr/bin/env python2
"""
SC-Controller - Global Settings

Currently setups only one thing...
"""
from __future__ import unicode_literals
from scc.tools import _

from gi.repository import GLib, GdkPixbuf, Gdk, Gtk
from scc.gui import icon_tint
from scc.gui.svg_widget import SVGWidget
from scc.gui.userdata_manager import UserDataManager
from scc.gui.editor import Editor, ComboSetter

import os, logging
log = logging.getLogger("GS")

class ControllerSettings(Editor, UserDataManager, ComboSetter):
	GLADE = "controller_settings.glade"
	SWATCH_SIZE = 24

	def __init__(self, app, controller, profile_switcher=None):
		UserDataManager.__init__(self)
		self.app = app
		self.controller = controller
		self.profile_switcher = profile_switcher
		self.setup_widgets()
		self._swatches = {}
		self._selected_color = None
		self._icon_shape = None
		self.load_colors()
		self._timer = None
		self.app.config.reload()
		self.load_settings()
		self._eh_ids = ()


	def load_colors(self):
		""" Builds preset color swatches; picker comes from glade """
		fbColors = self.builder.get_object("fbColors")
		for color in icon_tint.PRESET_COLORS:
			fbColors.add(self._make_swatch(color))
		self._custom_button = self.builder.get_object("btCustomColor")
		fbColors.show_all()
		self.builder.get_object("imgPreview").set_size_request(140, 90)
		cboShape = self.builder.get_object("cboShape")
		cboShape.append("", _("Automatic"))
		for tp in icon_tint.available_shapes(self.app.imagepath):
			cboShape.append(tp, icon_tint.shape_name(tp))
		cboShape.connect('changed', self.on_shape_changed)


	def _make_swatch(self, color):
		""" Creates clickable circular color swatch widget """
		ev = Gtk.EventBox()
		img = Gtk.Image.new_from_pixbuf(self._swatch_pixbuf(color, False))
		ev.add(img)
		ev.set_valign(Gtk.Align.CENTER)
		ev.set_tooltip_text(color)
		ev.connect('button-press-event', self.on_swatch_clicked, color)
		self._swatches[color] = (ev, img)
		return ev


	def _swatch_pixbuf(self, color, selected):
		"""
		Renders circular color swatch pixbuf
		"""
		import math
		s = self.SWATCH_SIZE
		r_, g_, b_ = (int(color[i:i + 2], 16) for i in (1, 3, 5))
		ir_, ig_, ib_ = 255 - r_, 255 - g_, 255 - b_
		rad = (s - 6) / 2.0
		cx = cy = s / 2.0
		ring_inner = rad + 0.8
		ring_outer = rad + 2.6
		data = bytearray(s * s * 4)
		for y in range(s):
			for x in range(s):
				dx, dy = x + 0.5 - cx, y + 0.5 - cy
				d = math.sqrt(dx * dx + dy * dy)
				i = (y * s + x) * 4
				a = round(255 * max(0.0, min(1.0, rad - d + 0.5)))
				if a == 0 and selected and ring_inner <= d <= ring_outer:
					a = round(255 * min(1.0, ring_outer - d + 0.5,
							d - ring_inner + 0.5))
					data[i:i + 4] = bytes((ir_, ig_, ib_, a))
					continue
				data[i:i + 4] = bytes((r_, g_, b_, a))
		return GdkPixbuf.Pixbuf.new_from_data(bytes(data),
				GdkPixbuf.Colorspace.RGB, True, 8, s, s, s * 4, None, None)


	def select_color(self, color):
		""" Highlights chosen swatch, updates preview and config """
		color = color.lower()
		old = self._selected_color
		self._selected_color = color
		if old in self._swatches:
			ev, img = self._swatches[old]
			img.set_from_pixbuf(self._swatch_pixbuf(old, False))
		if color in self._swatches:
			ev, img = self._swatches[color]
			img.set_from_pixbuf(self._swatch_pixbuf(color, True))
		try:
			c = Gdk.RGBA()
			c.parse(color)
			self._custom_button.set_rgba(c)
		except:
			pass
		self._apply_icon_settings(self._icon_shape, color)


	def _apply_icon_settings(self, shape, color):
		"""
		Updates preview image, config (icon_shape and icon_color) and
		profile switcher icon.
		"""
		shape_path = icon_tint.find_base_icon(shape, self.app.imagepath) \
				if shape else None
		if shape_path is None:
			shape = None
			shape_path = icon_tint.find_base_icon(
					self.controller.get_type(), self.app.imagepath)
		imgPreview = self.builder.get_object("imgPreview")
		if shape_path is not None:
			pixbuf = SVGWidget.render_cropped_svg_file(
					shape_path, height=85, tint=color, max_width=140)
			imgPreview.set_from_pixbuf(pixbuf)
		if self._recursing:
			return
		cfg = self.app.config.get_controller_config(self.controller.get_id())
		cfg["icon_color"] = color
		cfg["icon_shape"] = shape or None
		if self.profile_switcher:
			self.profile_switcher.update_icon()
		self.schedule_save_config()


	def on_shape_changed(self, cb):
		if self._recursing: return
		self._icon_shape = cb.get_active_id() or ""
		self._apply_icon_settings(
				self._icon_shape, icon_tint.get_icon_color(
						self.app.config, self.controller.get_id()))


	def on_swatch_clicked(self, ev, event, color):
		if self._recursing: return
		self.select_color(color)


	def on_custom_color_set(self, cb, *a):
		if self._recursing: return
		c = cb.get_rgba()
		color = "#%02x%02x%02x" % (
				int(c.red * 255), int(c.green * 255), int(c.blue * 255))
		self.select_color(color)


	def on_Dialog_destroy(self, *a):
		for x in self._eh_ids:
			self.app.dm.disconnect(x)
		self._eh_ids = ()


	def on_btClearControlWith_clicked(self, *a):
		self.builder.get_object("cbControlWith").set_active(0)


	def on_btClearConfirmWith_clicked(self, *a):
		self.builder.get_object("cbConfirmWith").set_active(0)


	def on_btClearCancelWith_clicked(self, *a):
		self.builder.get_object("cbCancelWith").set_active(1)


	def on_exTouchpadRotation_activate(self, ex, *a):
		rvTouchpadRotation = self.builder.get_object("rvTouchpadRotation")
		rvTouchpadRotation.set_reveal_child(not ex.get_expanded())


	def on_exMenuButtons_activate(self, ex, *a):
		rvMenuButtons = self.builder.get_object("rvMenuButtons")
		rvMenuButtons.set_reveal_child(not ex.get_expanded())


	def on_btClearLeftRotation_clicked(self, *a):
		sclLeftRotation = self.builder.get_object("sclLeftRotation")
		sclLeftRotation.set_value(20)


	def on_btClearRightRotation_clicked(self, *a):
		sclRightRotation = self.builder.get_object("sclRightRotation")
		sclRightRotation.set_value(-20)


	def on_rotation_value_changed(self, *a):
		if self._recursing: return
		self.save_config()


	def load_settings(self):
		txName = self.builder.get_object("txName")
		sclLED = self.builder.get_object("sclLED")
		cbAlignOSD = self.builder.get_object("cbAlignOSD")
		sclIdleTimeout = self.builder.get_object("sclIdleTimeout")
		sclLeftRotation = self.builder.get_object("sclLeftRotation")
		sclRightRotation = self.builder.get_object("sclRightRotation")
		cbControlWith = self.builder.get_object("cbControlWith")
		cbConfirmWith = self.builder.get_object("cbConfirmWith")
		cbCancelWith = self.builder.get_object("cbCancelWith")

		cfg = self.app.config.get_controller_config(self.controller.get_id())

		self._recursing = True
		txName.set_text(cfg["name"] or "")
		sclLED.set_value(float(cfg["led_level"]))
		sclIdleTimeout.set_value(float(cfg["idle_timeout"]))
		sclLeftRotation.set_value(float(cfg["input_rotation_l"]))
		sclRightRotation.set_value(float(cfg["input_rotation_r"]))
		cbAlignOSD.set_active(cfg["osd_alignment"] != 0)
		self.set_cb(cbControlWith, cfg["menu_control"], keyindex=1)
		self.set_cb(cbConfirmWith, cfg["menu_confirm"], keyindex=1)
		self.set_cb(cbCancelWith, cfg["menu_cancel"], keyindex=1)
		cbConfirmWith.set_row_separator_func( lambda model, iter : model.get_value(iter, 0) == "-" )
		cbCancelWith.set_row_separator_func( lambda model, iter : model.get_value(iter, 0)  == "-" )
		cfg = self.app.config.get_controller_config(self.controller.get_id())
		color = icon_tint.get_icon_color(self.app.config, self.controller.get_id())
		self._icon_shape = cfg.get("icon_shape") or ""
		cboShape = self.builder.get_object("cboShape")
		cboShape.set_active_id(self._icon_shape) if self._icon_shape else cboShape.set_active(0)
		self.select_color(color)
		self._recursing = False


	def save_config(self, *a):
		""" Transfers settings from UI back to config """
		if self._recursing:
			return
		# Get widgets
		txName = self.builder.get_object("txName")
		sclLED = self.builder.get_object("sclLED")
		cbAlignOSD = self.builder.get_object("cbAlignOSD")
		sclIdleTimeout = self.builder.get_object("sclIdleTimeout")
		sclLeftRotation = self.builder.get_object("sclLeftRotation")
		sclRightRotation = self.builder.get_object("sclRightRotation")
		cbControlWith = self.builder.get_object("cbControlWith")
		cbConfirmWith = self.builder.get_object("cbConfirmWith")
		cbCancelWith = self.builder.get_object("cbCancelWith")

		# Store data
		cfg = self.app.config.get_controller_config(self.controller.get_id())
		cfg["name"] = txName.get_text()
		cfg["led_level"] = sclLED.get_value()
		cfg["osd_alignment"] = 1 if cbAlignOSD.get_active() else 0
		cfg["idle_timeout"] = sclIdleTimeout.get_value()
		cfg["input_rotation_l"] = sclLeftRotation.get_value()
		cfg["input_rotation_r"] = sclRightRotation.get_value()
		cfg["menu_control"] = cbControlWith.get_model().get_value(cbControlWith.get_active_iter(), 1)
		cfg["menu_confirm"] = cbConfirmWith.get_model().get_value(cbConfirmWith.get_active_iter(), 1)
		cfg["menu_cancel"] = cbCancelWith.get_model().get_value(cbCancelWith.get_active_iter(), 1)

		# Save (almost)
		self.schedule_save_config()


	def schedule_save_config(self, *a):
		"""
		Schedules config saving in 1s.
		Done to prevent literal madness when user moves slider.
		"""
		def cb(*a):
			self._timer = None
			self.app.save_config()

		if self._timer is not None:
			GLib.source_remove(self._timer)
		self._timer = GLib.timeout_add_seconds(1, cb)


	def on_sclIdleTimeout_format_value(self, scale, value):
		if value <= 180:	# 2 minutes
			return _("%s seconds") % int(value)
		if value % 60 == 0:
			return _("%s minutes") % int(value / 60)
		return _("%sm %ss") % (int(value / 60), int(value % 60))


	def on_sclLED_value_changed(self, scale, *a):
		if self._recursing: return
		cfg = self.app.config.get_controller_config(self.controller.get_id())
		cfg["led_level"] = scale.get_value()
		try:
			self.controller.set_led_level(scale.get_value())
		except IndexError:
			# Happens when there is no controller connected to daemon
			pass
		self.schedule_save_config()


	def on_sclIdleTimeout_value_changed(self, scale, *a):
		if self._recursing: return
		cfg = self.app.config.get_controller_config(self.controller.get_id())
		cfg["idle_timeout"] = scale.get_value()
		self.schedule_save_config()
