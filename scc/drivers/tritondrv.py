#!/usr/bin/env python3
"""
SCC - Steam Controller 2 (Triton) driver

Handles Steam Controller 2 wired directly to USB bus (28de:1302),
wireless controllers connected through Proteus/Nereid dongle
(28de:1304, 28de:1305) and Steam Controller 2 connected over Bluetooth
(28de:1303, BLE mode, using hidraw transport).

Referenced Valve's SDL3 (SDL_hidapi_steam_triton.c and
steam/controller_structs.h) and https://github.com/CouchTurtle/sc2-research

Unlike original SC, Triton reports are multiplexed on a single stream and
reports may have different sizes so a variable length interrupt reader is
used instead of USBDevice.set_input_interrupt

Feature reports are sent as 64B feature report with report id 1:
   { 0x01, type, length, payload... } padded with zeros. Used to keep
lizard mode off (each 3 seconds) and to enable/disable IMU.
Haptics use two output reports: continuous rumble (0x80, 10B) for
repeating/long effects which has to be periodically repeated as the
controller has ~50ms haptic safety timeout, and one-shot click (0x82)
for discrete haptic events
"""

import logging
import math
import struct
import time
import traceback
from collections import namedtuple

from scc.constants import (
	STICK_PAD_MAX,
	STICK_PAD_MIN,
	ControllerFlags,
	HapticPos,
	SCButtons,
)
from scc.controller import Controller
from scc.drivers.usb import USBDevice, register_hotplug_device
from scc.lib import usb1
from scc.lib.hidraw import HIDRaw

import os

VENDOR_ID			= 0x28de
PRODUCT_SC2_WIRED	= 0x1302
PRODUCT_SC2_BLE		= 0x1303 # BLE mode also USB
PRODUCT_PROTEUS		= 0x1304
PRODUCT_NEREID		= 0x1305
DONGLE_PRODUCTS		= (PRODUCT_PROTEUS, PRODUCT_NEREID)

# Input report ids
REPORT_STATE			= 0x42
REPORT_BATTERY			= 0x43
REPORT_STATE_BLE		= 0x45
REPORT_WIRELESS_X		= 0x46
REPORT_STATE_TIMESTAMP	= 0x47
REPORT_LIZARD_MOUSE		= 0x40
REPORT_LIZARD_KEYBOARD	= 0x41
REPORT_LIZARD_STATUS	= 0x7b
REPORT_WIRELESS			= 0x79

# Wired connection state byte in 0x79 report
WIRELESS_CONNECT		= 0x02
WIRELESS_DISCONNECT		= 0x01

# Feature report (control transfer, report id 1)
FEATURE_REPORT_ID		= 1
FEATURE_SET_SETTINGS	= 0x87
FEATURE_TURN_OFF		= 0x9f
CONTROL_VALUE_FEATURE	= 0x0301

# Settings
SETTING_LIZARD_MODE			= 9
SETTING_IMU_MODE			= 48
SETTING_LED_USER_BRIGHTNESS	= 45
IMU_MODE_ENABLED			= 0x18	# SEND_RAW_ACCEL | SEND_RAW_GYRO

# Scales raw gyro int16 into the range the gyro actions expect
GYRO_SCALE = 0.5

# How often lizard mode must be disabled (SDL3 uses 3 seconds)
LIZARD_INTERVAL			= 3.0
# Haptic output report must be resent every 40ms (50ms safety timeout)
RUMBLE_INTERVAL			= 0.040
# Delay between SC2 BT reconnection attempts
BT_RETRY_INTERVAL		= 1.0
BT_PROBE_INTERVAL		= 0.25
BT_PROBE_RETRIES		= 3

# Interface numbers of controller slots on the dongle
DONGLE_SLOT_INTERFACES	= (2, 3, 4, 5)

RUMBLE_OUTPUT_REPORTS	= 10	# report id + MsgHapticRumble

log = logging.getLogger("Triton")

_bt_drv = None


SC2Input = namedtuple("SC2Input", '''buttons ltrig rtrig stick_x stick_y
	rstick_x rstick_y lpad_x lpad_y rpad_x rpad_y
	dpad_x dpad_y gpitch groll gyaw q1 q2 q3 q4''')
SC2_NULL = SC2Input(*([ 0 ] * len(SC2Input._fields)))


