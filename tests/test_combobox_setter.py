import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from scc.gui.editor import ComboSetter, canonical_action_string

STICK_KEY = "mode(RGRIP, OSK.move(), dpad(button(KEY_UP), button(KEY_DOWN), button(KEY_LEFT), button(KEY_RIGHT)))"
TRIGGERS_KEY = "trigger(50, button(KEY_LEFTSHIFT))|trigger(50, button(KEY_LEFTCTRL))"


class FakeComboSetter(ComboSetter):
	def __init__(self):
		self._recursing = False


def _make_combo(rows):
	store = Gtk.ListStore(str, str, bool)
	for label, action, custom in rows:
		store.append((label, action, custom))
	cb = Gtk.ComboBox.new_with_model(store)
	return cb


def test_canonical_strips_enum_prefixes():
	assert canonical_action_string("button(Keys.KEY_UP)") == "button(KEY_UP)"
	assert canonical_action_string(
			"trigger(50, button(Keys.KEY_LEFTSHIFT))|trigger(50, button(Keys.KEY_LEFTCTRL))"
	) == TRIGGERS_KEY
	assert canonical_action_string(
			"mode(LGRIP, OSK.move(), dpad(button(Keys.KEY_UP), button(Keys.KEY_DOWN),"
			" button(Keys.KEY_LEFT), button(Keys.KEY_RIGHT)))"
	) == STICK_KEY.replace("RGRIP", "LGRIP")
	assert canonical_action_string("profile('default.sccprofile')") == \
			"profile('default.sccprofile')"
	assert canonical_action_string(TRIGGERS_KEY) == TRIGGERS_KEY


def test_canonical_leaves_non_strings_alone():
	assert canonical_action_string(None) is None
	assert canonical_action_string(50) == 50


def test_set_cb_matches_bare_and_prefixed_variants():
	setter = FakeComboSetter()
	rows = [
		("Move Keyboard", "OSK.move()", False),
		("Emulate Arrows", "dpad(button(Keys.KEY_UP), button(Keys.KEY_DOWN), button(Keys.KEY_LEFT), button(Keys.KEY_RIGHT))", False),
		("Emulate Arrows, Move Keyboard when Right Grip is Pressed", STICK_KEY.replace("RGRIP", "LGRIP"), False),
	]
	rows[-1] = ("Emulate Arrows, Move Keyboard when Right Grip is Pressed",
			"mode(RGRIP, OSK.move(), dpad(button(Keys.KEY_UP), button(Keys.KEY_DOWN), button(Keys.KEY_LEFT), button(Keys.KEY_RIGHT)))", False)
	cb = _make_combo(rows)

	assert setter.set_cb(cb, STICK_KEY, keyindex=1)
	assert cb.get_active() == 2

	setter2 = FakeComboSetter()
	rows2 = [
		("Move Keyboard", "OSK.move()", False),
		("Emulate Arrows", "dpad(button(KEY_UP), button(KEY_DOWN), button(KEY_LEFT), button(KEY_RIGHT))", False),
	]
	cb2 = _make_combo(rows2)
	assert setter2.set_cb(cb2,
			"dpad(button(Keys.KEY_UP), button(Keys.KEY_DOWN), button(Keys.KEY_LEFT), button(Keys.KEY_RIGHT))",
			keyindex=1)
	assert cb2.get_active() == 1


def test_set_cb_matches_trigger_combo():
	setter = FakeComboSetter()
	cb = _make_combo([
		("Shift and Ctrl",
		 "trigger(50, button(Keys.KEY_LEFTSHIFT))|trigger(50, button(Keys.KEY_LEFTCTRL))", False),
		("Press Keyboard Buttons", "OSK.press(LEFT)|OSK.press(RIGHT)", False),
	])
	assert setter.set_cb(cb, TRIGGERS_KEY, keyindex=1)
	assert cb.get_active() == 0


def test_set_cb_still_fails_on_unknown_key():
	setter = FakeComboSetter()
	cb = _make_combo([("Move Keyboard", "OSK.move()", False)])
	assert not setter.set_cb(cb, "button(KEY_UP)", keyindex=1)
	assert cb.get_active() == -1


def test_set_cb_exact_match_preferred():
	setter = FakeComboSetter()
	cb = _make_combo([("X", "button(Keys.KEY_UP)", False)])
	assert setter.set_cb(cb, "button(Keys.KEY_UP)", keyindex=1)
	assert cb.get_active() == 0
