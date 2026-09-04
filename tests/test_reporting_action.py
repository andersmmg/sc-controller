import io

from scc.constants import STICK, CPAD
from scc.sccdaemon import ReportingAction


class FakeController(object):
	def get_id(self):
		return "testctl"


class FakeMapper(object):
	def __init__(self):
		self._c = FakeController()

	def get_controller(self):
		return self._c


class FakeClient(object):
	def __init__(self):
		self.mapper = FakeMapper()
		self.wfile = io.BytesIO()


def _make_action():
	client = FakeClient()
	action = ReportingAction(STICK, client)
	return action, client


def _events(client):
	return [l for l in client.wfile.getvalue().decode().splitlines() if l.startswith("Event:")]


def test_negative_y_movement_reported():
	action, client = _make_action()
	action.whole(client.mapper, 0, 0, STICK)
	action.whole(client.mapper, 0, -5000, STICK)
	assert len(_events(client)) == 2


def test_slow_circle_reports():
	import math
	action, client = _make_action()
	steps = 72
	radius = 8000
	for i in range(steps + 1):
		a = 2 * math.pi * i / steps
		action.whole(client.mapper, int(radius * math.cos(a)), int(radius * math.sin(a)), STICK)
	assert len(_events(client)) >= steps * 0.9


def test_small_jitter_suppressed():
	action, client = _make_action()
	action.whole(client.mapper, 0, 0, STICK)
	action.whole(client.mapper, 10, 10, STICK)
	action.whole(client.mapper, 20, 5, STICK)
	assert len(_events(client)) == 1


def test_release_reported():
	action, client = _make_action()
	action.whole(client.mapper, 0, 0, STICK)
	action.whole(client.mapper, 200, 200, STICK)
	action.whole(client.mapper, 0, 0, STICK)
	assert len(_events(client)) == 2


def test_cpad_lower_threshold():
	action, client = _make_action()
	a2, client2 = _make_action()
	a2.what = CPAD
	action.whole(client.mapper, 0, 0, STICK)
	a2.whole(client2.mapper, 0, 0, CPAD)
	a2.whole(client2.mapper, 20, 20, CPAD)
	a2.whole(client2.mapper, 25, 25, CPAD)
	assert len(_events(client)) == 1
	assert len(_events(client2)) == 2


def test_multiple_suppressed_events_stay_suppressed():
	action, client = _make_action()
	action.whole(client.mapper, 0, 0, STICK)
	action.whole(client.mapper, 100, 0, STICK)
	action.whole(client.mapper, 200, 0, STICK)
	assert len(_events(client)) == 1
