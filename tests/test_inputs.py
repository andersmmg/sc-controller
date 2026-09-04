from scc.constants import STICK_PAD_MIN, STICK_PAD_MAX
from scc.drivers.fake import FakeController
from scc.uinput import Dummy, Keys, Axes
from scc.constants import SCButtons, ControllerFlags, STICK, RSTICK
from scc.constants import TRIGGER_MAX, CUT, ROUND, LINEAR, MINIMUM
from scc.parser import ActionParser
from scc.profile import Profile
from scc.scheduler import Scheduler
from scc.mapper import Mapper
from scc.modifiers import TouchedModifier, DeadzoneModifier
from scc.actions import Action, NoAction
from scc.drivers.evdevdrv import EvdevController, EvdevControllerInput
from collections import namedtuple
from math import sqrt
import time

"""
Tests various inputs for crashes and incorrect behaviour,
mostly using dummy outputs and FakeController
"""

FakeControllerInput = namedtuple('FakeControllerInput',
	'buttons ltrig rtrig stick_x stick_y lpad_x lpad_y rpad_x rpad_y '
	'rstick_x rstick_y dpad_x dpad_y '
	'gpitch groll gyaw q1 q2 q3 q4 '
)
ZERO_STATE = FakeControllerInput( *[0] * len(FakeControllerInput._fields) )
parser = ActionParser()


class _CountingAction(Action):
	""" Action that counts how many times whole() was called. """
	def __init__(self):
		Action.__init__(self)
		self.hits = 0

	def whole(self, mapper, x, y, what):
		self.hits += 1

def input_test(fn):
	""" Decorator that creates usable mapper """
	def wrapper(*a):
		_time = time.time

		def fake_time():
			return fake_time.t
		def add(n):
			fake_time.t += n
		fake_time.t = _time()
		fake_time.add = add
		time.time = fake_time

		controller = FakeController(0)
		profile = Profile(parser)
		scheduler = Scheduler()
		mapper = Mapper(profile, scheduler, keyboard=False, mouse=False, gamepad=False, poller=None)
		mapper.keyboard = RememberingDummy()
		mapper.gamepad = RememberingDummy()
		mapper.mouse = RememberingDummy()
		mapper.set_controller(controller)
		mapper._testing = True
		mapper._tick_rate = 0.01

		_mapper_input = mapper.input
		def mapper_input(*a):
			add(mapper._tick_rate)
			_mapper_input(*a)
			scheduler.run()
		mapper.input = mapper_input

		a = list(a) + [ mapper ]
		try:
			return fn(*a)
		finally:
			time.time = _time
	return wrapper


class RememberingDummy(Dummy):
	def __init__(self, *a, **b):
		Dummy.__init__(self, *a, **b)
		self.pressed = set([])
		self.mouse_x = 0
		self.mouse_y = 0
		self.scroll_x = 0
		self.scroll_y = 0
		self.axes = {}


	def axisEvent(self, axis, val):
		self.axes[axis] = val


	def keyEvent(self, key, val):
		if val:
			self.pressed.add(key)
		else:
			self.pressed.discard(key)


	def moveEvent(self, dx=0, dy=0):
		self.mouse_x += dx
		self.mouse_y += dy


	def scrollEvent(self, dx=0, dy=0):
		self.scroll_x += dx
		self.scroll_y += dx


	def pressEvent(self, keys):
		for k in keys:
			assert k not in self.pressed
			self.pressed.add(k)


	def releaseEvent(self, keys=[]):
		for k in keys:
			if k in self.pressed:
				self.pressed.remove(k)


