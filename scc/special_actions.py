#!/usr/bin/env python3
"""
SC Controller - Special Actions

Special Action is "special" since it cannot be handled by mapper alone.
Instead, on_sa_<actionname> method on handler instance set by
mapper.set_special_actions_handler() is called to do whatever action is supposed
to do. If handler is not set, or doesn't have reqiuired method defined,
action only prints warning to console.
"""

import logging
import sys
from difflib import get_close_matches
from math import sqrt
from typing import override

from scc.actions import Action, HapticEnabledAction, OSDEnabledAction, SpecialAction
from scc.constants import DEFAULT, LEFT, RIGHT, SAME, STICK, STICK_PAD_MAX, SCButtons
from scc.modifiers import Modifier
from scc.tools import clamp, nameof, string_escape, strip_gesture

log = logging.getLogger("SActions")
_ = lambda x: x

unicode = str  # Python 2 compatibility alias


class ChangeProfileAction(Action, SpecialAction):
	SA = COMMAND = "profile"

	def __init__(self, profile):
		Action.__init__(self, profile)
		self.profile = profile

	@override
	def describe(self, context):
		if self.name:
			return self.name
		if context == Action.AC_OSD:
			return _("Profile: %s") % (self.profile,)
		if context == Action.AC_SWITCHER:
			return _("Switch to %s") % (self.profile,)
		return _("Profile Change")

	@override
	def get_compatible_modifiers(self):
		return Action.MOD_OSD

	@override
	def to_string(self, multiline=False, pad=0):
		return (" " * pad) + f"{self.COMMAND}('{string_escape(self.profile)}')"

	@override
	def button_press(self, mapper):
		pass

	@override
	def button_release(self, mapper):
		# Execute only when button is released (executing this when button
		# is pressed would send following button_release event to another
		# action from loaded profile)
		self.execute(mapper)

	@override
	def whole(self, mapper, x, y, what):
		self.execute(mapper)


class ShellCommandAction(Action, SpecialAction):
	SA = COMMAND = "shell"

	def __init__(self, command):
		if isinstance(command, bytes):
			command = command.decode("unicode_escape")
		assert type(command) == unicode
		Action.__init__(self, command)
		self.command = command

	@override
	def describe(self, context):
		if self.name:
			return self.name
		return _("Execute Command")

	@override
	def get_compatible_modifiers(self):
		return Action.MOD_OSD

	@override
	def to_string(self, multiline=False, pad=0):
		return (" " * pad) + f"{self.COMMAND}('{string_escape(self.parameters[0])}')"

	@override
	def button_press(self, mapper):
		# Executes only when button is pressed
		return self.execute(mapper)

	@override
	def button_release(self, mapper):
		pass


class TurnOffAction(Action, SpecialAction):
	SA = COMMAND = "turnoff"

	def __init__(self):
		Action.__init__(self)

	@override
	def describe(self, context):
		if self.name:
			return self.name
		if context == Action.AC_OSD:
			return _("Turning controller OFF")
		return _("Turn Off the Controller")

	@override
	def to_string(self, multiline=False, pad=0):
		return (" " * pad) + f"{self.COMMAND}()"

	@override
	def get_compatible_modifiers(self):
		return Action.MOD_OSD

	@override
	def button_release(self, mapper):
		# Execute only when button is released (executing this when button
		# is pressed would hold stuck any other action bound to same button,
		# as button_release is not sent after controller turns off)
		self.execute(mapper)

	@override
	def whole(self, mapper, x, y, what):
		self.execute(mapper)


class RestartDaemonAction(Action, SpecialAction):
	SA = COMMAND = "restart"
	ALIASES = ("exit",)

	def __init__(self):
		Action.__init__(self)

	@override
	def describe(self, context):
		if self.name:
			return self.name
		return _("Restart SCC-Daemon")

	@override
	def to_string(self, multiline=False, pad=0):
		return (" " * pad) + f"{self.COMMAND}()"

	@override
	def button_release(self, mapper):
		# Execute only when button is released (for same reason as
		# TurnOffAction does)
		self.execute(mapper)


