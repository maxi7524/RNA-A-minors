"""Native residue and atom inspection preserving source identifiers."""

from __future__ import annotations

from itertools import islice
from typing import TYPE_CHECKING

from .._tables import _frame

if TYPE_CHECKING:
    from aminor_msa.io.parsers.structure import ResidueRecord, StructureData


def residues_table(data: StructureData, *, model_number=None, chain=None, limit=200):
    """Show bounded native residue views, retaining both identifier namespaces.

    :param data: Selected coordinate file.
    :type data: StructureData
    :param model_number: Optional source model number.
    :type model_number: int | None
    :param chain: Optional author chain identifier.
    :type chain: str | None
    :param limit: Maximum rows; positive integer.
    :type limit: int
    :return: Source author and label keys with atom counts, including ligands/water.
    :rtype: pandas.DataFrame
    :raises ValueError: If limit is not positive.
    """
    if limit < 1:
        raise ValueError("limit must be positive")
    columns = [
        "model_number",
        "chain",
        "number",
        "insertion",
        "name",
        "label_chain",
        "label_number",
        "atoms",
    ]
    rows = [
        {
            **{key: getattr(record, key) for key in columns[:-1]},
            "atoms": len(record.residue),
        }
        for record in islice(
            data.iter_residues(model_number=model_number, chain=chain), limit
        )
    ]
    return _frame(rows, columns)


def atoms_table(record: ResidueRecord):
    """Show atoms of one selected residue, preserving alternate locations.

    :param record: Native residue view.
    :type record: ResidueRecord
    :return: Atom names, elements, altlocs, occupancy and Angstrom coordinates.
    :rtype: pandas.DataFrame
    """
    return _frame(
        [
            {
                "atom": atom.name,
                "element": atom.element.name,
                "altloc": atom.altloc.strip("\x00 "),
                "occupancy": atom.occ,
                "x": atom.pos.x,
                "y": atom.pos.y,
                "z": atom.pos.z,
            }
            for atom in record.residue
        ],
        ["atom", "element", "altloc", "occupancy", "x", "y", "z"],
    )
