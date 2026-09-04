"""
Tests for scc.device_monitor hotplug reliability

DeviceMonitor requires real libudev, so instances are created via
object.__new__ with stubbed internals, which so far seems to work
"""
from scc.device_monitor import DeviceMonitor
from scc.lib.eudevmonitor import Monitor
from scc.poller import Poller

import logging
logging.disable(logging.CRITICAL)


def make_event(action, subsystem, syspath, initialized=True):
	return Monitor.DeviceEvent(
		action, None, initialized, subsystem, None, syspath, None)


def make_monitor(events, has_data):
	"""
	Creates DeviceMonitor instance with on_data_ready dependencies stubbed
	"""
	dm = object.__new__(DeviceMonitor)
	dm._monitor = None		# keep Monitor.__del__ happy
	dm.known_devs = {}
	dm._added = []
	dm._removed = []
	dm._rescans = []

	def receive_device():
		if events:
			return events.pop(0)
		return None

	def on_new_syspath(subsystem, syspath):
		dm._added.append((subsystem, syspath))
		dm.known_devs[syspath] = ("v", "p", on_removed)

	def on_removed(syspath, vendor, product):
		dm._removed.append(syspath)

	def rescan():
		dm._rescans.append(1)

	dm.receive_device = receive_device
	dm._on_new_syspath = on_new_syspath
	dm._get_hci_addresses = lambda: None
	dm.rescan = rescan
	if has_data:
		dm._has_data = lambda: bool(has_data.pop(0))
	else:
		dm._has_data = lambda: False
	return dm


def test_drains_all_events():
	""" All events queued in socket are processed in single wakeup """
	dm = make_monitor([
		make_event("add", "input", "/sys/a/event3"),
		make_event("bind", "input", "/sys/a/event4"),
		make_event("add", "input", "/sys/a/event5"),
	], [ True, True, True, False ])

	dm.on_data_ready()

	# 'add' and 'bind' events for unknown syspaths both add the device
	assert dm._added == [
		("input", "/sys/a/event3"), ("input", "/sys/a/event4"), ("input", "/sys/a/event5") ]
	assert not dm._rescans

	dm2 = make_monitor([
		make_event("add", "input", "/sys/a/event3"),
		make_event("bind", "input", "/sys/a/event3"),
	], [ True, True, False ])
	dm2.on_data_ready()
	# bind event for already known device is skipped
	assert dm2._added == [ ("input", "/sys/a/event3") ]


def test_remove_event_pops_known_device():
	""" remove event calls removal callback and drops device from known_devs """
	dm = make_monitor([], [])
	dm.known_devs["/sys/a/event3"] = ("v", "p", lambda *a: dm._removed.append("/sys/a/event3"))
	dm.receive_device = lambda: make_event("remove", "input", "/sys/a/event3")
	# single event queued, then socket drained
	dm._has_data = iter([True, False]).__next__

	dm.on_data_ready()

	assert dm._removed == [ "/sys/a/event3" ]
	assert "/sys/a/event3" not in dm.known_devs


def test_overrun_triggers_rescan():
	""" Readable socket with no event means buffer overrun -> rescan once """
	dm = make_monitor([ None ], [ True, True, True ])

	dm.on_data_ready()

	assert dm._rescans == [ 1 ]
	assert not dm._added


def test_rescan_adds_new_device():
	""" rescan adds devices not yet known """
	dm = object.__new__(DeviceMonitor)
	dm._monitor = None		# keep Monitor.__del__ happy
	dm.known_devs = {}
	dm.dev_added_cbs = { ("input", None, None): None }
	dm._added = []
	dm._removed = []
	dm._rescans = []

	class FakeEnumerator(object):
		def __init__(self, paths): self.paths, self._started = paths, False
		def match_subsystem(self, s): return self
		def __iter__(self): return iter(self.paths)

	dm._eudev = type("FakeEudev", (), { "enumerate": lambda self: FakeEnumerator(["/sys/a/event3"]) })()
	dm._get_hci_addresses = lambda: None

	def on_new_syspath(subsystem, syspath):
		dm._added.append((subsystem, syspath))
		dm.known_devs[syspath] = ("v", "p", None)

	dm._on_new_syspath = on_new_syspath
	old = DeviceMonitor.get_subsystem
	DeviceMonitor.get_subsystem = staticmethod(lambda p: "input")
	try:
		dm.rescan()
	finally:
		DeviceMonitor.get_subsystem = old

	assert dm._added == [ ("input", "/sys/a/event3") ]
	assert "/sys/a/event3" in dm.known_devs