class LedAction(Action, SpecialAction):
	SA = COMMAND = "led"

	def __init__(self, brightness):
		Action.__init__(self, brightness)
		self.brightness = clamp(0, int(brightness), 100)

	@override
	def describe(self, context):
		if self.name:
			return self.name
		return _("Set LED brightness")

	@override
	def get_compatible_modifiers(self):
		return Action.MOD_OSD

	@override
	def button_press(self, mapper):
		# Execute only when button is pressed
		self.execute(mapper)


class OSDAction(Action, SpecialAction):
	"""
	Displays text in OSD, or, if used as modifier, displays action description
	and executes that action.
	"""

	SA = COMMAND = "osd"
	DEFAULT_TIMEOUT = 5
	DEFAULT_SIZE = 3
	PROFILE_KEY_PRIORITY = -5  # After XYAction, but beforee everything else

	def __init__(self, *parameters):
		Action.__init__(self, *parameters)
		self.action = None
		self.timeout = self.DEFAULT_TIMEOUT
		self.size = self.DEFAULT_SIZE
		if len(parameters) > 1 and type(parameters[0]) in (int, float):
			# timeout parameter included
			self.timeout = float(parameters[0])
			parameters = parameters[1:]
		if len(parameters) > 1 and type(parameters[0]) in (int, float):
			# size parameter included
			self.size = int(parameters[0])
			parameters = parameters[1:]
		if isinstance(parameters[0], Action):
			self.action = parameters[0]
			self.text = self.action.describe(Action.AC_OSD)
		else:
			self.text = unicode(parameters[0])
		if self.action and isinstance(self.action, OSDEnabledAction):
			self.action.enable_osd(self.timeout)

	@override
	def get_compatible_modifiers(self):
		if self.action:
			return self.action.get_compatible_modifiers()
		return 0

	@staticmethod
	def decode(data, a, *b):
		a = OSDAction(a)
		if data["osd"] is not True:
			a.timeout = float(data["osd"])
		return a

	@override
	def describe(self, context):
		if self.name:
			return self.name
		if self.action:
			return _("%s (with OSD)") % (self.action.describe(context),)
		if context == Action.AC_OSD:
			return _(f"Display '{self.text}'")
		return _("OSD Message")

	@override
	def to_string(self, multiline=False, pad=0):
		parameters = []
		if self.timeout != self.DEFAULT_TIMEOUT or self.size != self.DEFAULT_SIZE:
			parameters.append(str(self.timeout))
		if self.size != self.DEFAULT_SIZE:
			parameters.append(str(self.size))
		if self.action:
			parameters.append(self.action.to_string(multiline=multiline, pad=pad))
		else:
			parameters.append(f"'{string_escape(str(self.text))}'")
		return (" " * pad) + "{}({})".format(self.COMMAND, ",".join(parameters))

	@override
	def strip(self):
		if self.action:
			return self.action.strip()
		return self

	@override
	def compress(self):
		if self.action:
			if isinstance(self.action, OSDEnabledAction):
				return self.action.compress()
			self.action = self.action.compress()
		return self

	@override
	def button_press(self, mapper):
		self.execute(mapper)
		if self.action:
			return self.action.button_press(mapper)
		return None

	@override
	def button_release(self, mapper):
		if self.action:
			return self.action.button_release(mapper)
		return None

	@override
	def trigger(self, mapper, position, old_position):
		if self.action:
			return self.action.trigger(mapper, position, old_position)
		return None

	@override
	def axis(self, mapper, position, what):
		if self.action:
			return self.action.axis(mapper, position, what)
		return None

	@override
	def pad(self, mapper, position, what):
		if self.action:
			return self.action.pad(mapper, position, what)
		return None

	@override
	def whole(self, mapper, x, y, what):
		if self.action:
			return self.action.whole(mapper, x, y, what)
		return None


