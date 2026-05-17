"""Thread-safe pipeline executor with performance telemetry."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, List, TypeVar

from droxcli.core.logger import logger
from droxcli.core.telemetry import trace_performance

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class Task(Generic[T, R]):
    """A named unit of work."""

    name: str
    func: Callable[..., R]
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)

    def run(self) -> R:
        return self.func(*self.args, **self.kwargs)


class PipelineExecutor:
    """Parallel task executor with observability."""

    def __init__(self, max_workers: int = 5, timeout: float = 120.0) -> None:
        self._max_workers = max_workers
        self._timeout = timeout
        self._lock = threading.Lock()

    def execute_batch(
        self, tasks: List[Task]
    ) -> List[tuple[str, Any, Exception | None]]:
        """
        Execute all tasks in parallel.
        Returns list of (name, result, error) — error is None on success.
        """
        output: List[tuple[str, Any, Exception | None]] = []

        with trace_performance("batch_exec"):
            with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                futures = {pool.submit(self._run, task): task for task in tasks}
                for future in as_completed(futures):
                    task = futures[future]
                    try:
                        result = future.result(timeout=self._timeout)
                        output.append((task.name, result, None))
                    except Exception as exc:
                        logger.error("task_failed", task=task.name, error=str(exc))
                        output.append((task.name, None, exc))

        return output

    def _run(self, task: Task) -> Any:
        with trace_performance(f"task:{task.name}"):
            logger.debug("task_start", task=task.name)
            result = task.run()
            logger.debug("task_done", task=task.name)
            return result