# Mapping of Triton button bits (see TritonButtons enum in SDL3) to
# SCButtons used by mapper
TRITON_TO_SC = {
	0  : SCButtons.A,
	1  : SCButtons.B,
	2  : SCButtons.X,
	3  : SCButtons.Y,
	4  : SCButtons.DOTS,			# QAM (the ⋯ / … button, same as Steam Deck DOTS)
	5  : SCButtons.RSTICKPRESS,	# R3
	6  : SCButtons.START,		# View
	7  : SCButtons.RGRIP2,		# R4
	8  : SCButtons.RGRIP,		# R5
	9  : SCButtons.RB,
	14 : SCButtons.BACK,		# Menu
	15 : SCButtons.STICKPRESS,	# L3
	16 : SCButtons.C,		# Steam (same as SC's center/Steam button)
	17 : SCButtons.LGRIP2,		# L4
	18 : SCButtons.LGRIP,		# L5
	19 : SCButtons.LB,
	20 : SCButtons.RSTICKTOUCH,
	21 : SCButtons.RPADTOUCH,
	22 : SCButtons.RPAD,		# RPad click
	23 : SCButtons.RT,			# R trigger click
	24 : SCButtons.LSTICKTOUCH,
	25 : SCButtons.LPADTOUCH,
	26 : SCButtons.LPAD,		# LPad click
	27 : SCButtons.LT,			# L trigger click
	28 : SCButtons.RSENSE,		# Right grip touch
	29 : SCButtons.LSENSE,		# Left grip touch
}
_TRITON_TO_SC_BITS = tuple((1 << b, sc) for b, sc in TRITON_TO_SC.items())


def map_dpad(data, low, hi):
	if data & low:
		return STICK_PAD_MIN
	if data & hi:
		return STICK_PAD_MAX
	return 0


def clamp(value, low, hi):
	if value < low: return low
	if value > hi: return hi
	return value


def init(daemon, config):
	""" Registers hotplug callbacks for all SC2 devices """
	def cb(device, handle):
		return TritonDevice(device, handle, daemon)

	for product_id in (PRODUCT_SC2_WIRED, PRODUCT_SC2_BLE,
			PRODUCT_PROTEUS, PRODUCT_NEREID):
		register_hotplug_device(cb, VENDOR_ID, product_id)
	global _bt_drv
	_bt_drv = SC2BTDriver(daemon, config)
	return True


