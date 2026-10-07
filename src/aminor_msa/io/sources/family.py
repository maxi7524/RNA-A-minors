"""Lazy family handle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from aminor_msa.io.parsers.catalogue import RfamPdbMapping

from ..parsers.rfam import (
    CovarianceModel,
    FamilyMetadata,
    read_covariance_model,
    read_family_metadata,
)
from ..parsers.stockholm import StockholmAlignment, read_stockholm

if TYPE_CHECKING:
    from ..store import DataStore
    from .structure import StructureSource


@dataclass(frozen=True)
class FamilySource:
    """Paths and lazy readers for one Rfam family.

    :param store: Owning source store.
    :param accession: Canonical family accession.
    """

    store: DataStore
    accession: str

    @property
    def path(self) -> Path:
        """Return the family directory without reading it.

        :rtype: pathlib.Path
        """
        return self.store.root / "rfam/raw" / self.accession

    @property
    def alignment(self) -> StockholmAlignment:
        """Read only this family's MSA on access.

        :rtype: StockholmAlignment
        """

        def read():
            alignment = read_stockholm(self.path / "seed.sto.gz")
            if alignment.file_annotations.get("AC") != (self.accession,):
                raise ValueError("Stockholm accession differs from the selected family")
            return alignment

        return self.store._load("alignment", self.accession, read)

    @property
    def metadata(self) -> FamilyMetadata:
        """Read only this family's complete metadata on access.

        :rtype: FamilyMetadata
        """

        def read():
            metadata = read_family_metadata(self.path / "family.json")
            if metadata.accession != self.accession:
                raise ValueError("Metadata accession differs from the selected family")
            return metadata

        return self.store._load("metadata", self.accession, read)

    @property
    def covariance_model(self) -> CovarianceModel:
        """Read only this family's CM header on access.

        :rtype: CovarianceModel
        """

        def read():
            model = read_covariance_model(self.path / "model.cm")
            if model.accession != self.accession:
                raise ValueError("CM accession differs from the selected family")
            return model

        return self.store._load("cm", self.accession, read)

    @property
    def mappings(self) -> tuple[RfamPdbMapping, ...]:
        """Return catalogue chain/range links; these are not MSA column mappings.

        :rtype: tuple[RfamPdbMapping, ...]
        """
        return self.store._mappings(self.accession)

    @property
    def structures(self) -> tuple[StructureSource, ...]:
        """Return unique linked PDB handles without loading their coordinates.

        :rtype: tuple[StructureSource, ...]
        """
        return tuple(
            self.store.structure(pdb)
            for pdb in dict.fromkeys(r.pdb_id for r in self.mappings)
        )
