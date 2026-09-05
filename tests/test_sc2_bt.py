import os
import struct

import pytest

import scc.drivers.tritondrv as tritondrv
from scc.constants import SCButtons, STICK_PAD_MIN, STICK_PAD_MAX
from scc.drivers.tritondrv import SC2BTDevice, SC2BTDriver


class FakeHidrawDevice(object):
	def __init__(self):
		self.feature_reports = []
		self.closed = False
		self._device = self

	def fileno(self):
		return 42

	def close(self):
		self.closed = True

	def sendFeatureReport(self, report, report_num=0):
		self.feature_reports.append((bytes(report), report_num))

	def getPhysicalAddress(self):
		return b"AA:BB:CC:DD:EE:FF"


class FakeDeviceMonitor(object):
	def __init__(self):
		self.remove_cbs = {}
		self.add_cbs = {}
		self.hidraw = None

	def add_callback(self, subsystem, vendor, product, added_cb, removed_cb):
		self.add_cbs[(subsystem, vendor, product)] = added_cb

	def add_remove_callback(self, syspath, cb):
		self.remove_cbs[syspath] = cb

	def get_hidraw(self, syspath):
		return self.hidraw


class FakeScheduler(object):
	def __init__(self):
		self.tasks = []

	def schedule(self, delay, cb, *data):
		self.tasks.append((delay, cb))

	def run_one(self):
		if self.tasks:
			trash, cb = self.tasks.pop(0)
			cb()


class FakeDaemon(object):
	def __init__(self):
		self.device_monitor = FakeDeviceMonitor()
		self.scheduler = FakeScheduler()
		self.added = []
		self.removed = []

	def get_poller(self):
		return None

	def get_device_monitor(self):
		return self.device_monitor

	def get_scheduler(self):
		return self.scheduler

	def add_controller(self, c):
		self.added.append(c)

	def remove_controller(self, c):
		self.removed.append(c)


class FakeDriver(object):
	def __init__(self, daemon):
		self.daemon = daemon
		self.retried = []
		self.closed = []

	def retry(self, syspath):
		self.retried.append(syspath)

	def _controller_closed(self, syspath, c):
		self.closed.append((syspath, c))


class FakeMapper(object):
	def __init__(self):
		self.inputs = []

	def input(self, c, old_state, new_state):
		self.inputs.append((old_state, new_state))


def make_device(daemon=None, driver=None, hidraw=None):
	daemon = daemon or FakeDaemon()
	driver = driver or FakeDriver(daemon)
	hidraw = hidraw or FakeHidrawDevice()
	dev = SC2BTDevice(driver, "/sys/devices/test", hidraw)
	return dev, daemon, driver, hidraw


def make_state_report(buttons=0, stick=(0, 0), rstick=(0, 0), pads=(0, 0, 0, 0),
		gyro=(0, 0, 0), ble=True):
	data = bytearray(64)
	data[0] = tritondrv.REPORT_STATE_BLE if ble else tritondrv.REPORT_STATE
	struct.pack_into('<IHhhhhh', data, 2, buttons,
		0, 0, stick[0], stick[1], rstick[0], rstick[1])
	struct.pack_into('<hhHhhH', data, 18,
		pads[0], pads[1], 0, pads[2], pads[3], 0)
	struct.pack_into('<hhh', data, 40, *gyro)
	return bytes(data)


def test_state_report_parsed_and_dispatched(monkeypatch):
	dev, daemon, driver, hidraw = make_device()
	dev.mapper = FakeMapper()
	report = make_state_report(
		buttons=1 | (1 << 12), stick=(1000, -2000), gyro=(10, -20, 30))
	monkeypatch.setattr(os, "read", lambda fd, n: report)

	dev._input()

	assert len(dev.mapper.inputs) == 1
	old_state, state = dev.mapper.inputs[0]
	assert old_state == tritondrv.SC2_NULL
	assert state.buttons & SCButtons.A
	assert state.dpad_x == STICK_PAD_MIN
	assert state.stick_x == 1000
	assert state.stick_y == -2000
	assert state.gpitch == -5
	assert state.groll == -10
	assert state.gyaw == 15