class TritonDevice(USBDevice):
	"""
	Represents SC2 connected by USB ; handles either wired controller
	(one slot) or dongle with up to 4 wireless slots (one controller per
	endpoint).
	"""
	def __init__(self, device, handle, daemon):
		self.daemon = daemon
		USBDevice.__init__(self, device, handle)
		self._controllers = {}	# slot -> SC2Controller
		self._slots = {}		# slot -> (interface, in_ep, out_ep)
		self._endpoint_to_slot = {}
		self._omsg = []			# Haptics to write to interrupt out endpoint
		self._dongle = device.getProductID() in DONGLE_PRODUCTS

		self.claim_by(klass=3, subclass=0, protocol=0)
		self._find_slots()
		for slot in self._slots:
			self._read_slot(self._slots[slot][1])


	def get_type(self):
		return "sc2"


	def _find_slots(self):
		"""
		Enumerates HID interfaces and assigns each one an IN endpoint a slot.
		On dongle, only interfaces 2..5 are controller slots.
		"""
		ifaces = []
		for inter in self.device[0]:
			for setting in inter:
				number = setting.getNumber()
				if number not in self._claimed:
					continue
				if setting.getClass() != 3:
					continue
				in_ep = out_ep = None
				for ep in setting:
					address = ep.getAddress()
					if address & usb1.ENDPOINT_IN:
						in_ep = address & 0x7f
					else:
						out_ep = address
				if in_ep is not None:
					ifaces.append((number, in_ep, out_ep))
		ifaces.sort()
		for index, (number, in_ep, out_ep) in enumerate(ifaces):
			if self._dongle:
				if number not in DONGLE_SLOT_INTERFACES:
					continue	# dongle status channel, ignored
				slot = DONGLE_SLOT_INTERFACES.index(number)
			else:
				slot = index
			self._slots[slot] = (number, in_ep, out_ep)
			self._endpoint_to_slot[in_ep] = slot


	def _read_slot(self, endpoint):
		"""
		Sets up a interrupt transfer on given endpoint, accepting reports
		of any length (reports are multiplexed on single stream and have
		multiple sizes).
		"""
		def callback_wrapper(transfer):
			if transfer.getStatus() != usb1.TRANSFER_COMPLETED:
				return
			data = transfer.getBuffer()[:transfer.getActualLength()]
			try:
				self._on_input(endpoint, data)
			except Exception as e:
				log.error("Failed to handle SC2 data")
				log.error(e)
				log.error(traceback.format_exc())
			finally:
				try:
					transfer.submit()
				except usb1.USBErrorNoDevice:
					# usb removed
					pass

		transfer = self.handle.getTransfer()
		transfer.setInterrupt(
			usb1.ENDPOINT_IN | endpoint,
			64,
			callback=callback_wrapper,
		)
		transfer.submit()
		self._transfer_list.append(transfer)


	def _on_input(self, endpoint, data):
		if not data:
			return
		slot = self._endpoint_to_slot.get(endpoint)
		if slot is None:
			return
		report = data[0]
		if report in (REPORT_STATE, REPORT_STATE_BLE, REPORT_STATE_TIMESTAMP):
			controller = self._get_controller(slot)
			if controller:
				controller.input(data)
		elif report in (REPORT_WIRELESS, REPORT_WIRELESS_X):
			if len(data) < 2:
				return
			if data[1] == WIRELESS_CONNECT:
				self._get_controller(slot)
			elif data[1] == WIRELESS_DISCONNECT:
				self._remove_controller(slot)
		elif report == REPORT_BATTERY:
			controller = self._controllers.get(slot)
			if controller:
				controller.on_battery(data)
		elif report in (REPORT_LIZARD_MOUSE, REPORT_LIZARD_KEYBOARD, REPORT_LIZARD_STATUS):
			pass
		else:
			log.debug("Ignoring SC2 report type 0x%02x", report)


	def _get_controller(self, slot):
		"""
		Returns controller for slot, creating it when new controller
		connects either by receiving state report or 0x79 connect event.
		"""
		if slot not in self._controllers:
			iface, in_ep, out_ep = self._slots[slot]
			serial = "%s:%s" % (self.device.getBusNumber(),
				self.device.getPortNumber())
			c = SC2Controller(self, iface, out_ep, serial)
			self._controllers[slot] = c
			c.configure()
			self.daemon.add_controller(c)
		return self._controllers.get(slot)


	def _remove_controller(self, slot):
		c = self._controllers.get(slot)
		if c:
			del self._controllers[slot]
			self.daemon.remove_controller(c)
			c.disconnected()


	def _feature(self, index, data):
		"""
		Schedules 64B feature report (report id 1) to be sent to device.
		Reports are overwritten until sent so they don't pile up.
		"""
		data = (data + b'\x00' * 64)[:64]
		key = (index, data[1], data[3:5])
		for x in self._cmsg:
			if (x[3], x[4][1], x[4][3:5]) == key:
				self._cmsg.remove(x)
				break
		self._cmsg.insert(0, (
			0x21,	# request_type
			0x09,	# request
			CONTROL_VALUE_FEATURE,
			index,
			data,
			0		# Timeout
		))


	def rumble(self, out_ep, data):
		"""
		Schedules haptic output report to be sent over interrupt
		endpoint. Overwrites pending haptic for same endpoint.
		"""
		for i, (endpoint, trash) in enumerate(self._omsg):
			if endpoint == out_ep:
				del self._omsg[i]
				break
		self._omsg.insert(0, (out_ep, data))


	def flush(self):
		while len(self._omsg):
			endpoint, data = self._omsg.pop()
			self.handle.interruptWrite(usb1.ENDPOINT_OUT | endpoint, data)
		USBDevice.flush(self)


	def close(self):
		for c in list(self._controllers.values()):
			self.daemon.remove_controller(c)
		self._controllers = {}
		USBDevice.close(self)