class ClearOSDAction(Action, SpecialAction):
	"""
	Clears all windows from OSD layer. Cancels all menus, clears all messages,
	etc, etc.
	"""

	SA = COMMAND = "clearosd"

	@override
	def describe(self, context):
		return _("Hide all OSD Menus and Messages")

	@override
	def button_press(self, mapper):
		self.execute(mapper)


class MenuAction(Action, SpecialAction, HapticEnabledAction):
	"""
	Displays menu defined in profile or globally.
	"""

	SA = COMMAND = "menu"
	MENU_TYPE = "menu"
	MIN_STICK_DISTANCE = STICK_PAD_MAX / 3
	DEFAULT_POSITION = 10, -10

	def __init__(
		self, menu_id, control_with=DEFAULT, confirm_with=DEFAULT, cancel_with=DEFAULT, show_with_release=False, size=0
	):
		if control_with == SAME:
			# Little touch of backwards compatibility
			control_with, confirm_with = DEFAULT, SAME
		if type(control_with) == int:
			# Allow short form in case when menu is assigned to pad
			# eg.: menu("some-id", 3) sets size to 3
			control_with, size = DEFAULT, control_with
		Action.__init__(self, menu_id, control_with, confirm_with, cancel_with, show_with_release, size)
		HapticEnabledAction.__init__(self)
		self.menu_id = menu_id
		self.control_with = control_with
		self.confirm_with = confirm_with
		self.cancel_with = cancel_with
		self.size = size
		self.x, self.y = MenuAction.DEFAULT_POSITION
		self.show_with_release = bool(show_with_release)
		self._stick_distance = 0

	@override
	def describe(self, context):
		if self.name:
			return self.name
		return _("Menu")

	@override
	def get_compatible_modifiers(self):
		return Action.MOD_FEEDBACK

	@override
	def to_string(self, multiline=False, pad=0):
		if self.control_with == DEFAULT:
			dflt = (DEFAULT, DEFAULT, False)
			vals = (self.confirm_with, self.cancel_with, self.show_with_release)
			if dflt == vals:
				# Special case when menu is assigned to pad
				if self.size == 0:
					return "{}{}('{}')".format(" " * pad, self.COMMAND, self.menu_id)
				return "{}{}('{}', {})".format(" " * pad, self.COMMAND, self.menu_id, self.size)

		return "{}{}({})".format(" " * pad, self.COMMAND, ",".join(Action.encode_parameters(self.strip_defaults())))

	@override
	def get_previewable(self):
		return True

	@override
	def button_press(self, mapper):
		if not self.show_with_release:
			confirm_with = self.confirm_with
			cancel_with = self.cancel_with
			args = [mapper]
			if confirm_with == SAME:
				confirm_with = mapper.get_pressed_button() or DEFAULT
			elif confirm_with == DEFAULT:
				confirm_with = DEFAULT
			if cancel_with == DEFAULT:
				cancel_with = DEFAULT
			if nameof(self.control_with) in (LEFT, RIGHT):
				args += ["--use-cursor"]
			args += [
				"--control-with",
				nameof(self.control_with),
				"-x",
				str(self.x),
				"-y",
				str(self.y),
				"--size",
				str(self.size),
				"--confirm-with",
				nameof(confirm_with),
				"--cancel-with",
				nameof(cancel_with),
			]
			self.execute(*args)

	@override
	def button_release(self, mapper):
		if self.show_with_release:
			self.execute(mapper, "-x", str(self.x), "-y", str(self.y))

	@override
	def whole(self, mapper, x, y, what, *params):
		if x == 0 and y == 0:
			# Sent when pad is released - don't display menu then
			return
		if self.haptic:
			params = [*list(params), "--feedback-amplitude", str(self.haptic.get_amplitude())]
		if what in (LEFT, RIGHT):
			confirm_with = self.confirm_with
			cancel_with = self.cancel_with
			if what == LEFT:
				if confirm_with == DEFAULT:
					confirm_with = SCButtons.LPAD
				if cancel_with == DEFAULT:
					cancel_with = SCButtons.LPADTOUCH
			elif what == RIGHT:
				if confirm_with == DEFAULT:
					confirm_with = SCButtons.RPAD
				if cancel_with == DEFAULT:
					cancel_with = SCButtons.RPADTOUCH
			else:
				# Stick
				if confirm_with == DEFAULT:
					confirm_with = SCButtons.STICKPRESS
				if cancel_with == DEFAULT:
					cancel_with = SCButtons.B
			if not mapper.was_pressed(cancel_with):
				self.execute(
					mapper,
					"--control-with",
					what,
					"-x",
					str(self.x),
					"-y",
					str(self.y),
					"--use-cursor",
					"--size",
					str(self.size),
					"--confirm-with",
					nameof(confirm_with),
					"--cancel-with",
					nameof(cancel_with),
					*params,
				)
		if what == STICK:
			# Special case, menu is displayed only if is moved enought
			distance = sqrt(x * x + y * y)
			if self._stick_distance < MenuAction.MIN_STICK_DISTANCE and distance > MenuAction.MIN_STICK_DISTANCE:
				self.execute(
					mapper,
					"--control-with",
					STICK,
					"-x",
					str(self.x),
					"-y",
					str(self.y),
					"--use-cursor",
					"--size",
					str(self.size),
					"--confirm-with",
					"STICKPRESS",
					"--cancel-with",
					STICK,
					*params,
				)
			self._stick_distance = distance


