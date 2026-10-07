"""Sequence lengths and source Stockholm annotation tables."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._tables import _frame

if TYPE_CHECKING:
    from aminor_msa.io.parsers.stockholm import StockholmAlignment


def sequences_table(alignment: StockholmAlignment):
    """Summarize sequences without duplicating their full strings in a table.

    :param alignment: Parsed selected MSA.
    :type alignment: StockholmAlignment
    :return: IDs, aligned/ungapped lengths and gap counts.
    :rtype: pandas.DataFrame
    """
    return _frame(
        [
            {
                "sequence_id": key,
                "aligned_length": len(sequence),
                "ungapped_length": len(sequence.replace("-", "").replace(".", "")),
                "gap_count": sequence.count("-") + sequence.count("."),
            }
            for key, sequence in alignment.sequences.items()
        ],
        ["sequence_id", "aligned_length", "ungapped_length", "gap_count"],
    )


def annotations_table(alignment: StockholmAlignment):
    """Expose GF, GS, GR and GC records with their source scope.

    :param alignment: Parsed selected MSA.
    :type alignment: StockholmAlignment
    :return: Annotation scope, sequence key, tag and value.
    :rtype: pandas.DataFrame
    """
    rows = []
    for tag, values in alignment.file_annotations.items():
        rows.extend(
            {"scope": "GF", "sequence_id": None, "tag": tag, "value": value}
            for value in values
        )
    for key, records in alignment.sequence_annotations.items():
        for tag, values in records.items():
            rows.extend(
                {"scope": "GS", "sequence_id": key, "tag": tag, "value": value}
                for value in values
            )
    for key, records in alignment.residue_annotations.items():
        rows.extend(
            {"scope": "GR", "sequence_id": key, "tag": tag, "value": value}
            for tag, value in records.items()
        )
    rows.extend(
        {"scope": "GC", "sequence_id": None, "tag": tag, "value": value}
        for tag, value in alignment.column_annotations.items()
    )
    return _frame(rows, ["scope", "sequence_id", "tag", "value"])