class SC2Controller(Controller):
	"""
	One Steam Controller 2, either wired, connected to one of dongle slots
	or connected over Bluetooth (see SC2BTDevice).
	"""
	flags = ( 0
		| ControllerFlags.SEPARATE_STICK
		| ControllerFlags.HAS_DPAD
		| ControllerFlags.HAS_RSTICK
		| ControllerFlags.HAS_TOUCHPADS
		| ControllerFlags.IS_SC2
	)

	def __init__(self, driver, iface, out_ep, serial):
		Controller.__init__(self)
		self._driver = driver
		self._iface = iface
		self._out_ep = out_ep
		self._serial = serial
		self._enable_gyros = False
		self._rumble = None
		self._last_rumble = 0
		self._last_lizard = 0
		self._led_level = None
		self._old_state = SC2_NULL
		self._battery_level = None
		self._id = "sc2-%s" % (serial,)


	def get_type(self):
		return "sc2"


	def get_gui_config_file(self):
		return "sc2.config.json"


	def _send_feature(self, data):
		""" Sends 64B feature report (report id 1) to the controller """
		self._driver._feature(self._iface, data)


	def _send_output(self, data):
		""" Sends haptic output report over interrupt endpoint """
		self._driver.rumble(self._out_ep, data)


	def __repr__(self):
		return "<SC2 %s>" % (self.get_id(),)


	def configure(self):
		""" Keeps lizard mode off on freshly connected controller """
		self._last_lizard = 0
		self._keep_lizard_off()


	def _keep_lizard_off(self):
		self._last_lizard = time.time()
		self._send_feature(self._lizard_off_payload())


	@staticmethod
	def _lizard_off_payload():
		""" USB-style payload that turns lizard mode off """
		return struct.pack('<BBBBH',
			FEATURE_REPORT_ID, FEATURE_SET_SETTINGS, 3,
			SETTING_LIZARD_MODE, 0)


	def _send_rumble(self):
		left, right, count = self._rumble
		data = struct.pack('<BBHHBHB',
			0x80,			# ID_OUT_REPORT_HAPTIC_RUMBLE
			0,				# unRumbleType
			0,				# unIntensity
			left,			# unLeftMotorSpeed
			0,				# nLeftGain
			right,			# unRightMotorSpeed
			0,				# nRightGain
		)
		self._last_rumble = time.time()
		self._send_output(data)


	def _stop_rumble(self):
		""" Sends a report that stops both motors """
		self._send_output(struct.pack('<BBHHBHB',
			0x80, 0, 0, 0, 0, 0, 0))


	def input(self, data):
		now = time.time()

		if now - self._last_lizard >= LIZARD_INTERVAL:
			self._keep_lizard_off()
		if self._rumble and now - self._last_rumble >= RUMBLE_INTERVAL:
			self._rumble[2] -= 1
			if self._rumble[2] > 0:
				self._send_rumble()
			else:
				self._stop_rumble()
				self._rumble = None

		if self.mapper is None:
			return

		# Parse TritonMTUFull_t / TritonMTUNoQuat_t payload
		buttons, trig_l, trig_r, stick_x, stick_y, rstick_x, rstick_y = \
			struct.unpack_from('<IHhhhhh', data, 2)
		lpad_x, lpad_y, lpad_p, rpad_x, rpad_y, rpad_p = \
			struct.unpack_from('<hhHhhH', data, 18)
		gpitch = groll = gyaw = 0
		q_w = q_x = q_y = q_z = 0
		if len(data) >= 46:
			# raw angular velocity, not quaternion
			gyro_x, gyro_y, gyro_z = struct.unpack_from('<hhh', data, 40)
			gpitch = int(-gyro_x * GYRO_SCALE)
			groll  = int(gyro_y * GYRO_SCALE)
			gyaw   = int(gyro_z * GYRO_SCALE)

		# Button translation
		sc_buttons = 0
		for tbit, scbit in _TRITON_TO_SC_BITS:
			if buttons & tbit:
				sc_buttons |= scbit

		# Trigger values are raw int16
		# converted to 0..255
		ltrig = clamp(max(0, trig_l), 0, 32767) >> 7
		rtrig = clamp(max(0, trig_r), 0, 32767) >> 7

		state = SC2Input(
			sc_buttons,
			ltrig, rtrig,
			stick_x,	stick_y,
			rstick_x,	rstick_y,
			lpad_x if buttons & (1 << 25) else 0,
			lpad_y if buttons & (1 << 25) else 0,
			rpad_x if buttons & (1 << 21) else 0,
			rpad_y if buttons & (1 << 21) else 0,
			map_dpad(buttons, 1 << 12, 1 << 11),	# dpad_x
			map_dpad(buttons, 1 << 10, 1 << 13),	# dpad_y
			gpitch, groll, gyaw,
			q_w, q_x, q_y, q_z,
		)

		old_state, self._old_state = self._old_state, state
		self.mapper.input(self, old_state, state)


	def on_battery(self, data):
		""" Called when 0x43 battery report is received """
		if len(data) >= 3:
			self._battery_level = data[2]


	def get_battery_level(self):
		return self._battery_level


	def set_gyro_enabled(self, enabled):
		log.info("Triton: set_gyro_enabled(%s)", enabled)
		if self._enable_gyros == enabled:
			return
		self._enable_gyros = enabled
		self._send_feature(struct.pack('<BBBBH',
			FEATURE_REPORT_ID, FEATURE_SET_SETTINGS, 3,
			SETTING_IMU_MODE, IMU_MODE_ENABLED if enabled else 0))


	def get_gyro_enabled(self):
		return self._enable_gyros


	def apply_config(self, config):
		self.set_led_level(float(config['led_level']))


	def set_led_level(self, level):
		level = min(100, max(0, int(level)))
		if self._led_level == level:
			return
		self._led_level = level
		self._send_feature(struct.pack('<BBBBH',
			FEATURE_REPORT_ID, FEATURE_SET_SETTINGS, 3,
			SETTING_LED_USER_BRIGHTNESS, level))


	def feedback(self, data):
		"""
		Haptic feedback. Two kinds of effects are supported, chosen by
		the haptic count (see WholeHapticAction / mapper._rumble_ready)
		Discrete click or longer rumble
		"""
		amplitude = min(data.get_amplitude(), 0xffff)
		position = data.get_position()
		count = max(1, data.get_count())
		if amplitude <= 0:
			self._rumble = None
			return
		if count == 1:
			if self._rumble is not None:
				self._rumble = None
				self._stop_rumble()
			self._click(data)
			return
		left = amplitude if position in (HapticPos.LEFT, HapticPos.BOTH) else 0
		right = amplitude if position in (HapticPos.RIGHT, HapticPos.BOTH) else 0
		if left == right == 0:
			self._rumble = None
			return
		self._rumble = [ left, right, count ]
		self._send_rumble()


	def _click(self, data):
		"""
		Plays a discrete haptic click using HAPTIC_COMMAND (0x82)
		"""
		position = data.get_position()
		if position == HapticPos.LEFT:
			side = 0
		elif position == HapticPos.RIGHT:
			side = 1
		else:
			side = 2
		amplitude = data.get_amplitude()
		command = 2 if amplitude >= 4096 else 1	# CLICK_STRONG / CLICK
		gain = round(20.0 * math.log10(max(1, amplitude) / 512.0))
		gain = max(-23, min(24, gain))
		self._send_output(
			struct.pack('<BBBb', 0x82, side, command, gain))


	def turnoff(self):
		log.debug("Turning off SC2 controller %s", self.get_id())
		self._send_feature(struct.pack('<BBB',
			FEATURE_REPORT_ID, FEATURE_TURN_OFF, 0))