def test_touchpad_data_zeroed_when_not_touched(monkeypatch):
	dev, daemon, driver, hidraw = make_device()
	dev.mapper = FakeMapper()
	report = make_state_report(pads=(-300, 400, 500, -600))
	monkeypatch.setattr(os, "read", lambda fd, n: report)

	dev._input()

	trash, state = dev.mapper.inputs[0]
	assert state.lpad_x == 0
	assert state.lpad_y == 0
	assert state.rpad_x == 0
	assert state.rpad_y == 0


def test_battery_report_stored(monkeypatch):
	dev, daemon, driver, hidraw = make_device()
	monkeypatch.setattr(os, "read", lambda fd, n: bytes([0x43, 0, 87]))

	dev._input()

	assert dev.get_battery_level() == 87


def test_feature_report_framing():
	dev, daemon, driver, hidraw = make_device()
	hidraw.feature_reports.clear()	# discard init-time lizard-off report
	payload = struct.pack('<BBBBH',
		tritondrv.FEATURE_REPORT_ID, tritondrv.FEATURE_SET_SETTINGS, 3,
		tritondrv.SETTING_LIZARD_MODE, 0)

	dev._send_feature(payload)

	assert len(hidraw.feature_reports) == 1
	report, report_num = hidraw.feature_reports[0]
	assert report_num == tritondrv.FEATURE_REPORT_ID
	assert report[0:2] == bytes([tritondrv.FEATURE_SET_SETTINGS, 3])
	assert len(report) == 63


def test_output_report_written_as_is(monkeypatch):
	dev, daemon, driver, hidraw = make_device()
	writes = []
	monkeypatch.setattr(os, "write", lambda fd, data: writes.append((fd, data)))
	data = struct.pack('<BBHHBHB', 0x80, 0, 0, 100, 0, 200, 0)

	dev._send_output(data)

	assert writes == [(42, bytes(data))]


def test_read_error_probes_then_recovers(monkeypatch):
	dev, daemon, driver, hidraw = make_device()

	def fail(fd, n):
		raise OSError(5, "I/O error")

	monkeypatch.setattr(os, "read", fail)
	dev._input()

	# single error must not disconnect, only start probing
	assert daemon.removed == []
	assert len(daemon.scheduler.tasks) == 1

	# probe succeeds (fake hidraw works), polling resumes
	daemon.scheduler.run_one()

	assert daemon.removed == []
	assert daemon.scheduler.tasks == []

	# link fails again later: a fresh probe loop starts exactly once
	dev._input()
	assert len(daemon.scheduler.tasks) == 1


def test_io_error_during_probing_is_ignored(monkeypatch):
	dev, daemon, driver, hidraw = make_device()

	def fail(fd, n):
		raise OSError(5, "I/O error")

	monkeypatch.setattr(os, "read", fail)
	dev._input()
	assert len(daemon.scheduler.tasks) == 1

	# further errors while probe loop is pending must not stack loops
	dev._input()
	dev._input()
	assert len(daemon.scheduler.tasks) == 1


def test_repeated_probe_failures_disconnect(monkeypatch):
	dev, daemon, driver, hidraw = make_device()

	def fail(fd, n):
		raise OSError(5, "I/O error")

	monkeypatch.setattr(os, "read", fail)
	dev._input()

	def fail_write(report, report_num=0):
		raise OSError(5, "I/O error")

	monkeypatch.setattr(hidraw, "sendFeatureReport", fail_write)
	for _ in range(tritondrv.BT_PROBE_RETRIES + 1):
		daemon.scheduler.run_one()

	assert daemon.removed == [dev]
	assert driver.retried == ["/sys/devices/test"]
	assert hidraw.closed


