from collections import namedtuple

import scc.drivers.hiddrv as hiddrv
from scc.constants import SCButtons
from scc.drivers.hiddrv import HIDControllerInput, HIDDecoder, HIDDrv, HIDRawController
from scc.drivers.input_smoothing import InputSmoother

State = namedtuple("State", "buttons stick_x stick_y lpad_x lpad_y")


class FakeMonitor:
	def __init__(self):
		self.dev_added_cbs = {}

	def add_callback(self, subsystem, vendor, product, added_cb, removed_cb):
		self.dev_added_cbs[subsystem, vendor, product] = added_cb


class FakeDaemon:
	def __init__(self):
		self.monitor = FakeMonitor()

	def get_device_monitor(self):
		return self.monitor


class FakeMapper:
	def __init__(self):
		self.inputs = []

	def input(self, controller, old_state, state):
		self.inputs.append((old_state, state))


def test_shared_smoother_supports_namedtuples_and_touch_edges():
	smoother = InputSmoother(fields=("stick_x", "stick_y", "lpad_x", "lpad_y"))
	smoother.process(State(0, 0, 0, 0, 0))
	trash, contact = smoother.process(State(SCButtons.LPADTOUCH, 300, -300, 900, -400))
	trash, held = smoother.process(State(SCButtons.LPADTOUCH, 600, -600, 900, -400))

	assert contact.stick_x == 150
	assert held.stick_x == 300
	assert contact.lpad_x == held.lpad_x == 900
	assert contact.lpad_y == held.lpad_y == -400


def test_generic_hid_driver_registers_bluetooth_hidraw_callback():
	driver = object.__new__(HIDDrv)
	driver.daemon = FakeDaemon()
	driver.bt_registered = set()
	driver.bt_callbacks = {}

	driver._register_bluetooth(0x1234, 0xABCD)

	key = ("bluetooth", 0x1234, 0xABCD)
	assert key in driver.daemon.monitor.dev_added_cbs
	assert (0x1234, 0xABCD) in driver.bt_registered


def test_generic_bluetooth_hidraw_input_is_smoothed(monkeypatch):
	controller = object.__new__(HIDRawController)
	controller._fileno = 42
	controller._packet_size = 8
	controller._decoder = HIDDecoder()
	controller._input_smoother = InputSmoother()
	controller.mapper = FakeMapper()

	monkeypatch.setattr(hiddrv.os, "read", lambda fd, size: b"report")
	monkeypatch.setattr(hiddrv, "_decode", lambda decoder, data: True)

	controller._decoder.state = HIDControllerInput(stick_x=0)
	controller.input()
	controller._decoder.old_state = controller._decoder.state
	controller._decoder.state = HIDControllerInput(stick_x=300)
	controller.input()

	assert len(controller.mapper.inputs) == 2
	assert controller.mapper.inputs[-1][1].stick_x == 150