def test_start_tolerates_buffer_size_failure():
	""" start() must not crash when set_receive_buffer_size fails (unprivileged daemon) """
	dm = object.__new__(DeviceMonitor)
	dm._monitor = None
	dm._monitor_started = False

	class FakeLib(object):
		def udev_monitor_enable_receiving(self, monitor):
			return 0
	class FakeEudev(object):
		_lib = FakeLib()
	dm._eudev = FakeEudev()

	class FakePoller(object):
		POLLIN = Poller.POLLIN
		def __init__(self):
			self.registered = []
		def register(self, fd, events, cb):
			self.registered.append((fd, events, cb))
	poller = FakePoller()

	class FakeScheduler(object):
		def __init__(self):
			self.scheduled = []
		def schedule(self, delay, cb):
			self.scheduled.append((delay, cb))
			return None

	class FakeDaemon(object):
		def __init__(self):
			self.poller = poller
			self._sched = FakeScheduler()
		def get_scheduler(self):
			return self._sched

	dm.daemon = FakeDaemon()
	dm.fileno = lambda: 42

	def failing_set(*a):
		raise OSError("udev_monitor_set_receive_buffer_size: error -1")
	dm.set_receive_buffer_size = failing_set

	dm.start()

	# monitor still registered, started and periodic rescan scheduled
	assert poller.registered == [ (42, Poller.POLLIN, dm.on_data_ready) ]
	assert dm._monitor_started
	assert len(dm.daemon._sched.scheduled) == 1
	assert dm.daemon._sched.scheduled[0][0] == 5.0


def test_get_hci_addresses_closes_fd():
	""" hci fd must be closed even when ioctl fails (no fd leak per rescan) """
	import os as real_os
	import scc.device_monitor as dm_mod

	dm = object.__new__(DeviceMonitor)
	dm._monitor = None
	dm.bt_addresses = {}
	dm._last_bt_warn = 0

	read_fd, write_fd = real_os.pipe()

	class FakeBtlib(object):
		def hci_get_route(self, a):
			return 0
		def hci_open_dev(self, dev):
			return write_fd

	orig_have, orig_btlib = dm_mod.HAVE_BLUETOOTH_LIB, dm_mod.btlib
	orig_ioctl = dm_mod.fcntl.ioctl
	try:
		dm_mod.HAVE_BLUETOOTH_LIB = True
		dm_mod.btlib = FakeBtlib()
		dm_mod.fcntl.ioctl = lambda *a, **k: (_ for _ in ()).throw(OSError("denied"))

		dm._get_hci_addresses()

		# fd returned by hci_open_dev was closed despite ioctl failure
		try:
			real_os.fstat(write_fd)
			assert False, "hci fd was not closed"
		except OSError:
			pass
	finally:
		real_os.close(read_fd)
		dm_mod.HAVE_BLUETOOTH_LIB, dm_mod.btlib = orig_have, orig_btlib
		dm_mod.fcntl.ioctl = orig_ioctl


def test_periodic_rescan_gated_by_uevent_seqnum():
	""" full rescan only runs when kernel uevent seqnum advanced """
	dm = object.__new__(DeviceMonitor)
	dm._monitor = None
	dm._last_seqnum = None
	dm._ticks = 0
	dm._last_bt_warn = 0

	seqs = [ 100, 100, 101, 101 ]
	dm._read_uevent_seqnum = lambda: seqs.pop(0)

	class FakeScheduler(object):
		def __init__(self):
			self.n = 0
		def schedule(self, delay, cb):
			self.n += 1
			return None
	sched = FakeScheduler()
	class FakeDaemon(object):
		def get_scheduler(self):
			return sched
	dm.daemon = FakeDaemon()

	calls = []
	dm.rescan = lambda: calls.append(1)

	dm._periodic_rescan()	# first tick always rescans
	dm._periodic_rescan()	# seq unchanged
	dm._periodic_rescan()	# seq advanced
	dm._periodic_rescan()	# seq unchanged

	assert len(calls) == 2
	assert sched.n == 4


