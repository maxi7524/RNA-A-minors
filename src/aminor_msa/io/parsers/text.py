"""Streaming plain-text and gzip input."""

import gzip
from pathlib import Path
from typing import TextIO


def open_text(path: str | Path) -> TextIO:
    """Open a UTF-8 source; the caller must close the returned handle.

    :param path: Plain-text or gzip filename.
    :type path: str | pathlib.Path
    :return: Text stream, decompressing incrementally when needed.
    :rtype: typing.TextIO
    """
    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open(encoding="utf-8")
