"""Artifact ledger paths and offline verification."""

from __future__ import annotations

from pathlib import Path

from aminor_msa.utils.logging import get_custom_logger

logger = get_custom_logger(__name__)
import json
import zipfile
from dataclasses import asdict

from aminor_msa.utils.files import sha256_file

from .models import Artifact
from .validation import validate_artifact


def record_path(data_root: Path, artifact: Artifact) -> Path:
    """Return the provenance path for a request.

    :param data_root: Dataset directory.
    :type data_root: Path
    :param artifact: Acquisition request.
    :type artifact: Artifact
    :return: Record path.
    :rtype: pathlib.Path
    """
    return data_root / "downloads" / "records" / (artifact.key + ".json")


def verify_artifact(data_root: Path, artifact: Artifact) -> dict:
    """Verify a request against recorded bytes without network access.

    :param data_root: Dataset directory.
    :type data_root: Path
    :param artifact: Expected request.
    :type artifact: Artifact
    :return: Verification result with an explicit status.
    :rtype: dict
    """
    destination = data_root / artifact.relative_path
    result = {**asdict(artifact), "status": "missing"}
    if not destination.is_file():
        return result
    provenance = record_path(data_root, artifact)
    if not provenance.is_file():
        return {**result, "status": "unrecorded"}
    try:
        record = json.loads(provenance.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("Unexpected provenance schema")
        if (
            record.get("status") != "complete"
            or record.get("url") != artifact.url
            or record.get("relative_path") != artifact.relative_path
            or record.get("bytes") != destination.stat().st_size
            or record.get("sha256") != sha256_file(destination)
        ):
            return {**result, "status": "damaged"}
        diagnostics = validate_artifact(destination, artifact)
        return {**record, "status": "verified", "validation": diagnostics}
    except (
        OSError,
        ValueError,
        EOFError,
        zipfile.BadZipFile,
    ) as error:
        return {**result, "status": "damaged", "error": str(error)}
