#!/usr/bin/env python3
"""
SC-Controller - Wayland foreign toplevel tracker

Minimal, dependency-free Wayland client that implements enough of the
standardized "zwlr_foreign_toplevel_management_unstable_v1" protocol to keep
track of opened windows and which one is currently focused.

Should work on most wayland compositors!

- Hyprland
- sway
- niri
- KWin (Plasma 6.1+)
- other wlroots-based compositors
"""
from __future__ import unicode_literals

import os, socket, struct, threading, logging

log = logging.getLogger("WlForeign")

IFACE_MANAGER_NAME = "zwlr_foreign_toplevel_manager_v1"
IFACE_MANAGER = IFACE_MANAGER_NAME.encode("utf-8")
MANAGER_VERSION = 1

WL_DISPLAY_ERROR = 0
WL_DISPLAY_DELETE_ID = 1
WL_DISPLAY_SYNC = 0
WL_DISPLAY_GET_REGISTRY = 1
WL_REGISTRY_BIND = 0
WL_REGISTRY_GLOBAL = 0
WL_REGISTRY_GLOBAL_REMOVE = 1
WL_CALLBACK_DONE = 0

MGR_TOPLEVEL = 0
MGR_FINISHED = 1

H_TITLE = 0
H_APP_ID = 1
H_OUTPUT_ENTER = 2
H_OUTPUT_LEAVE = 3
H_STATE = 4
H_DONE = 5
H_CLOSED = 6
H_PARENT = 7

STATE_MAXIMIZED = 0
STATE_MINIMIZED = 1
STATE_ACTIVATED = 2
STATE_FULLSCREEN = 3

SERVER_ID_BASE = 0xFF000000


class _Toplevel(object):
	""" State of single tracked toplevel (window) """
	__slots__ = ("id", "title", "app_id", "states")

	def __init__(self, obj_id):
		self.id = obj_id
		self.title = ""
		self.app_id = ""
		self.states = frozenset()