def test_feature_report_io_error_after_ready_probes(monkeypatch):
	dev, daemon, driver, hidraw = make_device()

	def fail(report, report_num=0):
		raise OSError(5, "I/O error")

	monkeypatch.setattr(hidraw, "sendFeatureReport", fail)
	dev.turnoff()

	# still not disconnected; recovery attempt is scheduled
	assert daemon.removed == []
	assert len(daemon.scheduler.tasks) == 1


def test_io_error_before_ready_rejects_device():
	daemon, driver = FakeDaemon(), None
	driver = FakeDriver(daemon)
	hidraw = FakeHidrawDevice()

	def fail(report, report_num=0):
		raise OSError(5, "I/O error")

	hidraw.sendFeatureReport = fail
	with pytest.raises(OSError):
		SC2BTDevice(driver, "/sys/devices/test", hidraw)

	assert daemon.added == []
	assert hidraw.closed


def test_close_is_idempotent():
	dev, daemon, driver, hidraw = make_device()

	dev.close()
	dev.close()

	assert hidraw.closed
	assert len(daemon.removed) == 1


def make_working_hidraw(monkeypatch):
	""" Makes driver's HIDRaw open path succeed, returning a fake device """
	monkeypatch.setattr(tritondrv, "HIDRaw", lambda f: FakeHidrawDevice())
	monkeypatch.setattr("builtins.open", lambda path, mode: object())


def test_reconnect_loop_retries_until_success(monkeypatch):
	daemon = FakeDaemon()
	driver = SC2BTDriver(daemon, None)
	syspath = "/sys/devices/test"

	driver.retry(syspath)
	assert daemon.scheduler.tasks	# first attempt scheduled

	# no hidraw node yet, attempt fails and must be rescheduled
	daemon.scheduler.run_one()
	assert daemon.added == []
	assert daemon.scheduler.tasks

	# hidraw node appears, but device init fails (still down)
	daemon.device_monitor.hidraw = "hidraw9"
	monkeypatch.setattr(tritondrv, "HIDRaw",
			lambda f: (_ for _ in ()).throw(OSError(5, "I/O error")))
	monkeypatch.setattr("builtins.open", lambda path, mode: object())
	daemon.scheduler.run_one()
	assert daemon.added == []
	assert daemon.scheduler.tasks	# still rescheduled

	# device finally answers
	make_working_hidraw(monkeypatch)
	daemon.scheduler.run_one()
	assert len(daemon.added) == 1
	assert daemon.scheduler.tasks == []	# loop stopped
	assert syspath not in driver.reconnecting
	assert driver._active[syspath] is daemon.added[0]


def test_reconnect_loop_stops_when_device_removed(monkeypatch):
	daemon = FakeDaemon()
	driver = SC2BTDriver(daemon, None)
	syspath = "/sys/devices/test"

	driver.retry(syspath)

	daemon.device_monitor.remove_cbs[syspath](syspath)
	daemon.scheduler.run_one()

	assert daemon.scheduler.tasks == []
	assert daemon.added == []


def test_stale_retry_is_noop_after_success(monkeypatch):
	daemon = FakeDaemon()
	driver = SC2BTDriver(daemon, None)
	syspath = "/sys/devices/test"
	make_working_hidraw(monkeypatch)
	daemon.device_monitor.hidraw = "hidraw9"

	driver.retry(syspath)
	# controller comes back through normal udev path before retry fires
	c = driver.new_device_callback(syspath)
	assert c is not None

	daemon.scheduler.run_one()

	assert len(daemon.added) == 1
	assert daemon.scheduler.tasks == []


def test_duplicate_add_returns_active_controller(monkeypatch):
	daemon = FakeDaemon()
	driver = SC2BTDriver(daemon, None)
	syspath = "/sys/devices/test"
	make_working_hidraw(monkeypatch)
	daemon.device_monitor.hidraw = "hidraw9"

	c1 = driver.new_device_callback(syspath)
	c2 = driver.new_device_callback(syspath)

	assert c1 is c2
	assert daemon.added == [c1]
