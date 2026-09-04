from scc.constants import SCButtons, STICK, RSTICK, DPAD, GYRO
from scc.gui.input_names import get_input_name, get_app_config, DEFAULT_INPUT_NAMES

"""
Tests for centralized input name lookup (default names + per-controller
overrides from gui config "names" map)
"""


class _FakeBackground(object):
	def __init__(self, config):
		self._config = config

	def get_config(self):
		return self._config


class _FakeApp(object):
	def __init__(self, config):
		self.background = _FakeBackground(config)


def test_default_names():
	assert get_input_name("LPAD") == "Left Pad"
	assert get_input_name("RPAD") == "Right Pad"
	assert get_input_name("LB") == "LB"
	assert get_input_name("RB") == "RB"
	assert get_input_name(STICK) == "Left Stick"
	assert get_input_name(RSTICK) == "Right Stick"
	assert get_input_name(DPAD) == "D-Pad"
	assert get_input_name(GYRO) == "Gyro"
	assert get_input_name(SCButtons.LGRIP) == "Left Grip"
	assert get_input_name(SCButtons.LT) == "LT"


def test_unknown_input_falls_back_to_raw_name():
	assert get_input_name("SOMETHING_UNKNOWN") == "SOMETHING_UNKNOWN"


def test_controller_override_takes_precedence():
	config = { "gui": { "names": { "LB": "L1", "RB": "R1" } } }
	assert get_input_name("LB", config) == "L1"
	assert get_input_name("RB", config) == "R1"
	assert get_input_name("LPAD", config) == "Left Pad"


def test_press_variant_defaults_to_base_plus_press():
	assert get_input_name("RSTICKPRESS") == "Right Stick Press"
	assert get_input_name("STICKPRESS") == "Left Stick Press"
	assert get_input_name("CPADPRESS") == "Touch Pad Press"
	assert get_input_name("LPADPRESS") == "Left Pad Press"
	assert get_input_name("RPADPRESS") == "Right Pad Press"
	# enums
	assert get_input_name(SCButtons.RSTICKPRESS) == "Right Stick Press"
	assert get_input_name(SCButtons.STICKPRESS) == "Left Stick Press"


def test_press_variant_override_used_verbatim():
	config = { "gui": { "names": { "RSTICKPRESS": "L3" } } }
	assert get_input_name("RSTICKPRESS", config) == "L3"
	assert get_input_name(SCButtons.RSTICKPRESS, config) == "L3"
	assert get_input_name("RSTICKPRESS", config, "Right Stick Press") == "L3"


def test_press_variant_composes_with_base_override():
	config = { "gui": { "names": { "STICK": "Left Joystick" } } }
	assert get_input_name("STICKPRESS", config) == "Left Joystick Press"


def test_override_applies_to_enum_values():
	config = { "gui": { "names": { "LB": "L1" } } }
	assert get_input_name(SCButtons.LB, config) == "L1"


def test_explicit_default_is_used_when_no_override():
	config = { "gui": { "names": {} } }
	assert get_input_name("LB", config, "Left Bumper") == "Left Bumper"
	config = { "gui": { "names": { "LB": "L1" } } }
	assert get_input_name("LB", config, "Left Bumper") == "L1"


def test_config_without_names_map():
	assert get_input_name("LB", { "gui": { "background": "x360" } }) == "LB"
	assert get_input_name("LPAD", None) == "Left Pad"


def test_get_app_config():
	config = { "gui": { "names": { "LB": "L1" } } }
	app = _FakeApp(config)
	assert get_app_config(app) == config
	class _Editor(object):
		def __init__(self, app):
			self.app = app
	assert get_app_config(_Editor(app)) == config


def test_get_app_config_without_background():
	assert get_app_config(None) is None
	assert get_app_config(object()) is None
	assert get_app_config(_FakeApp(None)) is None


def test_defaults_cover_all_scbuttons():
	""" Every SCButtons member has a default name (or is intentionally raw) """
	raw_ok = { "A", "B", "X", "Y", "LB", "RB", "LT", "RT" }
	for button in SCButtons:
		name = get_input_name(button)
		if button.name in raw_ok:
			assert name == button.name
		else:
			assert name != button.name, button.name
