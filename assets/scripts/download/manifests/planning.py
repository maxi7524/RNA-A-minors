"""Manifests planning."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from aminor_msa.utils.logging import get_custom_logger
from assets.scripts.download.core.models import Artifact

logger = get_custom_logger(__name__)


def build_plan(
    manifest: Path,
    mapping: Path,
    participants: list[str] | None = None,
    families: list[str] | None = None,
) -> list[Artifact]:
    """Enumerate unique artifact requests from acquisition configuration.

    :param manifest: CSV or TSV with rfam_acc and optional per-artifact flags.
    :type manifest: Path
    :param mapping: Supplied tab-delimited Rfam-to-PDB catalogue.
    :type mapping: Path
    :param participants: Optional participant identifiers; requires participant_id.
    :type participants: list[str] | None
    :param families: Optional Rfam accessions; intersects participant selection.
    :type families: list[str] | None
    :return: Deterministically ordered, unique acquisition requests.
    :rtype: list[Artifact]
    :raises ValueError: If configuration or selection is invalid.
    """
    delimiter = "\t" if manifest.suffix.lower() == ".tsv" else ","
    with manifest.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle, delimiter=delimiter))
    available = {r.get("participant_id") for r in rows}
    if participants and set(participants) - available:
        raise ValueError(
            f"Unknown participant selection: {sorted(set(participants) - available)}"
        )
    available_families = {r.get("rfam_acc") for r in rows}
    if families and set(families) - available_families:
        raise ValueError("Unknown family selection")
    selected: dict[str, dict] = {}
    for row in rows:
        accession = row.get("rfam_acc", "")
        if not re.fullmatch(r"RF\d{5}", accession):
            raise ValueError(f"Invalid Rfam accession: {accession}")
        if participants and row.get("participant_id") not in participants:
            continue
        if families and accession not in families:
            continue
        if accession in selected and selected[accession] != row:
            raise ValueError(f"Conflicting duplicate family rows: {accession}")
        selected[accession] = row
    if not selected:
        raise ValueError("Acquisition selection is empty")

    # Family artifacts are selected independently by their own flags.
    plan = []
    enabled_pdb_families = set()
    sources = [
        (
            "seed",
            "download_seed_alignment",
            "seed.sto.gz",
            "/alignment/stockholm?gzip=1",
        ),
        ("cm", "download_covariance_model", "model.cm", "/cm"),
        (
            "metadata",
            "download_family_metadata",
            "family.json",
            "?content-type=application/json",
        ),
    ]
    for accession, row in sorted(selected.items()):
        for kind, flag, filename, suffix in sources:
            if _enabled(row, flag):
                plan.append(
                    Artifact(
                        f"{accession}_{kind}",
                        kind,
                        accession,
                        "https://rfam.org/family/" + accession + suffix,
                        f"rfam/raw/{accession}/{filename}",
                    )
                )
        if _enabled(row, "download_pdb_structures"):
            enabled_pdb_families.add(accession)

    # Catalogue lookup enumerates downloads; no residue-level mapping is performed.
    pdb_ids = set()
    with mapping.open(newline="", encoding="utf-8") as handle:
        for line, row in enumerate(csv.reader(handle, delimiter="\t"), 1):
            if not row:
                continue
            if len(row) < 9:
                raise ValueError(f"Invalid mapping catalogue row: {line}")
            if row[0] in enabled_pdb_families:
                pdb_id = row[1].lower()
                if not re.fullmatch(r"[0-9a-z]{4}", pdb_id):
                    raise ValueError(f"Invalid supplied PDB accession: {pdb_id}")
                pdb_ids.add(pdb_id)
    for pdb_id in sorted(pdb_ids):
        plan.append(
            Artifact(
                "pdb_" + pdb_id,
                "pdb",
                pdb_id,
                f"https://files.rcsb.org/download/{pdb_id}.cif.gz",
                f"pdb/raw/{pdb_id}.cif.gz",
            )
        )
    return plan


def _enabled(row: dict, flag: str) -> bool:
    value = row.get(flag, "true").strip().lower()
    if value not in {"true", "false"}:
        raise ValueError(f"Expected true or false for {flag}")
    return value == "true"
