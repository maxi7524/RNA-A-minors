"""Sources supplied."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from aminor_msa.utils.files import sha256_file, write_json
from aminor_msa.utils.logging import get_custom_logger
from assets.scripts.download.core.models import Artifact
from assets.scripts.download.core.records import record_path
from assets.scripts.download.core.validation import validate_artifact

logger = get_custom_logger(__name__)


SUPPLIED = [
    (
        "rfam-family-student.tsv",
        Artifact(
            "supplied_assignments",
            "supplied_table",
            "assignments",
            "https://drive.google.com/file/d/1ZhCRWFckRPst--E7Lul3MupgxLOpWuyZ/view",
            "config/rfam-family-student.tsv",
        ),
    ),
    (
        "Rfam.pdb",
        Artifact(
            "supplied_rfam_pdb",
            "supplied_table",
            "rfam_pdb",
            "https://drive.google.com/file/d/1NyTtZhizrozU9K6jEFwFu6ZuujoVLGd3/view",
            "rfam/raw/Rfam.pdb",
        ),
    ),
    (
        "dssr_out_261003.zip",
        Artifact(
            "supplied_dssr_zip",
            "dssr_zip",
            "dssr_out_261003",
            "https://drive.google.com/file/d/1749UkWDHi_kVs1KBe6oqGl2TVycXV5eu/view",
            "dssr/raw/dssr_out_261003.zip",
        ),
    ),
]


def import_source(source: Path, data_root: Path, artifact: Artifact) -> dict:
    """Copy supplied bytes and record their original source reference.

    :param source: Local input file.
    :type source: Path
    :param data_root: Output dataset directory.
    :type data_root: Path
    :param artifact: Destination and original source reference.
    :type artifact: Artifact
    :return: Complete provenance record.
    :rtype: dict
    :raises ValueError: If existing destination bytes differ from the source.
    """
    destination = data_root / artifact.relative_path
    logger.info("Importing supplied input: %s", source.name)
    source_hash = sha256_file(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256_file(destination) != source_hash:
            raise ValueError(
                f"Existing destination differs from supplied source: {destination}"
            )
    else:
        fd, temporary = tempfile.mkstemp(dir=destination.parent, suffix=".part")
        try:
            with source.open("rb") as reader, os.fdopen(fd, "wb") as writer:
                shutil.copyfileobj(reader, writer, length=1024 * 1024)
            if sha256_file(Path(temporary)) != source_hash:
                raise ValueError("Copied source checksum mismatch")
            validate_artifact(Path(temporary), artifact)
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
    record = {
        **asdict(artifact),
        "status": "complete",
        "sha256": source_hash,
        "bytes": destination.stat().st_size,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "local_source_name": source.name,
        "validation": validate_artifact(destination, artifact),
    }
    write_json(record_path(data_root, artifact), record)
    return record
