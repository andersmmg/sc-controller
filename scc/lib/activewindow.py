#!/usr/bin/env python3
"""
SC-Controller - Active Window Provider

Returns title and class of currently focused window in a compositor-agnostic
way. Tries Wayland-native sources first, then X11.

Supported backends, in order:
 - Wayland - (see scc/lib/wlforeign.py)
 - GNOME   - org.gnome.Shell.Introspect D-Bus API
 - X11     - _NET_ACTIVE_WINDOW via xwrappers

Every provider returns (title, (wm_class, res_name)) or None if the active
window cannot be determined. Errors are swallowed and logged.
"""
from __future__ import unicode_literals

import os, logging

log = logging.getLogger("ActiveWindow")


def _norm(s):
	return None if s in (None, "") else str(s)


_OWN_WINDOWS = (
	"scc-daemon",
	"scc-autoswitch-daemon",
	"sc-controller",
)


def _is_own_window(name):
	if not name:
		return False
	if name in _OWN_WINDOWS or name.startswith("scc-osd-"):
		return True
	return name.endswith(".py") and name[:-3] in _OWN_WINDOWS


class _WaylandProvider(object):
	def __init__(self):
		self.tracker = None
		try:
			from scc.lib.wlforeign import WlForeignToplevels
			self.tracker = WlForeignToplevels()
		except Exception as e:
			log.debug("Wayland provider unavailable: %s", e)
			self.tracker = None

	def _available(self):
		return self.tracker is not None and self.tracker.is_ok()

	def get_active_window(self):
		if not self._available():
			return None
		try:
			w = self.tracker.poll()
		except Exception as e:
			log.debug("Wayland provider failed: %s", e)
			return None
		if w is None:
			return None
		app_id = _norm(w.get("app_id"))
		if _is_own_window(app_id):
			return None
		return (_norm(w.get("title")), (app_id, None))


class _GNOMEProvider(object):
	def __init__(self):
		self.proxy = None
		try:
			from gi.repository import Gio
			# DO_NOT_AUTO_START makes it fail when shell is not running
			self.proxy = Gio.DBusProxy.new_for_bus_sync(
				Gio.BusType.SESSION,
				Gio.DBusProxyFlags.DO_NOT_AUTO_START,
				None, "org.gnome.Shell", "/org/gnome/Shell/Introspect",
				"org.gnome.Shell.Introspect", None)
		except Exception as e:
			log.debug("GNOME Introspect unavailable: %s", e)
			self.proxy = None

	def _available(self):
		return self.proxy is not None

	def get_active_window(self):
		# a little messy but should work
		if not self._available():
			return None
		try:
			from gi.repository import Gio
			rv = self.proxy.call_sync("GetWindows", None,
				Gio.DBusCallFlags.NONE, 2000, None)
			windows = rv.unpack()[0]
			for props in windows.values():
				if props.get("has-focus"):
					klass = props.get("wm-class") or props.get("app-id")
					klass = _norm(klass)
					if _is_own_window(klass):
						return None
					return (_norm(props.get("title")), (klass, None))
			return None
		except Exception as e:
			if "denied" in str(e).lower() or "authorized" in str(e).lower():
				log.warning(
					"GNOME Shell denied Introspect access. Autoswitch needs"
					" to be allowlisted:\n"
					"  gsettings set org.gnome.shell introspect-allowlist"
					" \"['*']\"")
			else:
				log.debug("GNOME Introspect failed: %s", e)
			return None


class _X11Provider(object):
	def __init__(self):
		self.dpy = None
		display = os.environ.get("DISPLAY")
		if display:
			try:
				from scc.lib import xwrappers as X
				self.X = X
				self.dpy = X.open_display(display.encode("utf-8"))
			except Exception as e:
				log.debug("X11 provider unavailable: %s", e)
				self.dpy = None

	def _available(self):
		return self.dpy is not None

	def get_active_window(self):
		if not self._available():
			return None
		X = self.X
		try:
			win = X.get_current_window(self.dpy)
			if not win or win == X.get_default_root_window(self.dpy):
				return None
			title = X.get_window_title(self.dpy, win)
			klass = X.get_window_class(self.dpy, win)
			if title is None and klass == (None, None):
				return None
			if _is_own_window(klass[0]) or _is_own_window(klass[1]):
				return None
			return (title, klass)
		except Exception as e:
			log.debug("X11 provider failed: %s", e)
			return None


# Module state
_provider = None


def _find_provider():
	for c in (_WaylandProvider(), _GNOMEProvider(), _X11Provider()):
		if c._available():
			log.debug("Using %s as active-window provider",
					c.__class__.__name__)
			return c
	log.warning("No way to determine active window found")
	return None


def get_active_window():
	"""
	Returns (title, (wm_class, res_name)) of focused window, or None if it
	cannot be determined.
	"""
	global _provider
	if _provider is None:
		_provider = _find_provider()
	return _provider.get_active_window() if _provider else None


def get_provider_name():
	"""
	Returns name of provider that is (or would be) used, mostly just
	for logging.
	"""
	global _provider
	if _provider is None:
		_provider = _find_provider()
	return _provider.__class__.__name__ if _provider else "none"
