"""Lazy report handle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..parsers.dssr import DssrReport

if TYPE_CHECKING:
    from ..store import DataStore


@dataclass(frozen=True)
class ReportSource:
    """One member of the supplied archive; no open ZIP handle is retained.

    :param store: Owning source store.
    :param member: Exact ZIP member name.
    :param variant: Literal filename suffix, not a source mmCIF model number.
    """

    store: DataStore
    member: str
    variant: str

    def read(self) -> DssrReport:
        """Decompress and parse this member alone, without extracting to disk.

        :return: Parsed selected report.
        :rtype: DssrReport
        :raises ValueError: On malformed supported report sections.
        """

        return self.store._load(
            "dssr", self.member, lambda: self.store._read_dssr(self.member)
        )
