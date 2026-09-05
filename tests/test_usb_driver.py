"""
Tests for scc.drivers.usb force_restart / retry queue handling.
"""
import scc.drivers.usb as usb


class FakeDeviceDesc(object):
	def getVendorID(self):
		return 0x045e

	def getProductID(self):
		return 0x028e


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
		assert lst == [("/sys/bus/usb/devices/3-7", (0x045e, 0x028e))]
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
			assert (vendor, product) == (0x045e, 0x028e)
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