class HorizontalMenuAction(MenuAction):
	"""
	Same as menu, but packed as row
	"""

	COMMAND = "hmenu"
	MENU_TYPE = "hmenu"


class GridMenuAction(MenuAction):
	"""
	Same as menu, but displayed in grid
	"""

	COMMAND = "gridmenu"
	MENU_TYPE = "gridmenu"


class QuickMenuAction(MenuAction):
	"""
	Quickmenu. Max.6 items, controller by buttons
	"""

	COMMAND = "quickmenu"
	MENU_TYPE = "quickmenu"

	@override
	def describe(self, context):
		if self.name:
			return self.name
		return _("QuickMenu")

	@override
	def button_press(self, mapper):
		# QuickMenu is always shown with release
		pass

	@override
	def button_release(self, mapper):
		self.execute(mapper, "-x", str(self.x), "-y", str(self.y))


class RadialMenuAction(MenuAction):
	"""
	Same as grid menu, which is same as menu but displayed in grid,
	but displayed as circle.
	"""

	COMMAND = "radialmenu"
	MENU_TYPE = "radialmenu"

	def __init__(
		self, menu_id, control_with=DEFAULT, confirm_with=DEFAULT, cancel_with=DEFAULT, show_with_release=False, size=0
	):
		MenuAction.__init__(self, menu_id, control_with, confirm_with, cancel_with, show_with_release, size)
		self.rotation = 0

	@override
	def whole(self, mapper, x, y, what, *params):
		if self.rotation:
			MenuAction.whole(self, mapper, x, y, what, "--rotation", self.rotation)
		else:
			MenuAction.whole(self, mapper, x, y, what)

	def set_rotation(self, angle):
		self.rotation = angle

	@override
	def get_compatible_modifiers(self):
		return MenuAction.get_compatible_modifiers(self) or Action.MOD_ROTATE


