"""Utilities for parsing the Rfam-to-PDB mapping table."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RfamPdbMapping:
    """One Rfam-to-PDB chain mapping.

    :param rfam_acc: Rfam family accession.
    :type rfam_acc: str
    :param pdb_id: Four-character PDB identifier.
    :type pdb_id: str
    :param chain: PDB chain identifier.
    :type chain: str
    :param pdb_start: Start residue in the PDB chain.
    :type pdb_start: int
    :param pdb_end: End residue in the PDB chain.
    :type pdb_end: int
    :param bit_score: Infernal covariance-model bit score.
    :type bit_score: float
    :param evalue_score: Infernal E-value.
    :type evalue_score: float
    :param cm_start: Start coordinate in the Rfam covariance model.
    :type cm_start: int
    :param cm_end: End coordinate in the Rfam covariance model.
    :type cm_end: int
    :param extra: Additional field present in the supplied flat file; retained losslessly.
    :type extra: str | None
    """

    rfam_acc: str
    pdb_id: str
    chain: str
    pdb_start: int
    pdb_end: int
    bit_score: float
    evalue_score: float
    cm_start: int
    cm_end: int
    extra: str | None = None


def read_rfam_pdb(path: Path) -> list[RfamPdbMapping]:
    """Parse the supplied tab-delimited ``Rfam.pdb`` mapping file.

    :param path: Path to the mapping file.
    :type path: pathlib.Path
    :return: Parsed mapping records.
    :rtype: list[RfamPdbMapping]
    :raises ValueError: If a row has fewer than nine columns.
    """
    records: list[RfamPdbMapping] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for line_number, row in enumerate(csv.reader(handle, delimiter="\t"), start=1):
            if not row:
                continue
            if len(row) < 9:
                raise ValueError(
                    f"{path}:{line_number}: expected >=9 columns, got {len(row)}"
                )
            records.append(
                RfamPdbMapping(
                    rfam_acc=row[0],
                    pdb_id=row[1].lower(),
                    chain=row[2],
                    pdb_start=int(row[3]),
                    pdb_end=int(row[4]),
                    bit_score=float(row[5]),
                    evalue_score=float(row[6]),
                    cm_start=int(row[7]),
                    cm_end=int(row[8]),
                    extra=row[9] if len(row) > 9 else None,
                )
            )
    return records
