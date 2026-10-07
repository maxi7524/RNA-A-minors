"""Lazy reports catalogue indexing."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from aminor_msa.utils.logging import get_custom_logger

logger = get_custom_logger(__name__)
REPORT_NAME = re.compile(r"([0-9][A-Za-z0-9]{3})\.out(\d*)", re.IGNORECASE)


class ReportCatalogue:
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

    def get(self, pdb_id: str) -> tuple[tuple[str, str], ...]:
        """Return source links for a key, indexing the source on first access.

        :param pdb_id: Canonical family or PDB identifier.
        :type pdb_id: str
        :return: Source records in deterministic order, or an empty tuple.
        :rtype: tuple
        :raises OSError: If the catalogue cannot be read.
        """
        if self._records is None:
            logger.debug("Indexing DSSR ZIP member names: %s", self.path)
            grouped: dict[str, list[tuple[str, str]]] = {}
            # Read only the central directory; never extract or parse all reports.
            with zipfile.ZipFile(self.path) as archive:
                names = archive.namelist()
                if len(names) != len(set(names)):
                    raise ValueError("DSSR ZIP contains duplicate member names")
                for name in names:
                    match = REPORT_NAME.fullmatch(Path(name).name)
                    if match:
                        pdb, variant = match.groups()
                        grouped.setdefault(pdb.lower(), []).append((variant, name))
            self._records = {
                key: tuple(sorted(values, key=lambda x: (len(x[0]), x[0], x[1])))
                for key, values in grouped.items()
            }
        return self._records.get(pdb_id, ())
