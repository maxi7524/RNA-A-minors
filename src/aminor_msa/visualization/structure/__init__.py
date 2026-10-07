"""Structure tables and views public API."""

from __future__ import annotations

from .motifs import view_aminor_motif
from .tables import atoms_table, residues_table
from .view import view_structure

__all__ = ["atoms_table", "residues_table", "view_aminor_motif", "view_structure"]
