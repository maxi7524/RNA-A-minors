"""Lazy pdb catalogue indexing."""

from __future__ import annotations

from pathlib import Path

from aminor_msa.io.parsers.catalogue import RfamPdbMapping, read_rfam_pdb
from aminor_msa.utils.logging import get_custom_logger

logger = get_custom_logger(__name__)


class PdbCatalogue:
    """Lazy source catalogue with process-local records.

    :param path: Source manifest, mapping table or ZIP archive.
    :type path: pathlib.Path
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._records = None

    @property
    def initialized(self) -> bool:
        """Return whether the source index has been read.

        :rtype: bool
        """
        return self._records is not None

    def get(self, accession: str) -> tuple[RfamPdbMapping, ...]:
        """Return source links for a key, indexing the source on first access.

        :param accession: Canonical family or PDB identifier.
        :type accession: str
        :return: Source records in deterministic order, or an empty tuple.
        :rtype: tuple
        :raises OSError: If the catalogue cannot be read.
        """
        if self._records is None:
            logger.debug("Indexing Rfam-to-PDB catalogue")
            grouped: dict[str, list[RfamPdbMapping]] = {}
            for record in read_rfam_pdb(self.path):
                grouped.setdefault(record.rfam_acc, []).append(record)
            self._records = {key: tuple(values) for key, values in grouped.items()}
        return self._records.get(accession, ())
