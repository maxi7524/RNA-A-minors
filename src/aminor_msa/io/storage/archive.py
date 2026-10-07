"""Selected source archive operations."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from aminor_msa.utils.logging import get_custom_logger

from ..parsers.dssr import DssrReport, parse_dssr

logger = get_custom_logger(__name__)


def read_report(path: Path, member: str) -> DssrReport:
    """Read one member and close both stream and archive before returning.

    :param path: Supplied ZIP archive.
    :type path: pathlib.Path
    :param member: Exact member name selected from its central directory.
    :type member: str
    :return: One parsed report, including original text.
    :rtype: DssrReport
    :raises KeyError: If the member is absent.
    :raises ValueError: If supported report tables are malformed.
    """
    with (
        zipfile.ZipFile(path) as archive,
        archive.open(member) as binary,
        io.TextIOWrapper(binary, encoding="utf-8") as handle,
    ):
        return parse_dssr(handle, source=f"{path}!{member}")