class SC2BTDriver(object):
	"""
	SC2 driver part that handles controller connected over bluetooth (BLE).
	Uses hidraw transport instead of USB
	"""

	def __init__(self, daemon, config):
		self.daemon = daemon
		self.config = config
		self.reconnecting = set()
		self._active = {}
		daemon.get_device_monitor().add_callback("bluetooth",
				VENDOR_ID, PRODUCT_SC2_BLE,
				self.new_device_callback, None)


	def new_device_callback(self, syspath, *whatever):
		if syspath in self._active:
			# Dedupes udev add events and reconnect attempts racing each
			# other so returns already working controller instead
			self.reconnecting.discard(syspath)
			return self._active[syspath]
		hidrawname = self.daemon.get_device_monitor().get_hidraw(syspath)
		if hidrawname is None:
			return None
		try:
			fh = open(os.path.join("/dev/", hidrawname), "w+b")
		except Exception as e:
			if syspath in self.reconnecting:
				log.debug("SC2 reconnect attempt failed: %s", e)
			else:
				log.exception(e)
			return None
		try:
			# HIDRaw takes ownership of fh
			dev = HIDRaw(fh)
			c = SC2BTDevice(self, syspath, dev)
		except Exception as e:
			fh.close()
			if syspath in self.reconnecting:
				log.debug("SC2 reconnect attempt failed: %s", e)
			else:
				log.exception(e)
			return None
		self._active[syspath] = c
		self.reconnecting.discard(syspath)
		return c


	def _controller_closed(self, syspath, c):
		""" Called from SC2BTDevice.close() """
		if self._active.get(syspath) is c:
			del self._active[syspath]


	def retry(self, syspath):
		"""
		Starts periodically retrying reconnection after IO operation with
		controller failed until controller answers again or device monitor
		reports it being disconnected

		Helps with issues when connection drops
		"""
		if syspath in self.reconnecting:
			return
		self.reconnecting.add(syspath)
		self.daemon.get_device_monitor().add_remove_callback(
			syspath, self._retry_cancel)
		self._schedule_retry(syspath)


	def _schedule_retry(self, syspath):
		def reconnect(*a):
			if syspath not in self.reconnecting:
				return
			monitor = self.daemon.get_device_monitor()
			if getattr(monitor, "known_devs", None) is not None and \
					syspath not in monitor.known_devs:
				self.reconnecting.discard(syspath)
				return
			if self.new_device_callback(syspath) is None:
				self._schedule_retry(syspath)
		self.daemon.get_scheduler().schedule(BT_RETRY_INTERVAL, reconnect)


	def _retry_cancel(self, syspath, *a):
		self.reconnecting.discard(syspath)


