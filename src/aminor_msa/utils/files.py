"""Bounded hashing and atomic record writes."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

CHUNK_SIZE = 1024 * 1024


def sha256_file(path: Path) -> str:
    """Hash a file without loading it into memory.

    :param path: Input file path.
    :type path: Path
    :return: SHA-256 hexadecimal digest.
    :rtype: str
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    """Atomically write a JSON record.

    :param path: Destination; parent directories are created.
    :type path: Path
    :param value: JSON serializable value.
    :type value: object
    :return: None.
    :rtype: None
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
