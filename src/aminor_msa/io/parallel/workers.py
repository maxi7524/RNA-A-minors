"""Worker-owned stores and reusable ZIP readers."""

from __future__ import annotations

from collections.abc import Callable

from aminor_msa.utils.logging import get_custom_logger

from ..store import DataStore

logger = get_custom_logger(__name__)
import atexit
import io
import threading
import zipfile

from ..parsers.dssr import DssrReport, parse_dssr
from .requests import LoadedSource, SourceRequest, read_request

_WORKER = threading.local()


class _WorkerReportReader:
    """Own a lazily opened ZIP for the lifetime of one executor worker."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.archive: zipfile.ZipFile | None = None

    def __call__(self, member: str) -> DssrReport:
        if self.archive is None:
            logger.debug("Opening worker-local DSSR ZIP: %s", self.path)
            self.archive = zipfile.ZipFile(self.path)
        with (
            self.archive.open(member) as binary,
            io.TextIOWrapper(binary, encoding="utf-8") as handle,
        ):
            return parse_dssr(handle, source=f"{self.path}!{member}")

    def close(self) -> None:
        if self.archive is not None:
            self.archive.close()
            self.archive = None


def _initialize_worker(root: str, archive: str, readers: list | None) -> None:
    store = DataStore(root, dssr_archive=archive)
    reader = _WorkerReportReader(archive)
    store._dssr_reader = reader
    _WORKER.store = store
    if readers is None:
        # Process termination also reclaims read-only handles if a task fails.
        atexit.register(reader.close)
    else:
        readers.append(reader)


def _run_task(request: SourceRequest, transform: Callable | None) -> LoadedSource:
    store = _WORKER.store
    data = (
        read_request(store, request) if transform is None else transform(store, request)
    )
    return LoadedSource(request, data)
