from scc.constants import STICK_PAD_MIN, STICK_PAD_MAX
from scc.drivers.fake import FakeController
from scc.uinput import Dummy, Keys, Axes
from scc.constants import SCButtons, ControllerFlags, STICK, RSTICK
from scc.parser import ActionParser
from scc.profile import Profile
from scc.scheduler import Scheduler
from scc.mapper import Mapper
from scc.modifiers import TouchedModifier
from scc.actions import Action
from collections import namedtuple
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
