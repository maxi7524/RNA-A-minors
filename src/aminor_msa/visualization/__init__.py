"""Optional domain views exposed through one notebook-facing facade."""

from .alignment import (
    AlignmentBrowser,
    annotations_table,
    sequences_table,
    view_alignment,
)
from .catalogue import (
    FamilyBrowser,
    families_table,
    mappings_table,
    participants_table,
    structures_table,
)
from .config import DEFAULT_STYLE, ViewStyle
from .dssr import dssr_tables, residue_links_table
from .structure import atoms_table, residues_table, view_aminor_motif, view_structure

__all__ = [
    "DEFAULT_STYLE",
    "AlignmentBrowser",
    "FamilyBrowser",
    "ViewStyle",
    "annotations_table",
    "atoms_table",
    "dssr_tables",
    "families_table",
    "mappings_table",
    "participants_table",
    "residue_links_table",
    "residues_table",
    "sequences_table",
    "structures_table",
    "view_alignment",
    "view_aminor_motif",
    "view_structure",
]
