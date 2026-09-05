#!/usr/bin/env python3
"""
SC-Controller - entry-point launchers
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
	sys.path.insert(0, _ROOT)
if not os.environ.get("SCC_SHARED") and os.path.isdir(os.path.join(_ROOT, "glade")):
	os.environ["SCC_SHARED"] = _ROOT


def _sigint_break(code=0):
	import signal
	def handler(*a):
		print("\n*break*")
		sys.exit(code)
	signal.signal(signal.SIGINT, handler)


def scc():
	from scc.scripts import main
	main()


def scc_daemon():
	from scc.sccdaemon import SCCDaemon
	from scc.paths import get_pid_file, get_daemon_socket
	from scc.tools import init_logging
	import argparse

	init_logging()
	parser = argparse.ArgumentParser()
	parser.add_argument('profile', type=str, nargs='*')
	parser.add_argument('command', type=str, choices=['start', 'stop', 'restart', 'debug'])
	parser.add_argument('--alone', action='store_true', help="prevent scc-daemon from launching osd-daemon and autoswitch-daemon")
	parser.add_argument('--once', action='store_true', help="use with 'stop' to send single SIGTERM without waiting for daemon to exit")
	daemon = SCCDaemon(get_pid_file(), get_daemon_socket())
	args = parser.parse_args()
	daemon.alone = args.alone

	profile = " ".join(args.profile)
	if profile:
		daemon.set_default_profile(profile)

	if 'start' == args.command:
		daemon.start()
	elif 'stop' == args.command:
		daemon.stop(once = args.once)
	elif 'restart' == args.command:
		daemon.restart()
	elif 'debug' == args.command:
		daemon.debug()


def sc_controller():
	_sigint_break(0)
	import gi
	gi.require_version('Gtk', '3.0')
	gi.require_version('GdkX11', '3.0')
	gi.require_version('Rsvg', '2.0')

	from scc.tools import init_logging
	from scc.paths import get_share_path
	init_logging()

	from gi.repository import Gtk, GObject
	glades = os.path.join(get_share_path(), "glade")
	images = os.path.join(get_share_path(), "images")
	if Gtk.IconTheme.get_default():
		Gtk.IconTheme.get_default().append_search_path(images)

	from scc.gui.app import App
	App(glades, images).run(sys.argv)


def osd_dialog():
	_sigint_break(-1)
	import gi
	gi.require_version('Gtk', '3.0')
	gi.require_version('Rsvg', '2.0')
	gi.require_version('GdkX11', '3.0')

	from scc.tools import init_logging
	init_logging()

	from scc.osd.dialog import Dialog
	m = Dialog()
	if not m.parse_argumets(sys.argv):
		sys.exit(1)
	m.run()
	if m.get_exit_code() == 0:
		print(m.get_selected_item_id())
	sys.exit(m.get_exit_code())


def osd_keyboard():
	_sigint_break(0)
	import gi
	gi.require_version('Gtk', '3.0')
	gi.require_version('Rsvg', '2.0')
	gi.require_version('GdkX11', '3.0')

	from scc.tools import init_logging
	init_logging()

	from scc.osd.keyboard import Keyboard
	k = Keyboard()
	if not k.parse_argumets(sys.argv):
		sys.exit(1)
	k.run()
	sys.exit(k.get_exit_code())


def osd_launcher():
	_sigint_break(-1)
	import gi
	gi.require_version('Gtk', '3.0')
	gi.require_version('Rsvg', '2.0')
	gi.require_version('GdkX11', '3.0')

	from scc.tools import init_logging
	init_logging()

	from scc.osd.launcher import Launcher
	m = Launcher()
	if not m.parse_argumets(sys.argv):
		sys.exit(1)
	m.run()
	sys.exit(m.get_exit_code())


def osd_menu():
	_sigint_break(-1)
	import gi
	gi.require_version('Gtk', '3.0')
	gi.require_version('Rsvg', '2.0')
	gi.require_version('GdkX11', '3.0')

	from scc.tools import init_logging
	init_logging()

	from scc.osd.menu import Menu
	m = Menu()
	if not m.parse_argumets(sys.argv):
		sys.exit(1)
	m.run()
	if m.get_exit_code() == 0:
		print(m.get_selected_item_id())
	sys.exit(m.get_exit_code())


def osd_message():
	_sigint_break(0)
	import gi
	gi.require_version('Gtk', '3.0')
	gi.require_version('Rsvg', '2.0')
	gi.require_version('GdkX11', '3.0')

	from scc.tools import init_logging
	init_logging()

	from scc.osd.message import Message
	m = Message()
	if not m.parse_argumets(sys.argv):
		sys.exit(1)
	m.run()
	sys.exit(m.get_exit_code())


def osd_radial_menu():
	_sigint_break(-1)
	import gi
	gi.require_version('Gtk', '3.0')
	gi.require_version('Rsvg', '2.0')
	gi.require_version('GdkX11', '3.0')

	from scc.tools import init_logging
	init_logging()

	from scc.osd.radial_menu import RadialMenu
	m = RadialMenu()
	if not m.parse_argumets(sys.argv):
		sys.exit(1)
	m.run()
	if m.get_exit_code() == 0:
		print(m.get_selected_item_id())
	sys.exit(m.get_exit_code())


def osd_show_bindings():
	_sigint_break(-1)
	import gi
	gi.require_version('Gtk', '3.0')
	gi.require_version('Rsvg', '2.0')
	gi.require_version('GdkX11', '3.0')

	from scc.tools import init_logging
	init_logging()

	from scc.osd.binding_display import BindingDisplay
	d = BindingDisplay()
	if not d.parse_argumets(sys.argv):
		sys.exit(1)
	d.run()
	sys.exit(d.get_exit_code())
