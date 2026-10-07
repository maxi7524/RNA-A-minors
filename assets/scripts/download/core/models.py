"""Immutable acquisition requests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Artifact:
    """An immutable acquisition request.

    :param key: Unique artifact identifier.
    :type key: str
    :param kind: Validation format.
    :type kind: str
    :param accession: Expected Rfam or PDB accession.
    :type accession: str
    :param url: Download URL or supplied source reference.
    :type url: str
    :param relative_path: Destination relative to the data root.
    :type relative_path: str
    """

    key: str
    kind: str
    accession: str
    url: str
    relative_path: str
