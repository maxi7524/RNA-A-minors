"""Supported DSSR annotations displayed with original residue tokens."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from .._tables import _frame

if TYPE_CHECKING:
    from aminor_msa.io.parsers.dssr import DssrReport


def dssr_tables(report: DssrReport):
    """Expose supported DSSR tables with unmodified residue tokens.

    :param report: One parsed ZIP member or standalone report.
    :type report: DssrReport
    :return: Tables keyed by summary, nucleotides, base_pairs, aminor_motifs and dot_brackets.
    :rtype: dict[str, pandas.DataFrame]
    """
    return {
        "summary": _frame(
            [
                {
                    "source": report.source,
                    "complete": report.complete,
                    "nucleotides": len(report.nucleotides),
                    "base_pairs": len(report.base_pairs),
                    "aminor_motifs": len(report.aminor_motifs),
                    "command": report.command,
                }
            ]
        ),
        "nucleotides": _frame(
            [
                {
                    "identifier": n.identifier.raw,
                    "base": n.base,
                    "dot_bracket": n.dot_bracket,
                    "features": n.features,
                }
                for n in report.nucleotides
            ],
            ["identifier", "base", "dot_bracket", "features"],
        ),
        "base_pairs": _frame(
            [
                {**asdict(p), "first": p.first.raw, "second": p.second.raw}
                for p in report.base_pairs
            ],
            [
                "first",
                "second",
                "bases",
                "name",
                "saenger",
                "leontis_westhof",
                "dssr",
                "raw",
            ],
        ),
        "aminor_motifs": _frame(
            [
                {
                    **asdict(m),
                    "donor": m.donor.raw,
                    "first": m.first.raw,
                    "second": m.second.raw,
                }
                for m in report.aminor_motifs
            ],
            ["donor", "first", "second", "kind", "starred", "raw"],
        ),
        "dot_brackets": _frame(
            [asdict(d) for d in report.dot_brackets], ["header", "sequence", "notation"]
        ),
    }
