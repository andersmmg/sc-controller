import json
from pathlib import Path

from scc.actions import ButtonAction
from scc.gui.area_to_action import AREA_TO_ACTION
from scc.uinput import Keys

ROOT = Path(__file__).resolve().parents[1]
XBOX_PROFILES = (
	"XBox Controller.sccprofile",
	"XBox Controller with High Precision Camera.sccprofile",
)


def test_standard_gamepad_face_button_aliases():
	# Linux's legacy aliases use the Nintendo-style face-button
	# names for some reason idk
	assert Keys.BTN_NORTH == Keys.BTN_X
	assert Keys.BTN_WEST == Keys.BTN_Y


def test_binding_chooser_uses_standard_xbox_face_button_positions():
	assert AREA_TO_ACTION["X"][1] == Keys.BTN_WEST
	assert AREA_TO_ACTION["Y"][1] == Keys.BTN_NORTH
	assert ButtonAction.SPECIAL_NAMES[Keys.BTN_WEST] == "X Button"
	assert ButtonAction.SPECIAL_NAMES[Keys.BTN_NORTH] == "Y Button"


def test_bundled_xbox_profiles_map_x_and_y_to_standard_positions():
	for filename in XBOX_PROFILES:
		with open(ROOT / "default_profiles" / filename) as profile_file:
			buttons = json.load(profile_file)["buttons"]
		assert buttons["X"]["action"] == "button(Keys.BTN_WEST)"
		assert buttons["Y"]["action"] == "button(Keys.BTN_NORTH)"
