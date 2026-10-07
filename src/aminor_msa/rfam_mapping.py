"""Compatibility imports for the Rfam-to-PDB catalogue reader."""

from .io.parsers.catalogue import RfamPdbMapping, read_rfam_pdb

__all__ = ["RfamPdbMapping", "read_rfam_pdb"]
