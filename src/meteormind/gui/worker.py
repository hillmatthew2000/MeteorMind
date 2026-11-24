"""Run slow work (network requests, file writes) off the Tk event loop.

Tk is not thread-safe, so results are handed back through a queue and
delivered by a callback scheduled on the Tk thread. Jobs run one at a time,
in order, on a single background thread, so the service never sees two
requests at once.
"""

from __future__ import annotations

import logging
import queue
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

Scheduler = Callable[[int, Callable[[], None]], object]

_Delivery = tuple["Future[Any]", Callable[[Any], None], Callable[[BaseException], None]]


class BackgroundWorker:
    """Runs callables in the background and reports back on the UI thread.

    ``schedule(delay_ms, callback)`` must run ``callback`` on the UI thread
    later; for Tk that is ``widget.after``.
    """

    POLL_MS = 30

    def __init__(self, schedule: Scheduler) -> None:
        self._schedule = schedule
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="meteormind")
        self._done: queue.Queue[_Delivery] = queue.Queue()
        self._pending = 0
        self._polling = False
        self._closed = False

    @property
    def busy(self) -> bool:
        return self._pending > 0

    def submit(
        self,
        job: Callable[[], T],
        on_success: Callable[[T], None],
        on_error: Callable[[BaseException], None],
    ) -> None:
        if self._closed:
            return
        self._pending += 1
        future = self._executor.submit(job)
        future.add_done_callback(lambda f: self._done.put((f, on_success, on_error)))
        if not self._polling:
            self._polling = True
            self._schedule(self.POLL_MS, self.poll)

    def poll(self) -> None:
        """Deliver finished jobs; reschedules itself while work is pending."""
        self._polling = False
        if self._closed:
            return
        while True:
            try:
                future, on_success, on_error = self._done.get_nowait()
            except queue.Empty:
                break
            self._pending -= 1
            error = future.exception()
            try:
                if error is None:
                    on_success(future.result())
                else:
                    on_error(error)
            except Exception:  # a broken callback must not stop other deliveries
                logger.exception("Error in a background job callback")
        if self._pending > 0:
            self._polling = True
            self._schedule(self.POLL_MS, self.poll)

    def close(self) -> None:
        """Stop delivering results and abandon queued jobs."""
        self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
