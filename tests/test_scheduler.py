"""
Tests for scc.scheduler, mostly for ordering of tasks with identical
scheduled times, which used to crash Mr. PriorityQueue
"""
import scc.scheduler as scheduler_mod
from scc.scheduler import Scheduler


def _clock(monkeypatch, start=0.0):
	""" Returns callable that advances patched time.time """
	now = [ float(start) ]
	monkeypatch.setattr(scheduler_mod.time, "time", lambda: now[0])
	return now


def test_equal_time_tasks_do_not_crash(monkeypatch):
	""" Three tasks with identical timestamp must schedule and run fine """
	now = _clock(monkeypatch)
	s = Scheduler()
	out = []
	s.schedule(1.0, lambda: out.append(1))
	s.schedule(1.0, lambda: out.append(2))
	s.schedule(1.0, lambda: out.append(3))	# used to raise TypeError

	now[0] = 2.0
	s.run()

	assert out == [ 1, 2, 3 ]


def test_equal_time_tasks_run_in_fifo_order(monkeypatch):
	""" Tasks with same time execute in scheduling order """
	now = _clock(monkeypatch)
	s = Scheduler()
	out = []
	for i in range(10):
		s.schedule(1.0, lambda i=i: out.append(i))

	now[0] = 2.0
	s.run()

	assert out == list(range(10))


def test_tasks_run_after_delay_in_time_order(monkeypatch):
	""" Tasks with different times run sorted by time, no sooner than delay """
	now = _clock(monkeypatch)
	s = Scheduler()
	out = []
	s.schedule(5.0, lambda: out.append("late"))
	s.schedule(1.0, lambda: out.append("early"))
	s.schedule(1.0, lambda: out.append("early2"))

	now[0] = 0.5
	s.run()
	assert out == []

	now[0] = 2.0
	s.run()
	assert out == [ "early", "early2" ]

	now[0] = 6.0
	s.run()
	assert out == [ "early", "early2", "late" ]


def test_cancel_task(monkeypatch):
	""" Canceled task is not executed """
	now = _clock(monkeypatch)
	s = Scheduler()
	out = []
	t1 = s.schedule(1.0, lambda: out.append(1))
	t2 = s.schedule(1.0, lambda: out.append(2))
	assert s.cancel_task(t1)

	now[0] = 2.0
	s.run()
	assert out == [ 2 ]
	assert not s.cancel_task(t1)


def test_task_cancel_method(monkeypatch):
	""" Task.cancel() marks task as no-op """
	now = _clock(monkeypatch)
	s = Scheduler()
	out = []
	t = s.schedule(1.0, lambda: out.append(1))
	t.cancel()

	now[0] = 2.0
	s.run()
	assert out == []
