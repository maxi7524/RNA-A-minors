"""Public lazy data-access facade."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from aminor_msa.io.parsers.catalogue import RfamPdbMapping
from aminor_msa.utils.logging import get_custom_logger

from .catalog.families import FamilyCatalogue
from .catalog.pdb import PdbCatalogue
from .catalog.reports import ReportCatalogue
from .parsers.dssr import DssrReport
from .sources.family import FamilySource
from .sources.structure import StructureSource
from .storage.archive import read_report
from .storage.cache import ParsedCache

logger = get_custom_logger(__name__)


class DataStore:
    """Lazy source access with small indexes and an optional object-count LRU.

    Construction and handle lookup do not read source files. The family manifest,
    mapping table and ZIP central directory are indexed only when queried. Large
    parsed objects are not cached by default. References retained by the caller
    remain the caller's responsibility; cache_entries is not a byte/RSS limit.
    Standalone reads retain no file handles. Parallel worker contexts may supply
    a reader owning one ZIP until the iterator closes. Each worker owns its store;
    thread sharing of a mutable cached object is not supported.

    :param root: Data directory, independent of the current notebook location.
    :type root: str | pathlib.Path
    :param cache_entries: Maximum retained parsed objects; zero disables caching.
    :type cache_entries: int
    :param dssr_archive: Optional alternate ZIP path; default uses the supplied ZIP.
    :type dssr_archive: str | pathlib.Path | None
    :raises ValueError: On a negative cache limit.
    """

    def __init__(
        self,
        root: str | Path = "data",
        *,
        cache_entries: int = 0,
        dssr_archive: str | Path | None = None,
    ) -> None:
        if cache_entries < 0:
            raise ValueError("cache_entries must be nonnegative")
        self.root = Path(root).resolve()
        self.archive = (
            Path(dssr_archive).resolve()
            if dssr_archive is not None
            else self.root / "dssr/raw/dssr_out_261003.zip"
        )
        self.cache_entries = cache_entries
        self._cache = ParsedCache(cache_entries)
        self._families = FamilyCatalogue(self.root / "config/families.csv")
        self._pdb_catalogue = PdbCatalogue(self.root / "rfam/raw/Rfam.pdb")
        self._report_catalogue = ReportCatalogue(self.archive)
        self._dssr_reader: Callable[[str], DssrReport] | None = None

    def family(self, accession: str) -> FamilySource:
        """Return a family handle without reading its files.

        :param accession: RFxxxxx family accession, case-insensitive.
        :type accession: str
        :return: Lazy family source.
        :rtype: FamilySource
        :raises ValueError: On a malformed accession.
        """
        accession = accession.upper()
        if not re.fullmatch(r"RF\d{5}", accession):
            raise ValueError("Expected an RFxxxxx family accession")
        return FamilySource(self, accession)

    def structure(self, pdb_id: str) -> StructureSource:
        """Return a PDB handle without reading coordinates or reports.

        :param pdb_id: Four-character PDB identifier, case-insensitive.
        :type pdb_id: str
        :return: Lazy coordinate/report source.
        :rtype: StructureSource
        :raises ValueError: On a malformed identifier.
        """
        pdb_id = pdb_id.lower()
        if not re.fullmatch(r"[0-9][a-z0-9]{3}", pdb_id):
            raise ValueError("Expected a four-character PDB identifier")
        return StructureSource(self, pdb_id)

    def family_records(
        self,
        *,
        participant: str | None = None,
        rna_type: str | None = None,
        entry_type: str | None = None,
    ) -> tuple[dict[str, str], ...]:
        """Filter the small family manifest before opening any heavy sources.

        :param participant: Case-insensitive substring of participant_id.
        :type participant: str | None
        :param rna_type: Case-insensitive exact semicolon-delimited RNA type token,
            such as rRNA or riboswitch, or the complete type field.
        :type rna_type: str | None
        :param entry_type: Case-insensitive exact entry_type, such as Family.
        :type entry_type: str | None
        :return: Copies of matching manifest rows in source order.
        :rtype: tuple[dict[str, str], ...]
        """
        return self._families.filter(
            participant=participant, rna_type=rna_type, entry_type=entry_type
        )

    def family_ids(
        self,
        *,
        participant: str | None = None,
        rna_type: str | None = None,
        entry_type: str | None = None,
    ) -> tuple[str, ...]:
        """Return unique accessions selected by the family manifest filters.

        :param participant: Case-insensitive participant_id substring.
        :type participant: str | None
        :param rna_type: RNA type token or complete manifest type field.
        :type rna_type: str | None
        :param entry_type: Exact entry type, case-insensitive.
        :type entry_type: str | None
        :return: Selected accessions in manifest order.
        :rtype: tuple[str, ...]
        """
        return tuple(
            dict.fromkeys(
                row["rfam_acc"]
                for row in self.family_records(
                    participant=participant, rna_type=rna_type, entry_type=entry_type
                )
            )
        )

    def load_state(self) -> dict[str, int | bool]:
        """Inspect retained state without opening any source files.

        :return: Object cache size/limit and lazy index initialization flags.
        :rtype: dict[str, int | bool]
        """
        return {
            "cached_objects": len(self._cache),
            "cache_entries": self.cache_entries,
            "family_manifest_indexed": self._families.initialized,
            "pdb_catalogue_indexed": self._pdb_catalogue.initialized,
            "zip_names_indexed": self._report_catalogue.initialized,
        }

    def clear_cache(self) -> None:
        """Release cached parsed objects; small source indexes remain available.

        :rtype: None
        """
        self._cache.clear()

    def __getstate__(self) -> dict[str, Any]:
        """Serialize source locations and configuration without process-local state.

        :return: State for a new worker, without parsed objects or indexes.
        :rtype: dict[str, typing.Any]
        """
        return dict(
            self.__dict__,
            _cache=ParsedCache(self.cache_entries),
            _families=FamilyCatalogue(self.root / "config/families.csv"),
            _pdb_catalogue=PdbCatalogue(self.root / "rfam/raw/Rfam.pdb"),
            _report_catalogue=ReportCatalogue(self.archive),
            _dssr_reader=None,
        )

    def _read_dssr(self, member: str) -> DssrReport:
        logger.info("Reading selected DSSR ZIP member: %s", member)
        if self._dssr_reader is not None:
            return self._dssr_reader(member)
        return read_report(self.archive, member)

    def _load(self, kind: str, key: str, reader: Callable[[], Any]) -> Any:
        return self._cache.load(kind, key, reader)

    def _mappings(self, accession: str) -> tuple[RfamPdbMapping, ...]:
        return self._pdb_catalogue.get(accession)

    def _reports(self, pdb_id: str) -> tuple[tuple[str, str], ...]:
        return self._report_catalogue.get(pdb_id)
