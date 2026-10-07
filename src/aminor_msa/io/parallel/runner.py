"""Bounded ordered concurrent loading."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from typing import Any

from aminor_msa.utils.logging import get_custom_logger

from ..store import DataStore

logger = get_custom_logger(__name__)
import multiprocessing
from collections import deque
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

from .requests import LoadedSource, SourceRequest
from .workers import _initialize_worker, _run_task


def iter_loaded(
    store: DataStore,
    requests: Iterable[SourceRequest],
    *,
    workers: int = 2,
    prefetch: int = 2,
    backend: str = "thread",
    transform: Callable[[DataStore, SourceRequest], Any] | None = None,
) -> Iterator[LoadedSource]:
    """Load or prepare sources concurrently with bounded submissions.

    Results follow request order. At most prefetch tasks are submitted ahead of
    consumption; memory additionally includes worker-local parsing and results
    retained by the caller. No source cache is enabled inside workers. Closing
    the generator cancels queued tasks and waits for already running tasks.
    Each worker lazily opens and reuses one ZIP for DSSR reads; the reader is
    closed at iterator shutdown or reclaimed when its worker process exits.

    Thread workers are convenient in notebooks and for I/O. Process workers use
    spawn; transforms must be importable module-level callables, and scripts need
    the usual main guard. For large objects, prepare features/write an output
    shard inside the transform and return its path to avoid expensive IPC copies.

    :param store: Source paths/configuration used to construct worker-local stores.
    :type store: DataStore
    :param requests: Finite or streaming artifact requests.
    :type requests: collections.abc.Iterable[SourceRequest]
    :param workers: Positive worker count.
    :type workers: int
    :param prefetch: Positive maximum submitted tasks; values below workers reduce parallelism.
    :type prefetch: int
    :param backend: thread or process.
    :type backend: str
    :param transform: Optional worker function owning source reading and preparation.
    :type transform: collections.abc.Callable | None
    :return: Keyed results, yielded incrementally in input order.
    :rtype: collections.abc.Iterator[LoadedSource]
    :raises ValueError: On invalid worker/prefetch counts or backend.
    """
    if workers < 1 or prefetch < 1:
        raise ValueError("workers and prefetch must be positive")
    if backend not in {"thread", "process"}:
        raise ValueError("backend must be thread or process")
    logger.info(
        "Loading sources with %s workers, backend=%s, prefetch=%s",
        workers,
        backend,
        prefetch,
    )
    readers = [] if backend == "thread" else None
    options = {
        "max_workers": workers,
        "initializer": _initialize_worker,
        "initargs": (str(store.root), str(store.archive), readers),
    }
    if backend == "process":
        executor = ProcessPoolExecutor(
            **options, mp_context=multiprocessing.get_context("spawn")
        )
    else:
        executor = ThreadPoolExecutor(**options)
    pending = deque()
    source = iter(requests)
    try:
        # Fill a bounded window; never eagerly submit the entire dataset.
        for _ in range(prefetch):
            request = next(source, None)
            if request is None:
                break
            pending.append(executor.submit(_run_task, request, transform))
        while pending:
            yield pending.popleft().result()
            request = next(source, None)
            if request is not None:
                pending.append(executor.submit(_run_task, request, transform))
    finally:
        for future in pending:
            future.cancel()
        try:
            executor.shutdown(wait=True, cancel_futures=True)
        finally:
            if readers is not None:
                for reader in readers:
                    reader.close()
