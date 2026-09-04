#!/usr/bin/env python3
"""
SC-Controller - Input Names

Central place for human readable names of physical controller inputs
(buttons, pads, sticks, triggers, ...).

By default, each input has a generic name (see DEFAULT_INPUT_NAMES).
Controller types can override those by adding a "names" map to the "gui"
section of their config json file like this:

    {
        "gui": {
            "background": "sc2",
            "names": { "LB": "L1", "RB": "R1" }
        }
    }

Registered devices (files in ~/.config/scc/devices/) can do the same!
"""
from __future__ import unicode_literals
from scc.tools import nameof

# Default, controller-agnostic names for inputs.
# Keys are input ids as used in profiles and by the GUI (SCButtons names,
# Profile constants, trigger ids, ...).
DEFAULT_INPUT_NAMES = {
	# Face buttons
	'A'			: 'A',
	'B'			: 'B',
	'X'			: 'X',
	'Y'			: 'Y',
	'C'			: 'Center',
	'BACK'		: 'Back',
	'START'		: 'Start',
	'DOTS'		: 'Quick Access',
	# Shoulders and triggers
	'LB'		: 'LB',
	'RB'		: 'RB',
	'LT'		: 'LT',
	'RT'		: 'RT',
	'LEFT'		: 'Left Trigger',
	'RIGHT'		: 'Right Trigger',
	# Grips
	'LGRIP'		: 'Left Grip',
	'RGRIP'		: 'Right Grip',
	'LGRIP2'	: 'Left Grip 2',
	'RGRIP2'	: 'Right Grip 2',
	# Pads, sticks, dpad, gyro
	'LPAD'		: 'Left Pad',
	'RPAD'		: 'Right Pad',
	'CPAD'		: 'Touch Pad',
	'STICK'		: 'Left Stick',
	'RSTICK'	: 'Right Stick',
	'DPAD'		: 'D-Pad',
	'GYRO'		: 'Gyro',
	# Touch variants
	'LPADTOUCH'		: 'Left Pad',
	'RPADTOUCH'		: 'Right Pad',
	'CPADTOUCH'		: 'Touch Pad',
	'LSTICKTOUCH'	: 'Left Stick Touch',
	'RSTICKTOUCH'	: 'Right Stick Touch',
	'LSENSE'		: 'Left Grip',
	'RSENSE'		: 'Right Grip',
}



def get_input_name(id, config=None, default=None):
	"""
	Returns display name for input 'id' (SCButton, Profile constant or
	string).
	"""
	key = nameof(id)
	names = {}
	if config:
		try:
			names = config.get("gui", {}).get("names", {}) or {}
		except AttributeError:
			names = {}
	if key in names:
		return names[key]
	if default is not None:
		return default
	if key in DEFAULT_INPUT_NAMES:
		return DEFAULT_INPUT_NAMES[key]
	if key.endswith("PRESS"):
		# No default for this pressed variant (e.g. RSTICKPRESS);
		# show base input name with " Press" appended, e.g. "Right Stick Press".
		base = key[:-len("PRESS")]
		if base:
			return get_input_name(base, config) + " Press"
	return key


def get_app_config(app):
	"""
	Returns gui config of controller currently displayed by the
	application, or None when there is none.
	"""
	for a in (app, getattr(app, "app", None)):
		background = getattr(a, "background", None)
		if background is not None:
			try:
				return background.get_config()
			except Exception:
				return None
	return None