class DialogAction(Action, SpecialAction):
	"""
	Dialog is actually kind of menu, but options for it are different.
	"""

	SA = COMMAND = "dialog"
	DEFAULT_POSITION = 10, -10

	def __init__(self, *pars):
		Action.__init__(self, pars)

		self.options = []
		self.confirm_with = DEFAULT
		self.cancel_with = DEFAULT
		self.text = _("Dialog")
		self.x, self.y = MenuAction.DEFAULT_POSITION
		# First and 2nd parameter may be confirm and cancel button
		if len(pars) > 0 and pars[0] in SCButtons:
			self.confirm_with, pars = pars[0], pars[1:]
			if len(pars) > 0 and pars[0] in SCButtons:
				self.cancel_with, pars = pars[0], pars[1:]
		# 1st always present argument is title
		if len(pars) > 0:
			self.text, pars = pars[0], pars[1:]
		# ... everything else are actions
		self.options = pars

	@override
	def describe(self, context):
		if self.name:
			return self.name
		return _("Dialog")

	@override
	def to_string(self, multiline=False, pad=0):
		rv = "{}{}(".format(" " * pad, self.COMMAND)
		if self.confirm_with != DEFAULT:
			rv += f"{nameof(self.confirm_with)}, "
			if self.cancel_with != DEFAULT:
				rv += f"{nameof(self.cancel_with)}, "
		rv += f"'{string_escape(self.text)}', "
		if multiline:
			rv += "\n%s" % (" " * (pad + 2))
		for option in self.options:
			rv += f"{option.to_string(False)}, "
			if multiline:
				rv += "\n%s" % (" " * (pad + 2))

		rv = rv.strip("\n ,")
		if multiline:
			rv += "\n)"
		else:
			rv += ")"
		return rv

	@override
	def get_previewable(self):
		return False

	@override
	def button_release(self, mapper):
		confirm_with = self.confirm_with
		cancel_with = self.cancel_with
		args = [
			mapper,
			"-x",
			str(self.x),
			"-y",
			str(self.y),
			"--confirm-with",
			nameof(confirm_with),
			"--cancel-with",
			nameof(cancel_with),
			"--text",
			self.text,
		]
		args.extend(self.options)
		self.execute(*args)


class KeyboardAction(Action, SpecialAction):
	"""
	Shows OSD keyboard.
	"""

	SA = COMMAND = "keyboard"

	def __init__(self):
		Action.__init__(self)

	@override
	def get_compatible_modifiers(self):
		return Action.MOD_POSITION

	@override
	def describe(self, context):
		if self.name:
			return self.name
		if context == Action.AC_OSD:
			return _("Display Keyboard")
		return _("OSD Keyboard")

	@override
	def to_string(self, multiline=False, pad=0):
		return (" " * pad) + f"{self.COMMAND}()"

	@override
	def button_press(self, mapper):
		self.execute(mapper)


class PositionModifier(Modifier):
	"""
	Sets position for OSD menu.
	"""

	COMMAND = "position"

	@override
	def _mod_init(self, x=0, y=0):
		self.position = (x, y)

	@override
	def compress(self):
		if isinstance(self.action, MenuAction):
			self.action.x, self.action.y = self.position
		return self.action

	@staticmethod
	def decode(data, a, *b):
		x, y = data[PositionModifier.COMMAND]
		return PositionModifier(x, y, a)

	@override
	def describe(self, context):
		return self.action.describe(context)


