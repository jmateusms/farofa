"""Background jobs: long simulations run in a worker thread.

The page starts a job, polls its progress and may cancel it. Cancelling sets
a flag that the job's progress callback checks after every replication; the
callback then raises :class:`Cancelled`, which unwinds ``simulate``.
"""
from __future__ import annotations

import threading
import time
import traceback
import uuid
from collections import OrderedDict
from typing import Any, Callable, Dict, Optional

from .api import EstimateInputError, ScenarioError


class Cancelled(Exception):
    """Raised inside a job when the user cancelled it."""


class Job:
    def __init__(self, kind: str):
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind
        self.status = 'running'
        self.done = 0
        self.total = 0
        self.result: Any = None
        self.export: Any = None
        self.error: Optional[Dict[str, Any]] = None
        self.started = time.time()
        self.finished: Optional[float] = None
        self._cancel = threading.Event()

    def progress(self, done: int, total: int) -> None:
        """Progress callback handed to ``simulate``; raises once cancelled."""
        self.done, self.total = done, total
        if self._cancel.is_set():
            raise Cancelled()

    def cancel(self) -> None:
        self._cancel.set()

    def status_dict(self, with_result: bool = True) -> Dict[str, Any]:
        out = {
            'id': self.id,
            'kind': self.kind,
            'status': self.status,
            'done': self.done,
            'total': self.total,
            'elapsed': (self.finished or time.time()) - self.started,
        }
        if self.error is not None:
            out['error'] = self.error
        if with_result and self.status == 'done':
            out['result'] = self.result
        return out


class JobManager:
    """Keeps the most recent jobs; older finished jobs are dropped."""

    def __init__(self, keep: int = 6):
        self._jobs: "OrderedDict[str, Job]" = OrderedDict()
        self._lock = threading.Lock()
        self._keep = keep

    def start(self, kind: str, work: Callable[[Job], Any]) -> Job:
        """Run ``work(job)`` in a daemon thread. ``work`` returns the result,
        or ``(result, export)`` to keep an export payload alongside it."""
        job = Job(kind)
        with self._lock:
            self._jobs[job.id] = job
            self._prune()

        def target() -> None:
            try:
                out = work(job)
                if isinstance(out, tuple):
                    job.result, job.export = out
                else:
                    job.result = out
                job.status = 'done'
            except Cancelled:
                job.status = 'cancelled'
            except ScenarioError as exc:
                job.status = 'error'
                job.error = {'message': str(exc), 'errors': exc.errors}
            except EstimateInputError as exc:
                job.status = 'error'
                job.error = {'message': str(exc), 'code': exc.code}
            except Exception as exc:  # engine errors surface as messages
                traceback.print_exc()
                job.status = 'error'
                job.error = {'message': f'{type(exc).__name__}: {exc}'}
            finally:
                job.finished = time.time()

        threading.Thread(target=target, name=f'farofa-job-{job.id}', daemon=True).start()
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel_all(self) -> None:
        with self._lock:
            for job in self._jobs.values():
                job.cancel()

    def _prune(self) -> None:
        finished = [j for j in self._jobs.values() if j.status != 'running']
        while len(self._jobs) > self._keep and finished:
            self._jobs.pop(finished.pop(0).id, None)