class TestInputs(object):
	@input_test
	def test_button(self, mapper):
		"""
		Just test for test, this should work every time.
		"""
		mapper.profile.buttons[SCButtons.A] = (parser
			.restart("button(Keys.KEY_ENTER)")).parse()
		state = ZERO_STATE._replace(buttons=SCButtons.A)
		mapper.input(mapper.controller, ZERO_STATE, state)
		assert Keys.KEY_ENTER in mapper.keyboard.pressed
		mapper.input(mapper.controller, state, state._replace(buttons=0))
		assert Keys.KEY_ENTER not in mapper.keyboard.pressed


	@input_test
	def test_trackball(self, mapper):
		"""
		Tests trackball emulation
		"""
		mapper.profile.pads[Profile.LEFT] = (parser.restart(
			"ball(XY("
			"	mouse(Rels.REL_HWHEEL, 1.0), "
			"	mouse(Rels.REL_WHEEL, 1.0)"
			"))"
		)).parse()

		# Create movement over left pad
		state = ZERO_STATE
		for x in reversed(range(STICK_PAD_MIN * 2 // 3, -10, 1000)):
			new_state = state._replace(buttons=SCButtons.LPADTOUCH, lpad_x=x)
			mapper.input(mapper.controller, state, new_state)
			state = new_state
		assert mapper.mouse.scroll_x == -21000.0
		# Release left pad
		mapper.input(mapper.controller, state, ZERO_STATE)
		# 'Wait' for 2s
		for x in range(20):
			mapper.input(mapper.controller, ZERO_STATE, ZERO_STATE)
		assert int(mapper.mouse.scroll_x) == -24479


	@input_test
	def test_dpad(self, mapper):
		"""
		Tests WSAD
		"""
		mapper.profile.pads[Profile.LEFT] = (parser.restart(
			"dpad("
			"	button(Keys.KEY_W), button(Keys.KEY_S),"
			"	button(Keys.KEY_A), button(Keys.KEY_D))"
		)).parse()

		# Create movements over left pad
		# - A
		state = ZERO_STATE._replace(buttons=SCButtons.LPADTOUCH, lpad_x=STICK_PAD_MIN)
		mapper.input(mapper.controller, ZERO_STATE, state)
		assert Keys.KEY_A in mapper.keyboard.pressed
		mapper.input(mapper.controller, state, ZERO_STATE)
		# - S
		state = ZERO_STATE._replace(buttons=SCButtons.LPADTOUCH, lpad_y=STICK_PAD_MIN)
		mapper.input(mapper.controller, ZERO_STATE, state)
		assert Keys.KEY_S in mapper.keyboard.pressed
		mapper.input(mapper.controller, state, ZERO_STATE)
		# - D
		state = ZERO_STATE._replace(buttons=SCButtons.LPADTOUCH, lpad_x=STICK_PAD_MAX)
		mapper.input(mapper.controller, ZERO_STATE, state)
		assert Keys.KEY_D in mapper.keyboard.pressed
		mapper.input(mapper.controller, state, ZERO_STATE)


	@input_test
	def test_joystick_camera(self, mapper):
		"""
		Tests joystick camera, mapping trackball to right joystick
		"""
		mapper.profile.pads[Profile.RIGHT] = (parser.restart(
			"ball(XY("
			"	axis(Axes.ABS_RX),"
			"	axis(Axes.ABS_RY)"
			"))"
		)).parse()

		# Create movement over right pad
		state = ZERO_STATE
		for x in range(10, STICK_PAD_MAX * 2 // 3, 3000):
			new_state = state._replace(buttons=SCButtons.RPADTOUCH, rpad_x=x)
			mapper.input(mapper.controller, state, new_state)
			state = new_state
		assert mapper.gamepad.axes[Axes.ABS_RX] == 3000
		# Release left pad
		mapper._tick_rate = 0.001
		mapper.input(mapper.controller, state, ZERO_STATE)
		# 'Wait' for 1s
		for x in range(100):
			mapper.input(mapper.controller, ZERO_STATE, ZERO_STATE)
		assert mapper.gamepad.axes[Axes.ABS_RX] == 3510
		# 'Wait' for another 0.5s
		for x in range(50):
			mapper.input(mapper.controller, ZERO_STATE, ZERO_STATE)
		assert mapper.gamepad.axes[Axes.ABS_RX] == 1570
		# 'Wait' for long time so stick recenters
		for x in range(100):
			mapper.input(mapper.controller, ZERO_STATE, ZERO_STATE)
		assert mapper.gamepad.axes[Axes.ABS_RX] == 0


	@input_test
	def test_sens_stick_whole(self, mapper):
		"""
		Tests that sens() forwards whole() input to stick bindings.
		SensitivityModifier used to swallow whole(), so stick to gamepad
		bindings wrapped in sens() produced no output at all!
		"""
		mapper.controller.flags = (ControllerFlags.SEPARATE_STICK
			| ControllerFlags.HAS_RSTICK | ControllerFlags.HAS_DPAD)
		mapper.profile.stick = (parser.restart(
			"sens(1.2, 1.2, XY(axis(Axes.ABS_X), raxis(Axes.ABS_Y)))"
		)).parse()
		state = ZERO_STATE._replace(stick_x=10000, stick_y=0)
		mapper.input(mapper.controller, ZERO_STATE, state)
		assert abs(mapper.gamepad.axes[Axes.ABS_X]) > 10000
		assert abs(mapper.gamepad.axes[Axes.ABS_X]) < 13000
		assert abs(mapper.gamepad.axes[Axes.ABS_Y]) <= 1
		mapper.input(mapper.controller, state, ZERO_STATE)
		assert abs(mapper.gamepad.axes[Axes.ABS_X]) <= 1
		assert abs(mapper.gamepad.axes[Axes.ABS_Y]) <= 1


	@input_test
	def test_joystick_round_response(self, mapper):
		"""
		Tests that round-response normalization keeps the emulated gamepad
		output inside the circle, even with sensitivity applied.
		"""
		import math
		mapper.controller.flags = (ControllerFlags.SEPARATE_STICK
			| ControllerFlags.HAS_RSTICK | ControllerFlags.HAS_DPAD)

		mapper.profile.stick = (parser.restart(
			"sens(1.2, 1.2, XY(axis(Axes.ABS_X), raxis(Axes.ABS_Y), True))"
		)).parse()
		state = ZERO_STATE._replace(stick_x=23170, stick_y=23170)
		mapper.input(mapper.controller, ZERO_STATE, state)
		x, y = mapper.gamepad.axes[Axes.ABS_X], mapper.gamepad.axes[Axes.ABS_Y]
		assert math.sqrt(x * x + y * y) <= STICK_PAD_MAX + 1

		mapper.profile.stick = (parser.restart(
			"sens(1.2, 1.2, XY(axis(Axes.ABS_X), raxis(Axes.ABS_Y)))"
		)).parse()
		state2 = ZERO_STATE._replace(stick_x=32767, stick_y=32767)
		mapper.input(mapper.controller, state, state2)
		x, y = mapper.gamepad.axes[Axes.ABS_X], mapper.gamepad.axes[Axes.ABS_Y]
		assert math.sqrt(x * x + y * y) > STICK_PAD_MAX
		mapper.input(mapper.controller, state2, ZERO_STATE)


	@input_test
	def test_dpad_button_goes_to_gamepad(self, mapper):
		"""
		Tests that dpad buttons (BTN_DPAD_*) are emitted through the emulated
		gamepad, not the keyboard, whic was a weird issue sometimes.
		"""
		if not hasattr(Keys, "BTN_DPAD_DOWN"):
			return
		mapper.controller.flags = (ControllerFlags.SEPARATE_STICK
			| ControllerFlags.HAS_RSTICK | ControllerFlags.HAS_DPAD)
		mapper.profile.buttons[SCButtons.A] = (parser.restart(
			"button(Keys.BTN_DPAD_DOWN)")).parse()
		state = ZERO_STATE._replace(buttons=SCButtons.A)
		mapper.input(mapper.controller, ZERO_STATE, state)
		assert Keys.BTN_DPAD_DOWN in mapper.gamepad.pressed
		assert Keys.BTN_DPAD_DOWN not in mapper.keyboard.pressed
		mapper.input(mapper.controller, state, ZERO_STATE)
		assert Keys.BTN_DPAD_DOWN not in mapper.gamepad.pressed


	@input_test
	def test_modeshift(self, mapper):
		"""
		Tests WSAD
		"""
		mapper.profile.buttons[SCButtons.A] = (parser.restart(
			"mode(B, button(Keys.KEY_V), button(Keys.KEY_Y))"
		)).parse()

		# Press single button
		state = ZERO_STATE._replace(buttons=SCButtons.A)
		mapper.input(mapper.controller, ZERO_STATE, state)
		assert Keys.KEY_Y in mapper.keyboard.pressed
		mapper.input(mapper.controller, state, ZERO_STATE)
		assert Keys.KEY_Y not in mapper.keyboard.pressed

		# Press modeshifting button
		state = ZERO_STATE._replace(buttons=SCButtons.B)
		mapper.input(mapper.controller, ZERO_STATE, state)
		assert Keys.KEY_Y not in mapper.keyboard.pressed
		assert Keys.KEY_V not in mapper.keyboard.pressed

		# Press button again
		_state, state = state, state._replace(buttons=SCButtons.B | SCButtons.A)
		mapper.input(mapper.controller, _state, state)
		assert Keys.KEY_V in mapper.keyboard.pressed
		assert Keys.KEY_Y not in mapper.keyboard.pressed

		# Release modeshifting button
		_state, state = state, state._replace(buttons=SCButtons.A)
		mapper.input(mapper.controller, _state, state)
		assert Keys.KEY_V in mapper.keyboard.pressed
		assert Keys.KEY_Y not in mapper.keyboard.pressed

		# Release original button and press it again
		_state, state = state, state._replace(buttons=0)
		mapper.input(mapper.controller, _state, state)
		assert Keys.KEY_V not in mapper.keyboard.pressed
		assert Keys.KEY_Y not in mapper.keyboard.pressed

		_state, state = state, state._replace(buttons=SCButtons.A)
		mapper.input(mapper.controller, _state, state)
		assert Keys.KEY_Y in mapper.keyboard.pressed


	@input_test
	def test_sc2_is_touched(self, mapper):
		"""
		Tests that mapper.is_touched()/was_touched() reflect SC2 stick touch bits.
		"""
		mapper.controller.flags = (ControllerFlags.IS_SC2 | ControllerFlags.SEPARATE_STICK
			| ControllerFlags.HAS_DPAD | ControllerFlags.HAS_RSTICK
			| ControllerFlags.HAS_TOUCHPADS)
		assert not mapper.is_touched(STICK)
		assert not mapper.is_touched(RSTICK)

		state = ZERO_STATE._replace(buttons=SCButtons.LSTICKTOUCH | SCButtons.RSTICKTOUCH)
		mapper.input(mapper.controller, ZERO_STATE, state)
		assert mapper.is_touched(STICK)
		assert mapper.is_touched(RSTICK)
		assert not mapper.was_touched(STICK)
		assert not mapper.was_touched(RSTICK)

		mapper.input(mapper.controller, state, ZERO_STATE)
		assert not mapper.is_touched(STICK)
		assert not mapper.is_touched(RSTICK)
		assert mapper.was_touched(STICK)
		assert mapper.was_touched(RSTICK)


	@input_test
	def test_sc2_stick_touch_whole(self, mapper):
		"""
		Tests that stick touch edge triggers profile.stick/rstick.whole even
		with no coordinate change, so touched()/untouched() can fire on sticks.
		"""
		mapper.controller.flags = (ControllerFlags.IS_SC2 | ControllerFlags.SEPARATE_STICK
			| ControllerFlags.HAS_DPAD | ControllerFlags.HAS_RSTICK
			| ControllerFlags.HAS_TOUCHPADS)
		stick = _CountingAction()
		rstick = _CountingAction()
		mapper.profile.stick = stick
		mapper.profile.rstick = rstick

		# Touch both sticks, stay centered (no coordinate change)
		state = ZERO_STATE._replace(buttons=SCButtons.LSTICKTOUCH | SCButtons.RSTICKTOUCH)
		mapper.input(mapper.controller, ZERO_STATE, state)
		assert stick.hits == 1
		assert rstick.hits == 1

		# Release both sticks
		mapper.input(mapper.controller, state, ZERO_STATE)
		assert stick.hits == 2
		assert rstick.hits == 2


	@input_test
	def test_sc2_touched_modifier_on_stick(self, mapper):
		"""
		Tests that touched(STICK)/touched(RSTICK) fires on stick touch edge.
		"""
		mapper.controller.flags = (ControllerFlags.IS_SC2 | ControllerFlags.SEPARATE_STICK
			| ControllerFlags.HAS_DPAD | ControllerFlags.HAS_RSTICK
			| ControllerFlags.HAS_TOUCHPADS)
		mapper.profile.stick = TouchedModifier(
			(parser.restart("button(Keys.KEY_P)")).parse())
		mapper.profile.rstick = TouchedModifier(
			(parser.restart("button(Keys.KEY_Q)")).parse())

		state = ZERO_STATE._replace(buttons=SCButtons.LSTICKTOUCH | SCButtons.RSTICKTOUCH)
		mapper.input(mapper.controller, ZERO_STATE, state)
		assert Keys.KEY_P in mapper.keyboard.pressed
		assert Keys.KEY_Q in mapper.keyboard.pressed

		mapper.input(mapper.controller, state, ZERO_STATE)
		assert Keys.KEY_P not in mapper.keyboard.pressed
		assert Keys.KEY_Q not in mapper.keyboard.pressed


	@input_test
	def test_sc2_set_button_rstick(self, mapper):
		"""
		Tests that set_button(RSTICK, ...) does not crash (bug where
		'a &= ~string' raised TypeError).
		"""
		mapper.controller.flags = (ControllerFlags.IS_SC2 | ControllerFlags.SEPARATE_STICK
			| ControllerFlags.HAS_DPAD | ControllerFlags.HAS_RSTICK
			| ControllerFlags.HAS_TOUCHPADS)
		mapper.set_button(RSTICK, True)
		assert mapper.is_pressed(SCButtons.RSTICKTOUCH)
		mapper.set_button(RSTICK, False)
		assert not mapper.is_pressed(SCButtons.RSTICKTOUCH)
		mapper.set_was_pressed(RSTICK, True)
		assert mapper.was_pressed(SCButtons.RSTICKTOUCH)
		mapper.set_was_pressed(RSTICK, False)
		assert not mapper.was_pressed(SCButtons.RSTICKTOUCH)


	@input_test
	def test_sc2_grip_sense_buttons(self, mapper):
		"""
		Tests that LSENSE/RSENSE (right/left grip touch) are handled as
		regular buttons: set_button / is_pressed and button edges fire
		profile.button actions.
		"""
		mapper.controller.flags = (ControllerFlags.IS_SC2 | ControllerFlags.SEPARATE_STICK
			| ControllerFlags.HAS_DPAD | ControllerFlags.HAS_RSTICK
			| ControllerFlags.HAS_TOUCHPADS)
		assert int(SCButtons.RSENSE) != int(SCButtons.RPADTOUCH)
		assert int(SCButtons.LSENSE) != int(SCButtons.LPADTOUCH)
		assert int(SCButtons.RSENSE) != int(SCButtons.LSENSE)
		mapper.set_button(SCButtons.LSENSE, True)
		assert mapper.is_pressed(SCButtons.LSENSE)
		mapper.set_button(SCButtons.RSENSE, True)
		assert mapper.is_pressed(SCButtons.RSENSE)
		mapper.set_button(SCButtons.LSENSE, False)
		assert not mapper.is_pressed(SCButtons.LSENSE)
		mapper.set_was_pressed(SCButtons.RSENSE, True)
		assert mapper.was_pressed(SCButtons.RSENSE)


	@input_test
	def test_sc2_grip_sense_edge(self, mapper):
		"""
		Tests that grip touch button edges trigger the mapped button action.
		"""
		mapper.controller.flags = (ControllerFlags.IS_SC2 | ControllerFlags.SEPARATE_STICK
			| ControllerFlags.HAS_DPAD | ControllerFlags.HAS_RSTICK
			| ControllerFlags.HAS_TOUCHPADS)
		mapper.profile.buttons[SCButtons.LSENSE] = (parser
			.restart("button(Keys.KEY_R)")).parse()
		mapper.profile.buttons[SCButtons.RSENSE] = (parser
			.restart("button(Keys.KEY_T)")).parse()

		state = ZERO_STATE._replace(buttons=SCButtons.LSENSE | SCButtons.RSENSE)
		mapper.input(mapper.controller, ZERO_STATE, state)
		assert Keys.KEY_R in mapper.keyboard.pressed
		assert Keys.KEY_T in mapper.keyboard.pressed

		mapper.input(mapper.controller, state, ZERO_STATE)
		assert Keys.KEY_R not in mapper.keyboard.pressed
		assert Keys.KEY_T not in mapper.keyboard.pressed


	@input_test
	def test_normalize_corner_clamped_to_circle(self, mapper):
		"""
		With normalize=True, corner input is scaled down to
		the unit circle instead of passed through as a square corner.
		"""
		mapper.profile.stick = parser.restart(
			"XY(axis(Axes.ABS_X), axis(Axes.ABS_Y), True)").parse()

		state = ZERO_STATE._replace(lpad_x=STICK_PAD_MAX, lpad_y=STICK_PAD_MAX)
		mapper.input(mapper.controller, ZERO_STATE, state)

		x = mapper.gamepad.axes[Axes.ABS_X]
		y = mapper.gamepad.axes[Axes.ABS_Y]
		r = sqrt(float(x) * x + float(y) * y)
		assert abs(r - STICK_PAD_MAX) < 2, "radius %s not on circle" % (r,)


	@input_test
	def test_normalize_passthrough_inside_circle(self, mapper):
		"""
		With normalize=True, input already inside the circle passes through
		unchanged.
		"""
		mapper.profile.stick = parser.restart(
			"XY(axis(Axes.ABS_X), axis(Axes.ABS_Y), True)").parse()

		state = ZERO_STATE._replace(lpad_x=16384)
		mapper.input(mapper.controller, ZERO_STATE, state)
		assert mapper.gamepad.axes[Axes.ABS_X] == 16384
		assert mapper.gamepad.axes[Axes.ABS_Y] == 0


	@input_test
	def test_no_normalize_default_square(self, mapper):
		"""
		Default (normalize unset) keeps square output: full corner deflection
		reaches (max, max).
		"""
		mapper.profile.stick = parser.restart(
			"XY(axis(Axes.ABS_X), axis(Axes.ABS_Y))").parse()

		state = ZERO_STATE._replace(lpad_x=STICK_PAD_MAX, lpad_y=STICK_PAD_MAX)
		mapper.input(mapper.controller, ZERO_STATE, state)
		assert mapper.gamepad.axes[Axes.ABS_X] == STICK_PAD_MAX
		assert mapper.gamepad.axes[Axes.ABS_Y] == STICK_PAD_MAX


class TestDeadzoneUpperBound(object):
	"""
	Behavioral tests for DeadzoneModifier's optional upper bound

	Ensure it never clips high input in any mode, even LINEAR
	"""

	def test_cut_without_upper_never_cuts_high_input(self):
		d = DeadzoneModifier(CUT, 2000, NoAction())
		assert d.upper is None
		assert d._convert(20000, 0, TRIGGER_MAX) == (20000, 0)
		assert d._convert(STICK_PAD_MAX, 0, STICK_PAD_MAX) == (STICK_PAD_MAX, 0)
		assert d._convert(STICK_PAD_MAX, STICK_PAD_MAX, STICK_PAD_MAX) \
			== (STICK_PAD_MAX, STICK_PAD_MAX)

	def test_cut_with_upper_cuts_input_above_bound(self):
		d = DeadzoneModifier(CUT, 2000, 20000, NoAction())
		assert d._convert(20000, 0, TRIGGER_MAX) == (20000, 0)
		assert d._convert(20001, 0, TRIGGER_MAX) == (0, 0)
		assert d._convert(STICK_PAD_MAX, STICK_PAD_MAX, STICK_PAD_MAX) == (0, 0)

	def test_round_with_upper_snaps_to_circle(self):
		d = DeadzoneModifier(ROUND, 2000, 20000, NoAction())
		x, y = d._convert(STICK_PAD_MAX, STICK_PAD_MAX, STICK_PAD_MAX)
		expected = STICK_PAD_MAX * sqrt(0.5)
		assert abs(x - expected) < 1
		assert abs(y - expected) < 1

	def test_round_without_upper_passes_high_input(self):
		d = DeadzoneModifier(ROUND, 2000, NoAction())
		assert d._convert(STICK_PAD_MAX, 0, TRIGGER_MAX) == (STICK_PAD_MAX, 0)

	def test_linear_full_deflection_reaches_max_without_upper(self):
		d = DeadzoneModifier(LINEAR, 2000, NoAction())
		x, y = d._convert(STICK_PAD_MAX, 0, STICK_PAD_MAX)
		assert abs(x - STICK_PAD_MAX) < 1

	def test_linear_upper_is_saturation_input(self):
		"""
		In LINEAR mode, 'upper' is the input value that maps to full output
		(range): input band [lower, upper] is scaled to [0, range].
		"""
		d = DeadzoneModifier(LINEAR, 2000, 20000, NoAction())
		# 11000 is halfway between lower (2000) and upper (20000)
		x, y = d._convert(11000, 0, STICK_PAD_MAX)
		assert abs(x - STICK_PAD_MAX * 0.5) < 1
		# at/above upper, output is at full range
		x, y = d._convert(20000, 0, STICK_PAD_MAX)
		assert abs(x - STICK_PAD_MAX) < 1

	def test_minimum_full_deflection_without_upper_covers_range(self):
		d = DeadzoneModifier(MINIMUM, 2000, NoAction())
		x, y = d._convert(STICK_PAD_MAX, 0, STICK_PAD_MAX)
		assert abs(x - STICK_PAD_MAX) < 1

	def test_minimum_full_deflection_maps_to_upper(self):
		d = DeadzoneModifier(MINIMUM, 2000, 20000, NoAction())
		x, y = d._convert(STICK_PAD_MAX, 0, STICK_PAD_MAX)
		assert abs(x - 20000) < 1

	def test_decode_without_upper_key(self):
		"""
		Regression: profile json without 'upper' key
		"""
		a = DeadzoneModifier.decode(
			{"deadzone": {"mode": "CUT", "lower": 100}}, NoAction())
		assert a.upper is None
		assert a.lower == 100

	def test_decode_with_upper_key(self):
		a = DeadzoneModifier.decode(
			{"deadzone": {"mode": "CUT", "lower": 100, "upper": 20000}},
			NoAction())
		assert a.upper == 20000

	def test_decode_from_profile_json(self):
		""" Full parser path for a profile saved with upper-bound toggle off """
		p = ActionParser()
		a = p.from_json_data({"deadzone": {
			"mode": "LINEAR", "lower": 100,
			"action": {"__class": "mouse", "id": "REL_WHEEL"}}})
		assert a.upper is None


class TestStickRepeat(object):
	"""
	Tests for evdev driver's stick repeat
	"""

	class RecordingMapper(object):
		def __init__(self):
			self.inputs = []
			self.scheduled = []

		def input(self, c, old_state, new_state):
			self.inputs.append(new_state)

		def schedule(self, delay, cb):
			self.scheduled.append((delay, cb))
			return object()

	def _mk_controller(self):
		c = object.__new__(EvdevController)
		c._state = EvdevControllerInput(
			*[0] * len(EvdevControllerInput._fields))
		c._stickrepeat_task = None
		c._padpressemu_task = None
		c._last_event_ts = 0
		c.mapper = None
		return c

	def test_is_stick_deflected(self):
		c = self._mk_controller()
		assert not c._is_stick_deflected(c._state)
		c._state = c._state._replace(stick_x=100)
		assert c._is_stick_deflected(c._state)
		c._state = EvdevControllerInput(
			*[0] * len(EvdevControllerInput._fields))._replace(rstick_y=-100)
		assert c._is_stick_deflected(c._state)

	def test_repeat_resends_while_deflected(self):
		c = self._mk_controller()
		c.mapper = self.RecordingMapper()
		c._state = c._state._replace(stick_x=100)
		c._last_event_ts = time.time() - 10 # long since last real event

		c.repeat_stick(c.mapper)

		assert len(c.mapper.inputs) == 1
		assert c.mapper.inputs[0].stick_x == 100
		# loop is kept alive while stick stays deflected
		assert c._stickrepeat_task is not None
		assert len(c.mapper.scheduled) == 1

	def test_repeat_skips_when_event_recent(self):
		""" No repeat input when a real event arrived just now """
		c = self._mk_controller()
		c.mapper = self.RecordingMapper()
		c._state = c._state._replace(stick_x=100)
		c._last_event_ts = time.time()

		c.repeat_stick(c.mapper)

		assert len(c.mapper.inputs) == 0
		# but the loop is still rescheduled
		assert c._stickrepeat_task is not None

	def test_repeat_stops_when_centered(self):
		""" No repeat input and no reschedule once stick is back at center """
		c = self._mk_controller()
		c.mapper = self.RecordingMapper()

		c.repeat_stick(c.mapper)

		assert len(c.mapper.inputs) == 0
		assert len(c.mapper.scheduled) == 0
		assert c._stickrepeat_task is None