class WlForeignToplevels(object):
	"""
	Connects to compositor on its wayland socket and keeps dict of opened
	toplevel windows, updated from compositor events in background thread.
	"""

	CONNECT_TIMEOUT = 3.0

	def __init__(self):
		self._lock = threading.RLock()
		self._connected_evt = threading.Event()
		self._failed = False
		self._toplevels = {}  # object id -> _Toplevel
		self._supported = False

		self._sock = None
		self._buf = b""
		self._objects = {}  # object id -> (interface, handler)
		self._next_id = 2  # 1 is wl_display
		self._sync_flags = {}

		self._connect()
		self._thread = threading.Thread(target=self._run, daemon=True)
		self._thread.start()
		# Wait for initial round of toplevel events
		if not self._connected_evt.wait(self.CONNECT_TIMEOUT):
			self._set_failed("compositor did not respond in time")
		elif not self._supported:
			self._set_failed(
				"compositor does not support %s" % IFACE_MANAGER.decode())

	@staticmethod
	def _socket_path():
		name = os.environ.get("WAYLAND_DISPLAY") or "wayland-0"
		if name.startswith("/"):
			return name
		rtd = os.environ.get("XDG_RUNTIME_DIR")
		if not rtd:
			return None
		return os.path.join(rtd, name)

	def _connect(self):
		path = self._socket_path()
		if not path or not os.path.exists(path):
			self._set_failed("no wayland socket found")
			return
		try:
			self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
			self._sock.connect(path)
		except Exception as e:
			self._set_failed("failed to connect to %s: %s" % (path, e))
			return
		# Object 1 is wl_display; create registry
		registry_id = self._alloc_id()
		self._objects[1] = ("wl_display", self._on_display_event)
		self._objects[registry_id] = ("wl_registry", self._on_registry_event)
		self._send(1, WL_DISPLAY_GET_REGISTRY, "n", registry_id)

	def _alloc_id(self):
		obj_id = self._next_id
		self._next_id += 1
		return obj_id

	def _send(self, obj_id, opcode, sig="", *args):
		payload = b""
		for a, t in zip(args, sig):
			if t in "ui":
				payload += struct.pack("=i" if t == "i" else "=I", a)
			elif t == "s":
				data = a if isinstance(a, bytes) else a.encode("utf-8")
				payload += struct.pack("=I", len(data) + 1) + data + b"\0"
				while len(payload) % 4:
					payload += b"\0"
			elif t == "n":
				payload += struct.pack("=I", a)
		size = 8 + len(payload)
		header = struct.pack("=II", obj_id, (size << 16) | opcode)
		try:
			self._sock.sendall(header + payload)
		except Exception as e:
			self._set_failed("failed to send request: %s" % e)
			return False
		return True

	# Event handlers -----------------------------------------------------

	def _on_display_event(self, toplevel, opcode, reader):
		if opcode == WL_DISPLAY_ERROR:
			obj_id = reader.u()
			code = reader.u()
			message = reader.s()
			self._set_failed("wayland protocol error %s on object %s: %s" % (
				code, obj_id, message))
		elif opcode == WL_DISPLAY_DELETE_ID:
			obj_id = reader.u()
			with self._lock:
				self._objects.pop(obj_id, None)
				self._sync_flags.pop(obj_id, None)

	def _on_registry_event(self, toplevel, opcode, reader):
		if opcode == WL_REGISTRY_GLOBAL:
			name = reader.u()
			interface = reader.s()
			version = reader.u()
			if interface == IFACE_MANAGER_NAME:
				obj_id = self._alloc_id()
				# bind(name u, interface s, version u, new_id n)
				if self._send(toplevel, WL_REGISTRY_BIND, "usun",
						name, IFACE_MANAGER, min(version, MANAGER_VERSION), obj_id):
					with self._lock:
						self._objects[obj_id] = (
							IFACE_MANAGER, self._on_manager_event)
					self._supported = True
					log.debug("Bound foreign toplevel manager v%s (id %s)",
						min(version, MANAGER_VERSION), obj_id)
		elif opcode == WL_REGISTRY_GLOBAL_REMOVE:
			pass

	def _on_manager_event(self, toplevel, opcode, reader):
		if opcode == MGR_TOPLEVEL:
			obj_id = reader.u()
			t = _Toplevel(obj_id)
			with self._lock:
				self._objects[obj_id] = (b"handle", self._on_handle_event)
				self._toplevels[obj_id] = t
		elif opcode == MGR_FINISHED:
			self._set_failed("compositor finished foreign toplevel manager")

	def _on_handle_event(self, toplevel, opcode, reader):
		with self._lock:
			t = self._toplevels.get(toplevel)
			if t is None:
				return
			if opcode == H_TITLE:
				t.title = reader.s()
			elif opcode == H_APP_ID:
				t.app_id = reader.s()
			elif opcode == H_STATE:
				t.states = frozenset(reader.array_uints())
			elif opcode == H_CLOSED:
				self._toplevels.pop(toplevel, None)
				self._objects.pop(toplevel, None)
			# output_enter/leave, done and parent need no action here

	# Reading / dispatching ----------------------------------------------

	def _run(self):
		try:
			while self._sock is not None and not self._failed:
				try:
					# recv() without lock - holding it here would stall poll()
					data = self._sock.recv(4096)
				except OSError:
					break
				if not data:
					break
				with self._lock:
					self._buf += data
					self._dispatch()
				self._connected_evt.set()
		finally:
			self._close("connection closed")

	def _dispatch(self):
		""" Parses as much complete messages from self._buf as possible.
		Called with self._lock held. """
		buf = self._buf
		while len(buf) >= 8:
			obj_id, size_opcode = struct.unpack_from("=II", buf)
			size = size_opcode >> 16
			opcode = size_opcode & 0xFFFF
			if size < 8 or size % 4 != 0 or len(buf) < size:
				if size < 8 or size % 4 != 0:
					self._set_failed("malformed wayland message")
				break
			entry = self._objects.get(obj_id)
			if entry is not None:
				_, handler = entry
				try:
					handler(obj_id, opcode, _Reader(buf[8:size]))
				except Exception as e:
					self._set_failed("failed to parse wayland message: %s" % e)
					return
			buf = buf[size:]
		self._buf = buf

	def _set_failed(self, message):
		""" Marks tracker as failed and closes connection """
		with self._lock:
			if self._failed:
				return
			self._failed = True
		log.debug("%s", message)
		self._close(message)

	def _close(self, message):
		with self._lock:
			sock = self._sock
			self._sock = None
		if sock is not None:
			try:
				sock.close()
			except Exception:
				pass
		self._connected_evt.set()

	# Public API ---------------------------------------------------------

	def is_ok(self):
		return self._sock is not None and self._supported and not self._failed

	def poll(self):
		"""
		Returns dict with 'title' and 'app_id' of currently activated window,
		or None if none is focused or tracker isnt working.
		"""
		if not self.is_ok():
			return None
		with self._lock:
			for t in self._toplevels.values():
				if STATE_ACTIVATED in t.states:
					return { "title": t.title, "app_id": t.app_id }
		return None


class _Reader(object):
	""" Sequential reader for message arguments """
	__slots__ = ("data", "pos")

	def __init__(self, data):
		self.data = data
		self.pos = 0

	def _take(self, count):
		if self.pos + count > len(self.data):
			raise IOError("truncated wayland message")
		rv = self.data[self.pos:self.pos + count]
		self.pos += count
		return rv

	def u(self):
		return struct.unpack("=I", self._take(4))[0]

	def s(self):
		length = self.u()
		data = self._take(length)
		return data.rstrip(b"\0").decode("utf-8", "replace")

	def array_uints(self):
		length = self.u()
		data = self._take(length)
		return list(struct.unpack("=%sI" % (length // 4), data))


if __name__ == "__main__":
	# basic testing, normally not used
	logging.basicConfig(level=logging.DEBUG)
	w = WlForeignToplevels()
	print("ok:", w.is_ok())
	import time
	while True:
		print(w.poll())
		time.sleep(1)
