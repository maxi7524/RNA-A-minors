"""Manifest, catalogue links and source-file inventory tables."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from .._tables import _frame

if TYPE_CHECKING:
    from aminor_msa import DataStore
    from aminor_msa.io.sources.family import FamilySource


def participants_table(store: DataStore):
    """Summarize participants using only the family manifest.

    :param store: Lazy data store.
    :type store: DataStore
    :return: Participant identifiers, names and family counts.
    :rtype: pandas.DataFrame
    """
    grouped = {}
    for row in store.family_records():
        key = row["participant_id"]
        if key not in grouped:
            grouped[key] = {
                "participant_id": key,
                "surname": row.get("student_surname", ""),
                "given_names": row.get("student_given_names", ""),
                "families": set(),
            }
        grouped[key]["families"].add(row["rfam_acc"])
    return _frame(
        [{**row, "families": len(row["families"])} for row in grouped.values()],
        ["participant_id", "surname", "given_names", "families"],
    )


def families_table(
    store: DataStore, *, participant=None, rna_type=None, entry_type=None
):
    """Return filtered manifest rows without reading family payloads.

    :param store: Lazy data store.
    :type store: DataStore
    :param participant: Case-insensitive participant identifier substring.
    :type participant: str | None
    :param rna_type: Exact type token or complete type field, case-insensitive.
    :type rna_type: str | None
    :param entry_type: Exact entry type, case-insensitive.
    :type entry_type: str | None
    :return: All manifest columns for matching families.
    :rtype: pandas.DataFrame
    """
    rows = store.family_records(
        participant=participant, rna_type=rna_type, entry_type=entry_type
    )
    columns = list(store.family_records()[0]) if store.family_records() else []
    return _frame(rows, columns)


def mappings_table(family: FamilySource):
    """Expose every catalogue chain/range row, preserving source numbering.

    :param family: Selected family handle.
    :type family: FamilySource
    :return: Rfam-to-PDB provenance, not a residue-to-MSA alignment.
    :rtype: pandas.DataFrame
    """
    from aminor_msa.rfam_mapping import RfamPdbMapping

    return _frame(
        [asdict(row) for row in family.mappings],
        list(RfamPdbMapping.__dataclass_fields__),
    )


def structures_table(family: FamilySource):
    """List linked files and ZIP report names without reading their payloads.

    :param family: Selected family handle.
    :type family: FamilySource
    :return: PDB keys, coordinate availability and report variants.
    :rtype: pandas.DataFrame
    :raises OSError: If the archive inventory cannot be read.
    """
    rows = []
    for source in family.structures:
        present = source.path.is_file()
        rows.append(
            {
                "pdb_id": source.pdb_id,
                "coordinate_file": str(source.path),
                "coordinate_present": present,
                "compressed_bytes": source.path.stat().st_size if present else None,
                "report_variants": tuple(report.variant for report in source.reports),
            }
        )
    return _frame(
        rows,
        [
            "pdb_id",
            "coordinate_file",
            "coordinate_present",
            "compressed_bytes",
            "report_variants",
        ],
    )