class GesturesAction(Action, OSDEnabledAction, SpecialAction):
	"""
	Stars gesture detection on pad. Recognition is handled by whatever
	is special_actions_handler and results are then sent back to this action
	as parameter of gesture() method.
	"""

	SA = COMMAND = "gestures"
	PROFILE_KEYS = ("gestures",)
	PROFILE_KEY_PRIORITY = 2
	DEFAULT_PRECISION = 1.0

	def __init__(self, *stuff):
		OSDEnabledAction.__init__(self)
		Action.__init__(self, *stuff)
		self.gestures = {}
		self.precision = self.DEFAULT_PRECISION
		gstr = None

		if len(stuff) > 0 and type(stuff[0]) in (int, float):
			self.precision = clamp(0.0, float(stuff[0]), 1.0)
			stuff = stuff[1:]

		for i in stuff:
			if gstr is None and type(i) in (str, unicode):
				gstr = i
			elif gstr is not None and isinstance(i, Action):
				self.gestures[gstr] = i
				gstr = None
			else:
				raise ValueError(f"Invalid parameter for '{self.COMMAND}': unexpected {i}")

	@override
	def get_compatible_modifiers(self):
		return Action.MOD_OSD

	@override
	def describe(self, context):
		if self.name:
			return self.name
		return _("Gestures")

	@override
	def to_string(self, multiline=False, pad=0):
		if multiline:
			rv = [(" " * pad) + self.COMMAND + "("]
			if self.precision != self.DEFAULT_PRECISION:
				rv[0] += f"{self.precision},"
			for gstr in self.gestures:
				a_str = self.gestures[gstr].to_string(True).split("\n")
				a_str[0] = (" " * pad) + "  '" + (gstr + "',").ljust(11) + a_str[0]  # Key has to be one of SCButtons
				for i in range(1, len(a_str)):
					a_str[i] = (" " * pad) + "  " + a_str[i]
				a_str[-1] = a_str[-1] + ","
				rv += a_str
			if rv[-1][-1] == ",":
				rv[-1] = rv[-1][0:-1]
			rv += [(" " * pad) + ")"]
			return "\n".join(rv)
		rv = []
		if self.precision != self.DEFAULT_PRECISION:
			rv.append(str(self.precision))
		for gstr in self.gestures:
			rv += [f"'{gstr}'", self.gestures[gstr].to_string(False)]
		return self.COMMAND + "(" + ", ".join(rv) + ")"

	@override
	def compress(self):
		for gstr in self.gestures:
			a = self.gestures[gstr].compress()
			if "i" in gstr:
				del self.gestures[gstr]
				gstr = strip_gesture(gstr)
			self.gestures[gstr] = a
		return self

	@staticmethod
	def decode(data, a, parser, *b):
		ga = GesturesAction()
		ga.gestures = {
			gstr: parser.from_json_data(data[GesturesAction.PROFILE_KEYS[0]][gstr])
			for gstr in data[GesturesAction.PROFILE_KEYS[0]]
		}
		if "name" in data:
			ga.name = data["name"]
		if "osd" in data:
			ga = OSDAction(ga)
		return ga

	def _find_exact_gesture(self, gesture_string):
		return self.gestures.get(gesture_string)

	def _find_ignore_stroke_count_gesture(self, gesture_string):
		stripped_gesture_string = strip_gesture(gesture_string)
		return self.gestures.get(stripped_gesture_string)

	def _find_best_match_gesture(self, gesture_string):
		NUM_MATCHES_TO_RETURN = 1

		similar_gestures = get_close_matches(
			gesture_string, self.gestures.keys(), NUM_MATCHES_TO_RETURN, self.precision
		)
		best_gesture = next(iter(similar_gestures), None)

		if best_gesture is not None:
			return self.gestures[best_gesture]
		return None

	def find_gesture_action(self, gesture_string):
		action = None
		action = action or self._find_exact_gesture(gesture_string)
		action = action or self._find_ignore_stroke_count_gesture(gesture_string)
		return action or self._find_best_match_gesture(gesture_string)

	def gesture(self, mapper, gesture_string):
		action = self.find_gesture_action(gesture_string)
		if action:
			action.button_press(mapper)
			mapper.schedule(0, action.button_release)

	@override
	def whole(self, mapper, x, y, what):
		if (x, y) != (0, 0):
			# (0, 0) singlanizes released touchpad
			self.execute(mapper, x, y, what)


class CemuHookAction(Action, SpecialAction):
	SA = COMMAND = "cemuhook"
	MAGIC_GYRO = 2000.0 / float(STICK_PAD_MAX)

	@override
	def gyro(self, mapper, pitch, yaw, roll, q1, q2, q3, q4):
		sa_data = (
			pitch * CemuHookAction.MAGIC_GYRO,
			-yaw * CemuHookAction.MAGIC_GYRO,
			-roll * CemuHookAction.MAGIC_GYRO,
		)
		self.execute(mapper, sa_data)

	@override
	def describe(self, context):
		if self.name:
			return self.name
		return _("CemuHook")


# Register actions from current module
Action.register_all(sys.modules[__name__])
