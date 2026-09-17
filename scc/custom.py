#!/usr/bin/env python3
"""
SC-Controller - Custom module loader

Loads ~/.config/scc/custom.py, if present. This allows injecting custom action
classes by user and breaking everything in very creative ways.

load_custom_module function needs to be called by daemon and GUI, so it exists
in separate module.
"""

import os

from scc.paths import get_config_path


def load_custom_module(log, who_calls="daemon"):
	"""
	Loads and imports ~/.config/scc/custom.py, if it is present and displays
	big, fat warning in such case.

	Returns True if file exists.
	"""

	filename = os.path.join(get_config_path(), "custom.py")
	if os.path.exists(filename):
		log.warning("=" * 60)
		log.warning(f"Loading {filename}")
		log.warning(
			"If you don't know what this means or you haven't created it, stop daemon right now and remove this file."
		)
		log.warning("")
		log.warning(f"Also try removing it if {who_calls} crashes shortly after this message.")

		import importlib.util

		spec = importlib.util.spec_from_file_location("custom", filename)
		if spec is not None and spec.loader is not None:
			module = importlib.util.module_from_spec(spec)
			spec.loader.exec_module(module)
		log.warning("=" * 60)
		return True
	return False