def test_periodic_rescan_forced_every_n_ticks():
	""" full rescan still happens occasionally even with no uevents """
	from scc.device_monitor import FORCE_RESCAN_TICKS
	dm = object.__new__(DeviceMonitor)
	dm._monitor = None
	dm._last_seqnum = 100
	dm._ticks = 0
	dm._last_bt_warn = 0

	dm._read_uevent_seqnum = lambda: 100
	class FakeScheduler(object):
		def schedule(self, delay, cb):
			return None
	dm.daemon = type("D", (), { "get_scheduler": lambda self: FakeScheduler() })()

	calls = []
	dm.rescan = lambda: calls.append(1)

	for i in range(FORCE_RESCAN_TICKS):
		dm._periodic_rescan()

	# with seqnum unchanged, only every FORCE_RESCAN_TICKS-th tick rescans
	assert len(calls) == 1

	for i in range(FORCE_RESCAN_TICKS):
		dm._periodic_rescan()

	assert len(calls) == 2


def test_periodic_rescan_fallback_when_seqnum_unreadable():
	""" without uevent seqnum, rescan runs every tick (old behaviour) """
	dm = object.__new__(DeviceMonitor)
	dm._monitor = None
	dm._last_seqnum = None
	dm._ticks = 0
	dm._last_bt_warn = 0

	dm._read_uevent_seqnum = lambda: None
	class FakeScheduler(object):
		def schedule(self, delay, cb):
			return None
	dm.daemon = type("D", (), { "get_scheduler": lambda self: FakeScheduler() })()

	calls = []
	dm.rescan = lambda: calls.append(1)

	for i in range(3):
		dm._periodic_rescan()

	assert len(calls) == 3

def test_retry_cancel_accepts_full_callback_args():
	"""
	Removal callbacks are invoked as cb(syspath, vendor, product);
	sc_by_bt's _retry_cancel must tolerate the extra arguments.
	"""
	from scc.drivers.sc_by_bt import Driver
	d = object.__new__(Driver)
	d.reconnecting = { "/sys/a/bt1" }

	d._retry_cancel("/sys/a/bt1", 0x28de, 0x1106)

	assert d.reconnecting == set()
	# Firing again (eg. device removed after reconnect already fired) must
	# not raise KeyError!
	d._retry_cancel("/sys/a/bt1", 0x28de, 0x1106)


def test_rescan_removes_missing_device():
	""" rescan fires removal callback for device gone from sysfs """
	dm = object.__new__(DeviceMonitor)
	dm._monitor = None		# keep Monitor.__del__ happy
	dm.known_devs = { "/sys/a/event3": ("v", "p", None),
		"/sys/a/gone": ("v", "p", lambda *a: dm._removed.append("/sys/a/gone")) }
	dm.dev_added_cbs = { ("input", None, None): None }
	dm._removed = []

	class FakeEnumerator(object):
		def __init__(self, paths): self.paths = paths
		def match_subsystem(self, s): return self
		def __iter__(self): return iter(self.paths)

	dm._eudev = type("FakeEudev", (), { "enumerate": lambda self: FakeEnumerator(["/sys/a/event3"]) })()
	dm._get_hci_addresses = lambda: None
	dm._on_new_syspath = lambda s, p: None

	old = DeviceMonitor.get_subsystem
	DeviceMonitor.get_subsystem = staticmethod(lambda p: "input")
	try:
		dm.rescan()
	finally:
		DeviceMonitor.get_subsystem = old

	assert dm._removed == [ "/sys/a/gone" ]
	assert "/sys/a/gone" not in dm.known_devs
	assert "/sys/a/event3" in dm.known_devs
