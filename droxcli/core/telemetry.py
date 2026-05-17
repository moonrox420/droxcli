"""Performance tracing and atomic operation context managers."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional

from droxcli.core.logger import logger


@contextmanager
def trace_performance(operation: str) -> Iterator[None]:
    """Measures execution time and logs it."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.debug(
            "perf",
            op=operation,
            ms=round(elapsed * 1000, 2),
        )


@contextmanager
def atomic_operation(
    description: str,
    rollback: Optional[Callable[[], Any]] = None,
) -> Iterator[None]:
    """
    Atomic context with optional rollback on failure.

    Usage:
        with atomic_operation("apply patches", rollback=lambda: restore_snapshot(snap_id, root)):
            apply_patches(patches, root)
    """
    logger.info("atomic_start", desc=description)
    try:
        yield
        logger.info("atomic_ok", desc=description)
    except Exception as exc:
        logger.error("atomic_fail", desc=description, error=str(exc))
        if rollback:
            logger.warning("rollback_start", desc=description)
            try:
                rollback()
                logger.info("rollback_ok", desc=description)
            except Exception as rb_exc:
                logger.error("rollback_fail", desc=description, error=str(rb_exc))
        raise
