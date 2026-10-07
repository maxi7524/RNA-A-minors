"""Lazy structure handle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import gemmi

from ..parsers.structure import StructureData, read_mmcif_document, read_structure

if TYPE_CHECKING:
    from ..store import DataStore
    from .structure import StructureSource
from .report import ReportSource


@dataclass(frozen=True)
class StructureSource:
    """Lazy coordinates and report variants associated with a PDB identifier.

    :param store: Owning source store.
    :param pdb_id: Lowercase PDB accession.
    """

    store: DataStore
    pdb_id: str

    @property
    def path(self) -> Path:
        """Return the coordinate source path without opening it.

        :rtype: pathlib.Path
        """
        return self.store.root / "pdb/raw" / f"{self.pdb_id}.cif.gz"

    @property
    def coordinates(self) -> StructureData:
        """Read one coordinate file, including all of its source models.

        :rtype: StructureData
        """
        return self.store._load(
            "coordinates", self.pdb_id, lambda: read_structure(self.path)
        )

    @property
    def cif_document(self) -> gemmi.cif.Document:
        """Read all mmCIF categories on request, independently of atomic models.

        :rtype: gemmi.cif.Document
        """
        return self.store._load(
            "cif", self.pdb_id, lambda: read_mmcif_document(self.path)
        )

    @property
    def reports(self) -> tuple[ReportSource, ...]:
        """List report handles from ZIP names without decompressing any member.

        :rtype: tuple[ReportSource, ...]
        """
        return tuple(
            ReportSource(self.store, name, variant)
            for variant, name in self.store._reports(self.pdb_id)
        )

    def report(self, variant: str | int | None = None) -> ReportSource:
        """Select one report, requiring a variant when multiple reports exist.

        :param variant: Literal out suffix, such as 1; unrelated to model numbering.
        :type variant: str | int | None
        :return: Lazy report handle.
        :rtype: ReportSource
        :raises KeyError: If no report matches.
        :raises ValueError: If the requested choice is ambiguous.
        """
        matches = [
            report
            for report in self.reports
            if variant is None or report.variant == str(variant)
        ]
        if not matches:
            raise KeyError(f"No DSSR report for {self.pdb_id}, variant={variant}")
        if len(matches) != 1:
            raise ValueError(f"Select an explicit DSSR variant for {self.pdb_id}")
        return matches[0]
