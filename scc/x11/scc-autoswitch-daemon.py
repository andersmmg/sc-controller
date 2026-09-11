#!/usr/bin/env python3
"""
SC-Controller - Autoswitch Daemon

Observes active window and commands scc-daemon to change profiles as needed.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
	sys.path.insert(0, _ROOT)
if not os.environ.get("SCC_SHARED") and os.path.isdir(os.path.join(_ROOT, "glade")):
	os.environ["SCC_SHARED"] = _ROOT

import logging
import os
import signal
import sys

from scc.tools import set_logging_level
from scc.x11.autoswitcher import AutoSwitcher

log = logging.getLogger("AS-Daemon")


if __name__ == "__main__":
	from scc.tools import init_logging, set_logging_level

	init_logging(suffix=" AS ")
	set_logging_level("debug" in sys.argv, "debug" in sys.argv)

	if "DISPLAY" not in os.environ and "WAYLAND_DISPLAY" not in os.environ:
		log.error("Neither DISPLAY nor WAYLAND_DISPLAY env variable is set.")
		sys.exit(1)

	d = AutoSwitcher()
	signal.signal(signal.SIGINT, d.sigint)
	d.run()
	sys.exit(d.exit_code)
