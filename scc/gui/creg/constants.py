#!/usr/bin/env python3
"""
SC-Controller - Controller Registration Constants

Just huge chunk of constants put aside to make impotant code more readable
"""
from __future__ import unicode_literals

from scc.constants import SCButtons, STICK, RSTICK, DPAD
from scc.gui import BUTTON_ORDER

# Actual dpad buttons
BUTTON_ORDER = tuple( b for b in BUTTON_ORDER
		if b not in (SCButtons.LPAD, SCButtons.RPAD) ) \
		+ (SCButtons.RSTICKPRESS,)

X = 0
Y = 1

AXIS_ORDER = (
	("stick_x", X), ("stick_y", Y),
	("rstick_x", X), ("rstick_y", Y),
	("dpad_x", X),  ("dpad_y", Y),
	("ltrig", X),	# index 6
	("rtrig", X),
)

STICK_PAD_AREAS = {
	# Numbers here are indexes to AXIS_ORDER tuple
	"STICK":	(STICK, (0, 1)),
	"RSTICK":	(RSTICK, (2, 3)),
	"DPAD":		(DPAD, (4, 5)),
}

TRIGGER_AREAS = {
	# Numbers here are indexes to AXIS_ORDER tuple
	"LT": 6,
	"RT": 7
}

AXIS_TO_BUTTON = {
	# Maps stick and dpad axes to their respective "pressed" button
	"stick_x":	SCButtons.STICKPRESS,
	"stick_y":	SCButtons.STICKPRESS,
	"rstick_x":	SCButtons.RSTICKPRESS,
	"rstick_y":	SCButtons.RSTICKPRESS,
}

SDL_TO_SCC_NAMES = {
	'guide':			'C',
	'leftstick':		'STICKPRESS',
	'rightstick':		'RSTICKPRESS',
	'leftshoulder':		'LB',
	'rightshoulder':	'RB',
}

SDL_AXES = (
	# This tuple has to use same order as AXIS_ORDER
	'leftx', 'lefty',
	'rightx', 'righty',
	"dpadx", "dpady",
	'lefttrigger',
	'righttrigger'
)


SDL_DPAD = {
	# Numbers here are indexes to AXIS_ORDER tuple
	# Booleans here are True for positive movements (up/right) and
	# False for negative (down/left), same convention as Deck/SC2 dpad
	# (dpad_x positive = right, dpad_y positive = up)
	'dpdown':	(5, False),
	'dpleft':	(4, False),
	'dpright':	(4, True),
	'dpup':		(5, True),
}