class SC2BTDevice(SC2Controller):
	"""
	Steam Controller 2 connected over bluetooth (BLE)
	"""

	def __init__(self, driver, syspath, hidrawdev):
		SC2Controller.__init__(self, driver, -1, -1, None)
		self.daemon = driver.daemon
		self.syspath = syspath
		self._closed = False
		self._ready = False
		self._hidrawdev = hidrawdev
		self._fileno = hidrawdev._device.fileno()
		self._poller = driver.daemon.get_poller()
		self._probe_count = 0
		self._probing = False
		self._id = "sc2bt:%s" % (
			hidrawdev.getPhysicalAddress().decode("utf-8", "ignore")
					.replace(":", ""), )
		try:
			self.configure()
		except Exception:
			self._hidrawdev._device.close()
			raise
		self._ready = True
		if self._poller:
			self._poller.register(self._fileno, self._poller.POLLIN, self._input)
		driver.daemon.get_device_monitor().add_remove_callback(
			syspath, self.close)
		log.debug("SC2 over bluetooth added: %s", self.get_id())
		driver.daemon.add_controller(self)


	def get_type(self):
		return "sc2"


	def __repr__(self):
		return "<SC2BT %s>" % (self.get_id(), )


	def _io_error(self, op):
		if self._closed or self._probing:
			return
		log.debug("SC2 BT IO error on %s, probing connection", op)
		if self._poller:
			self._poller.unregister(self._fileno)
		self._probe_count = 0
		self._probing = True
		self._schedule_probe()


	def _schedule_probe(self):
		def probe(*a):
			if self._closed:
				return
			self._probe_count += 1
			if self._probe_count > BT_PROBE_RETRIES:
				self._probing = False
				self._disconnect()
				return
			try:
				self._hidrawdev.sendFeatureReport(
					(self._lizard_off_payload() + b'\x00' * 64)[:64][1:],
					FEATURE_REPORT_ID)
			except (OSError, IOError):
				self._schedule_probe()
			else:
				log.debug("SC2 BT connection recovered after IO error")
				self._probing = False
				if self._poller:
					self._poller.register(self._fileno,
						self._poller.POLLIN, self._input)
		self.daemon.get_scheduler().schedule(BT_PROBE_INTERVAL, probe)


	def _send_feature(self, data):
		"""
		Sends 64B feature report over hidraw, similar ot USB
		"""
		body = (data + b'\x00' * 64)[:64][1:]
		try:
			self._hidrawdev.sendFeatureReport(body, FEATURE_REPORT_ID)
		except (OSError, IOError):
			if not self._ready:
				raise
			self._io_error("feature report")


	def _send_output(self, data):
		"""
		Sends haptic output report over hidraw
		"""
		try:
			os.write(self._fileno, bytes(data))
		except (OSError, IOError):
			if not self._ready:
				raise
			self._io_error("output report")


	def _input(self, *a):
		try:
			data = os.read(self._fileno, 64)
		except (OSError, IOError):
			self._io_error("read")
			return
		if not data:
			return
		try:
			if data[0] in (REPORT_STATE, REPORT_STATE_BLE, REPORT_STATE_TIMESTAMP):
				self.input(data)
			elif data[0] == REPORT_BATTERY and len(data) >= 3:
				self._battery_level = data[2]
		except Exception as e:
			log.error("Failed to handle SC2 BT data")
			log.error(e)
			log.error(traceback.format_exc())


	def _disconnect(self):
		"""
		Treats failed IO as disconnection
		"""
		if self._closed:
			return
		log.debug("IO with SC2 controller failed, assuming disconnection")
		self.close()
		self._driver.retry(self.syspath)


	def close(self, *a):
		if self._closed:
			return
		self._closed = True
		if self._poller:
			self._poller.unregister(self._fileno)
		self._driver._controller_closed(self.syspath, self)
		self.daemon.remove_controller(self)
		self._hidrawdev._device.close()
