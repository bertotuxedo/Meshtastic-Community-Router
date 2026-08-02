from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field


LOGGER = logging.getLogger("mcr.scheduler")

JobFunction = Callable[[], None]


@dataclass(slots=True)
class ScheduledJob:
    name: str
    interval_seconds: float
    function: JobFunction
    run_immediately: bool = False
    next_run: float = field(default=0.0)
    running: bool = False
    executions: int = 0
    failures: int = 0
    last_started: float | None = None
    last_finished: float | None = None
    last_error: str | None = None


class Scheduler:
    """
    Lightweight interval scheduler for core and plugin jobs.

    Jobs run in individual daemon threads so a slow plugin job does
    not block MQTT processing or other scheduled jobs.
    """

    def __init__(
        self,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError(
                "poll_interval_seconds must be greater than zero"
            )

        self.poll_interval_seconds = (
            poll_interval_seconds
        )

        self.jobs: dict[str, ScheduledJob] = {}
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def register_interval(
        self,
        name: str,
        interval_seconds: float,
        function: JobFunction,
        run_immediately: bool = False,
    ) -> None:
        normalized_name = name.strip()

        if not normalized_name:
            raise ValueError(
                "Scheduled job name cannot be empty"
            )

        if interval_seconds <= 0:
            raise ValueError(
                "Scheduled job interval must be greater than zero"
            )

        now = time.monotonic()

        job = ScheduledJob(
            name=normalized_name,
            interval_seconds=float(
                interval_seconds
            ),
            function=function,
            run_immediately=run_immediately,
            next_run=(
                now
                if run_immediately
                else now + interval_seconds
            ),
        )

        with self.lock:
            if normalized_name in self.jobs:
                raise ValueError(
                    "Scheduled job already registered: "
                    f"{normalized_name}"
                )

            self.jobs[normalized_name] = job

        LOGGER.info(
            "Registered scheduled job name=%s "
            "interval=%ss immediate=%s",
            normalized_name,
            interval_seconds,
            run_immediately,
        )

    def unregister(
        self,
        name: str,
    ) -> bool:
        with self.lock:
            job = self.jobs.pop(
                name,
                None,
            )

        if job is None:
            return False

        LOGGER.info(
            "Unregistered scheduled job name=%s",
            name,
        )

        return True

    def start(self) -> None:
        with self.lock:
            if (
                self.thread is not None
                and self.thread.is_alive()
            ):
                return

            self.stop_event.clear()

            self.thread = threading.Thread(
                target=self._run_loop,
                name="mcr-scheduler",
                daemon=True,
            )

            self.thread.start()

        LOGGER.info("Scheduler started")

    def stop(
        self,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.stop_event.set()

        thread = self.thread

        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(
                timeout=timeout_seconds
            )

        LOGGER.info("Scheduler stopped")

    def _run_loop(self) -> None:
        while not self.stop_event.wait(
            self.poll_interval_seconds
        ):
            now = time.monotonic()

            with self.lock:
                due_jobs = [
                    job
                    for job in self.jobs.values()
                    if (
                        not job.running
                        and now >= job.next_run
                    )
                ]

                for job in due_jobs:
                    job.running = True
                    job.next_run = (
                        now + job.interval_seconds
                    )

            for job in due_jobs:
                worker = threading.Thread(
                    target=self._execute_job,
                    args=(job,),
                    name=(
                        "mcr-job-"
                        f"{job.name.replace('.', '-')}"
                    ),
                    daemon=True,
                )
                worker.start()

    def _execute_job(
        self,
        job: ScheduledJob,
    ) -> None:
        started = time.time()

        with self.lock:
            job.last_started = started
            job.last_error = None

        LOGGER.debug(
            "Starting scheduled job name=%s",
            job.name,
        )

        try:
            job.function()
        except Exception as exc:
            LOGGER.exception(
                "Scheduled job failed name=%s",
                job.name,
            )

            with self.lock:
                job.failures += 1
                job.last_error = (
                    f"{type(exc).__name__}: {exc}"
                )
        else:
            with self.lock:
                job.executions += 1
        finally:
            with self.lock:
                job.running = False
                job.last_finished = time.time()

    def health(
        self,
    ) -> dict[str, object]:
        with self.lock:
            jobs = {
                name: {
                    "interval_seconds": (
                        job.interval_seconds
                    ),
                    "running": job.running,
                    "executions": job.executions,
                    "failures": job.failures,
                    "last_started": job.last_started,
                    "last_finished": job.last_finished,
                    "last_error": job.last_error,
                }
                for name, job in self.jobs.items()
            }

            running = (
                self.thread is not None
                and self.thread.is_alive()
            )

        return {
            "running": running,
            "job_count": len(jobs),
            "jobs": jobs,
        }
