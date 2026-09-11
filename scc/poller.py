#!/usr/bin/env python3
"""
SC-Controller - Poller

Uses select to pool for file descriptors. Driver classes can use
daemon.get_poller().register and .unregister to add file descriptors and
register callbacks to be called when data is available in them.

Callback is called as callback(fd, event) where event is one of select.POLL*
"""

import logging
import select
from collections.abc import Callable
from typing import Any

log = logging.getLogger("Poller")


def DO_NOTHING(*a: Any) -> bool:
	return False


class Poller:
	POLLIN = select.POLLIN
	POLLOUT = select.POLLOUT
	POLLPRI = select.POLLPRI

	def __init__(self) -> None:
		self._events: dict[int, int] = {}
		self._callbacks: dict[int, Callable[[int, int], Any]] = {}
		self._pool_in: list[int] = []
		self._pool_out: list[int] = []
		self._pool_pri: list[int] = []

	def register(self, fd: int, events: int, callback: Callable[[int, int], Any]) -> None:
		if fd < 0:
			raise ValueError("Invalid file descriptor")
		self._events[fd] = events
		self._callbacks[fd] = callback
		self._generate_lists()

	def unregister(self, fd: int) -> None:
		if fd in self._events:
			del self._events[fd]
		if fd in self._callbacks:
			del self._callbacks[fd]
		self._generate_lists()

	def _generate_lists(self) -> None:
		self._pool_in = [fd for fd, events in self._events.items() if events & Poller.POLLIN]
		self._pool_out = [fd for fd, events in self._events.items() if events & Poller.POLLOUT]
		self._pool_pri = [fd for fd, events in self._events.items() if events & Poller.POLLPRI]

	def poll(self, timeout: float = 0.01) -> None:
		inn: list[int]
		out: list[int]
		pri: list[int]
		inn, out, pri = select.select(self._pool_in, self._pool_out, self._pool_pri, timeout)

		for fd in inn:
			callback: Callable[[int, int], Any] = self._callbacks.get(fd, DO_NOTHING)
			callback(fd, Poller.POLLIN)
		for fd in out:
			callback = self._callbacks.get(fd, DO_NOTHING)
			callback(fd, Poller.POLLOUT)
		for fd in pri:
			callback = self._callbacks.get(fd, DO_NOTHING)
			callback(fd, Poller.POLLPRI)
