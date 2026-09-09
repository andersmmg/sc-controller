#!/usr/bin/env python3
"""Shared transport-level smoothing for controller input state objects."""

from collections import deque

from scc.constants import SCButtons


DEFAULT_WINDOW = 3
DEFAULT_ANALOG_FIELDS = (
	"ltrig", "rtrig", "stick_x", "stick_y", "rstick_x", "rstick_y",
	"lpad_x", "lpad_y", "rpad_x", "rpad_y", "cpad_x", "cpad_y",
)


class InputSmoother(object):
	"""Rolling average that preserves button and touch contact edges."""

	def __init__(self, fields=DEFAULT_ANALOG_FIELDS, window=DEFAULT_WINDOW):
		self.fields = tuple(fields)
		self.history = deque(maxlen=window)
		self.previous = None


	@staticmethod
	def _copy(state):
		if hasattr(state, "_replace"):
			return state._replace()
		copy = type(state)()
		for name, _ in state._fields_:
			setattr(copy, name, getattr(state, name))
		return copy


	def process(self, state, fallback_old=None):
		"""Returns the previous smoothed state and the smoothed current state."""
		raw = self._copy(state)
		self.history.append(raw)
		current = self._copy(raw)
		if len(self.history) > 1:
			values = {
				name: round(sum(getattr(item, name) for item in self.history)
					/ len(self.history))
				for name in self.fields if hasattr(current, name)
			}
			current = self._updated(current, values)
			current = self._preserve_touch_edges(current, raw)

		old = self.previous if self.previous is not None else fallback_old
		self.previous = current
		return old, current


	@staticmethod
	def _updated(state, values):
		if hasattr(state, "_replace"):
			return state._replace(**values)
		for name, value in values.items():
			setattr(state, name, value)
		return state


	def _preserve_touch_edges(self, current, raw):
		previous = self.history[-2]
		current = self._smooth_touch(current, raw, previous,
			SCButtons.LPADTOUCH, ("lpad_x", "lpad_y"))
		return self._smooth_touch(current, raw, previous,
			SCButtons.RPADTOUCH, ("rpad_x", "rpad_y"))


	def _smooth_touch(self, current, raw, previous, mask, fields):
		if not all(hasattr(current, name) for name in fields):
			return current
		touched = bool(raw.buttons & mask)
		was_touched = bool(previous.buttons & mask)
		if not touched:
			values = {name: 0 for name in fields}
		elif not was_touched:
			values = {name: getattr(raw, name) for name in fields}
		else:
			samples = [item for item in self.history if item.buttons & mask]
			values = {
				name: round(sum(getattr(item, name) for item in samples)
					/ len(samples))
				for name in fields
			}
		return self._updated(current, values)
