"""Manifests families."""

from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path

from aminor_msa.utils.logging import get_custom_logger

logger = get_custom_logger(__name__)


def build_manifest(source: Path, output: Path, surname: str | None = None) -> int:
    """Create a CSV manifest while preserving assignment metadata.

    :param source: Assignment TSV with positional surname and given-name columns.
    :type source: Path
    :param output: Output CSV path.
    :type output: Path
    :param surname: Optional case-insensitive surname selection.
    :type surname: str | None
    :return: Number of written rows.
    :rtype: int
    :raises ValueError: If a header, row or participant identifier is invalid.
    """
    rows = []
    with source.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader, [])
        if header[:3] != ["Accession", "Student", "Student"] or len(header) != 11:
            raise ValueError("Unexpected assignment header")
        for row in reader:
            if not row:
                continue
            if len(row) != 11 or not re.fullmatch(r"RF\d{5}", row[0]):
                raise ValueError(f"Invalid assignment row: {row}")
            if (
                surname is not None
                and row[1].strip().casefold() != surname.strip().casefold()
            ):
                continue
            transliterated = unicodedata.normalize(
                "NFKD", row[1].strip().lower().replace("ł", "l")
            )
            participant = re.sub(
                r"[^a-z0-9]+", "", transliterated.encode("ascii", "ignore").decode()
            )
            if not participant:
                raise ValueError("Empty participant identifier")
            rows.append(
                dict(
                    zip(
                        [
                            "rfam_acc",
                            "student_surname",
                            "student_given_names",
                            "entry_type",
                            "description",
                            "family_name",
                            "rna_type",
                            "seed_sequences",
                            "full_sequences",
                            "species",
                            "reported_3d_structures",
                        ],
                        [v.strip() for v in row],
                    )
                )
            )
            rows[-1].update(
                participant_id=participant,
                download_seed_alignment="true",
                download_covariance_model="true",
                download_family_metadata="true",
                download_pdb_structures="true",
            )
    if not rows:
        raise ValueError("Assignment selection is empty")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Wrote %s assignment rows to %s", len(rows), output)
    return len(rows)
