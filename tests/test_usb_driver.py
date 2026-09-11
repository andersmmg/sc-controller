"""
Tests for scc.drivers.usb force_restart / retry queue handling.
"""

import scc.drivers.usb as usb


class FakeDeviceDesc:
	def getVendorID(self):
		return 0x045E

	def getProductID(self):
		return 0x028E


def _make_device(syspath):
	dev = usb.USBDevice.__new__(usb.USBDevice)
	dev.device = FakeDeviceDesc()
	dev.syspath = syspath
	dev._claimed = []
	dev.closed = False
	dev.close = lambda: setattr(dev, "closed", True)
	return dev


def test_force_restart_queues_syspath_and_tp():
	dev = _make_device("/sys/bus/usb/devices/3-7")
	saved = usb._usb._retry_devices
	usb._usb._retry_devices = lst = []
	try:
		dev.force_restart()
		assert dev.closed
		assert lst == [("/sys/bus/usb/devices/3-7", (0x045E, 0x028E))]
	finally:
		usb._usb._retry_devices = saved


def test_retry_consumer_unpacks_force_restart_entry():
	dev = _make_device("/sys/bus/usb/devices/3-7")
	saved = usb._usb._retry_devices
	usb._usb._retry_devices = lst = []
	try:
		dev.force_restart()
		for syspath, (vendor, product) in lst:
			assert syspath == "/sys/bus/usb/devices/3-7"
			assert (vendor, product) == (0x045E, 0x028E)
	finally:
		usb._usb._retry_devices = saved


def test_force_restart_without_syspath_is_guarded():
	dev = _make_device(None)
	saved = usb._usb._retry_devices
	usb._usb._retry_devices = lst = []
	try:
		dev.force_restart()
		assert not dev.closed
		assert lst == []
	finally:
		usb._usb._retry_devices = saved


class _Failing:
	"""Device whose flush() raises USBErrorPipe, recording call order."""

	def __init__(self, events):
		self.events = events
		self.closed = False

	def flush(self):
		self.events.append("flush:dead")
		raise usb.usb1.USBErrorPipe(-1)

	def close(self):
		self.closed = True
		self.events.append("close:dead")


class _Healthy:
	def __init__(self, events):
		self.events = events
		self.flushed = 0
		self.closed = False

	def flush(self):
		self.flushed += 1
		self.events.append("flush:ok")

	def close(self):
		self.closed = True
		self.events.append("close:ok")


def test_mainloop_closes_dead_devices_after_iterating_all():
	"""All devices are flushed first; failing ones closed after, not during."""
	events = []
	dead, healthy = _Failing(events), _Healthy(events)
	saved = usb._usb._devices
	usb._usb._devices = {"/sys/dead": dead, "/sys/ok": healthy}
	try:
		usb._usb.mainloop()
		assert events == ["flush:dead", "flush:ok", "close:dead"]
		assert dead.closed
		assert healthy.flushed == 1
		assert not healthy.closed
		assert "/sys/dead" not in usb._usb._devices
		assert "/sys/ok" in usb._usb._devices
	finally:
		usb._usb._devices = saved


def test_mainloop_keeps_healthy_devices_when_none_fail():
	"""No flush errors, nothing closed, nothing removed."""
	healthy = _Healthy([])
	saved = usb._usb._devices
	usb._usb._devices = {"/sys/ok": healthy}
	try:
		usb._usb.mainloop()
		assert healthy.flushed == 1
		assert not healthy.closed
		assert list(usb._usb._devices) == ["/sys/ok"]
	finally:
		usb._usb._devices = saved
