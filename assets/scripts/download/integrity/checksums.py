"""Integrity checksums."""

from __future__ import annotations

import json
from pathlib import Path

from aminor_msa.utils.files import sha256_file
from aminor_msa.utils.logging import get_custom_logger
from assets.scripts.download.core.records import record_path

from ..manifests.planning import build_plan
from ..sources.supplied import SUPPLIED

logger = get_custom_logger(__name__)


def export_checksums(data_root: Path) -> int:
    """Export the complete configured input set, rejecting missing provenance.

    :param data_root: Dataset directory containing configuration and records.
    :type data_root: pathlib.Path
    :return: Number of checksum entries.
    :rtype: int
    :raises ValueError: If an expected input lacks complete acquisition evidence.
    """
    manifest = data_root / "config/families.csv"
    plan = build_plan(manifest, data_root / "rfam/raw/Rfam.pdb")
    plan.extend(artifact for _, artifact in SUPPLIED)
    lines = [f"{sha256_file(manifest)}  config/families.csv\n"]
    for artifact in sorted(plan, key=lambda item: item.relative_path):
        path = record_path(data_root, artifact)
        if not path.is_file():
            raise ValueError(f"Missing provenance for {artifact.key}")
        record = json.loads(path.read_text(encoding="utf-8"))
        destination = data_root / artifact.relative_path
        if (
            record.get("status") != "complete"
            or record.get("url") != artifact.url
            or not destination.is_file()
            or record.get("bytes") != destination.stat().st_size
        ):
            raise ValueError(f"Incomplete acquisition for {artifact.key}")
        lines.append(f"{record['sha256']}  {artifact.relative_path}\n")
    output = data_root / "downloads/checksums.sha256"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(lines), encoding="utf-8")
    logger.info("Exported %s checksum entries to %s", len(lines), output)
    return len(lines)
