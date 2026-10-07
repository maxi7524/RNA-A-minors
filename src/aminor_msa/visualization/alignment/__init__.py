"""Alignment tables and views public API."""

from __future__ import annotations

from .browser import AlignmentBrowser
from .tables import annotations_table, sequences_table
from .view import view_alignment

__all__ = ["AlignmentBrowser", "annotations_table", "sequences_table", "view_alignment"]
