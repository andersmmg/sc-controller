from scc.actions import Action, MouseAction
from scc.modifiers import SensitivityModifier
from scc.uinput import Rels
from scc.gui.action_editor import ActionEditor

REL_XY = MouseAction(Rels.REL_X, Rels.REL_Y)


class FakeWidget(object):
	def __init__(self, value=0.0, active=False):
		self.value = value
		self.active = active
		self.sensitive = True
		self.visible = True

	def get_value(self):
		return self.value

	def set_value(self, v):
		self.value = v

	def get_active(self):
		return self.active

	def set_active(self, a):
		self.active = bool(a)

	def get_sensitive(self):
		return self.sensitive

	def set_sensitive(self, s):
		self.sensitive = bool(s)

	def set_visible(self, v):
		self.visible = bool(v)


class FakeBuilder(object):
	def __init__(self):
		self.objects = {}

	def get_object(self, name):
		if name not in self.objects:
			self.objects[name] = FakeWidget()
		return self.objects[name]


class FakeComponent(object):
	def modifier_updated(self):
		pass


class FakeEditor(ActionEditor):
	def __init__(self, mode):
		self.id = "lstick"
		self.sens = [1.0, 1.0, 1.0]
		self.sens_defaults = [1.0, 1.0, 1.0]
		self.sens_widgets = [
			(FakeWidget(1.0), FakeWidget(), FakeWidget(), FakeWidget())
			for _ in range(3)
		]
		self.feedback = [0.0, 0.0, 0.0]
		self.feedback_widgets = [
			(FakeWidget(0.0), FakeWidget(), FakeWidget(), 0.0)
			for _ in range(3)
		]
		self.smoothing = None
		self.smoothing_widgets = [
			(FakeWidget(), FakeWidget(2.0), FakeWidget(), 0.0)
			for _ in range(3)
		]
		self.deadzone = [0, 0]
		self.deadzone_widgets = [
			(FakeWidget(), FakeWidget(0.0), FakeWidget(), 0)
			for _ in range(2)
		]
		self.deadzone_mode = None
		self.deadzone_upper_enabled = False
		self.feedback_position = None
		self.click = False
		self.osd = False
		self.rotation_angle = 0
		self.friction = -1
		self._mode = mode
		self._recursing = False
		self._sens_xy_locked = False
		self._action = REL_XY
		self._selected_component = FakeComponent()
		self.builder = FakeBuilder()
		self.set_action_calls = 0

	def set_action(self, action, from_custom=False):
		self.set_action_calls += 1


def _mk_editor(mode):
	return FakeEditor(mode)


def test_lock_syncs_y_from_x_stick():
	ed = _mk_editor(Action.AC_STICK)
	ed.builder.get_object("cbSensLockXY").set_active(True)
	ed.sens_widgets[0][0].set_value(2.5)

	ed.update_modifiers()

	assert ed.sens[0] == 2.5
	assert ed.sens[1] == 2.5, "Y must follow X while locked"


def test_lock_syncs_invert_flag():
	ed = _mk_editor(Action.AC_STICK)
	ed.builder.get_object("cbSensLockXY").set_active(True)
	ed.sens_widgets[0][3].set_active(True)  # invert X
	ed.sens_widgets[0][0].set_value(1.5)

	ed.update_modifiers()

	assert ed.sens[0] == -1.5
	assert ed.sens[1] == -1.5
	assert ed.sens_widgets[1][3].get_active(), "Y invert checkbox must follow X"


def test_unlock_allows_different_xy():
	ed = _mk_editor(Action.AC_STICK)
	ed.builder.get_object("cbSensLockXY").set_active(False)
	ed.sens_widgets[0][0].set_value(3.0)
	ed.sens_widgets[1][0].set_value(0.5)

	ed.update_modifiers()

	assert ed.sens[0] == 3.0
	assert ed.sens[1] == 0.5, "Y must be independent when unlocked"


def test_lock_disables_y_widgets():
	ed = _mk_editor(Action.AC_STICK)
	lock = ed.builder.get_object("cbSensLockXY")

	lock.set_active(False)
	ed.update_modifiers()
	assert all(w.get_sensitive() for w in ed.sens_widgets[1]), \
		"Y widgets must be enabled when unlocked"

	lock.set_active(True)
	ed.update_modifiers()
	assert all(not w.get_sensitive() for w in ed.sens_widgets[1]), \
		"Y widgets must be disabled (display-only) while locked"
	assert all(w.get_sensitive() for w in ed.sens_widgets[0]), \
		"X widgets must stay enabled while locked"


def test_lock_not_available_for_trigger():
	ed = _mk_editor(Action.AC_TRIGGER)
	ed.builder.get_object("cbSensLockXY").set_active(True)
	ed.sens_widgets[0][0].set_value(2.0)
	ed.sens_widgets[1][0].set_value(0.5)

	ed.update_modifiers()

	assert ed._sens_xy_locked is False
	assert ed.sens[1] == 0.5, "lock must be ignored for non-2-axis inputs"
	assert all(w.get_sensitive() for w in ed.sens_widgets[1]), \
		"Y widgets must stay enabled for non-2-axis inputs"


def test_clear_x_clears_y_when_locked():
	ed = _mk_editor(Action.AC_STICK)
	ed.builder.get_object("cbSensLockXY").set_active(True)
	ed.sens_widgets[0][0].set_value(4.0)
	ed.sens_widgets[1][0].set_value(4.0)

	ed.on_btClearSens_clicked(ed.sens_widgets[0][2])

	assert ed.sens_widgets[0][0].get_value() == 1.0
	assert ed.sens_widgets[1][0].get_value() == 1.0, \
		"Y must be cleared along with X"


def test_clear_y_does_not_clear_x():
	ed = _mk_editor(Action.AC_STICK)
	ed.builder.get_object("cbSensLockXY").set_active(True)
	ed.sens_widgets[0][0].set_value(4.0)

	ed.on_btClearSens_clicked(ed.sens_widgets[1][2])

	assert ed.sens_widgets[0][0].get_value() == 4.0, \
		"clearing Y must not touch X"


def test_generate_modifiers_produces_locked_sens():
	ed = _mk_editor(Action.AC_STICK)
	ed.builder.get_object("cbSensLockXY").set_active(True)
	ed.sens_widgets[0][0].set_value(2.0)
	ed._modifiers_enabled = True
	ed.sens = [2.0, 2.0, 1.0]

	a = ed.generate_modifiers(REL_XY)

	assert isinstance(a, SensitivityModifier)
	assert a.speeds[0] == 2.0 and a.speeds[1] == 2.0


def test_generate_modifiers_unlocked_keeps_xy_split():
	ed = _mk_editor(Action.AC_STICK)
	ed.sens = [2.0, 0.5, 1.0]
	ed._modifiers_enabled = True

	a = ed.generate_modifiers(REL_XY)

	assert isinstance(a, SensitivityModifier)
	assert a.speeds[0] == 2.0 and a.speeds[1] == 0.5
