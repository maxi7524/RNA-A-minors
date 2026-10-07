"""Lazy families catalogue indexing."""

from __future__ import annotations

import csv
from pathlib import Path

from aminor_msa.utils.logging import get_custom_logger

logger = get_custom_logger(__name__)


class FamilyCatalogue:
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

    def filter(
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
        if self._records is None:
            logger.debug("Indexing family manifest")
            with (self.path).open(newline="", encoding="utf-8") as handle:
                self._records = list(csv.DictReader(handle))
        selected = []
        for row in self._records:
            if (
                participant is not None
                and participant.casefold()
                not in row.get("participant_id", "").casefold()
            ):
                continue
            source_type = row.get("rna_type", "").casefold()
            if rna_type is not None and rna_type.casefold() not in {
                source_type,
                *(token.strip() for token in source_type.split(";")),
            }:
                continue
            if (
                entry_type is not None
                and entry_type.casefold() != row.get("entry_type", "").casefold()
            ):
                continue
            selected.append(dict(row))
        return tuple(selected)
