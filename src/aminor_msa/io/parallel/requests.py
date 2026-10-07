"""Artifact selection and keyed reading."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from aminor_msa.utils.logging import get_custom_logger

from ..store import DataStore

logger = get_custom_logger(__name__)


KINDS = {"alignment", "metadata", "cm", "coordinates", "cif", "dssr"}


@dataclass(frozen=True)
class SourceRequest:
    """One independently addressable artifact selected before heavy I/O.

    :param kind: alignment, metadata, cm, coordinates, cif or dssr.
    :param accession: RFxxxxx for family data; PDB identifier otherwise.
    :param variant: DSSR filename suffix when selecting a specific report.
    """

    kind: str
    accession: str
    variant: str | None = None


@dataclass
class LoadedSource:
    """A source key and its parsed object or worker preparation result.

    :param request: Source identifier retained after loading/preparation.
    :param data: Parsed source object, or custom transform return value.
    """

    request: SourceRequest
    data: Any


def read_request(store: DataStore, request: SourceRequest) -> Any:
    """Read one keyed artifact using the same lazy public source readers.

    :param store: Source store owned by the calling worker or application.
    :type store: DataStore
    :param request: Artifact kind and identifier.
    :type request: SourceRequest
    :return: Parsed selected source object.
    :rtype: typing.Any
    :raises ValueError: On invalid kinds or variants for non-DSSR artifacts.
    """
    if request.kind not in KINDS:
        raise ValueError(f"Unknown source kind: {request.kind}")
    if request.variant is not None and request.kind != "dssr":
        raise ValueError("Only DSSR source requests have a report variant")
    if request.kind == "alignment":
        return store.family(request.accession).alignment
    if request.kind == "metadata":
        return store.family(request.accession).metadata
    if request.kind == "cm":
        return store.family(request.accession).covariance_model
    if request.kind == "coordinates":
        return store.structure(request.accession).coordinates
    if request.kind == "cif":
        return store.structure(request.accession).cif_document
    return store.structure(request.accession).report(request.variant).read()


def iter_requests(
    store: DataStore,
    *,
    kinds: Iterable[str] = ("alignment",),
    families: Iterable[str] | None = None,
    participant: str | None = None,
    rna_type: str | None = None,
    entry_type: str | None = None,
) -> Iterator[SourceRequest]:
    """Select and deduplicate artifact keys using only small source indexes.

    Missing report names produce no DSSR request; absence is not a negative label.
    Existing coordinate/alignment files are checked when read, not at selection.
    Catalogue chain/range provenance remains available from FamilySource.mappings.

    :param store: Source store.
    :type store: DataStore
    :param kinds: Requested artifact kinds, in output order within each family.
    :type kinds: collections.abc.Iterable[str]
    :param families: Optional explicit families intersected with manifest filters.
    :type families: collections.abc.Iterable[str] | None
    :param participant: Participant_id substring, case-insensitive.
    :type participant: str | None
    :param rna_type: RNA type token or complete manifest field, case-insensitive.
    :type rna_type: str | None
    :param entry_type: Exact manifest entry type, case-insensitive.
    :type entry_type: str | None
    :return: Unique selected artifact requests; no heavy sources are parsed.
    :rtype: collections.abc.Iterator[SourceRequest]
    :raises ValueError: On an unsupported artifact kind.
    """
    kinds = tuple(kinds)
    if set(kinds) - KINDS:
        raise ValueError(f"Unknown source kinds: {set(kinds) - KINDS}")
    selected = store.family_ids(
        participant=participant, rna_type=rna_type, entry_type=entry_type
    )
    allowed = (
        None
        if families is None
        else {store.family(accession).accession for accession in families}
    )
    seen = set()
    for accession in selected:
        if allowed is not None and accession not in allowed:
            continue
        family = store.family(accession)
        for kind in kinds:
            if kind in {"alignment", "metadata", "cm"}:
                candidates = (SourceRequest(kind, accession),)
            elif kind in {"coordinates", "cif"}:
                candidates = (
                    SourceRequest(kind, source.pdb_id) for source in family.structures
                )
            else:
                candidates = (
                    SourceRequest(kind, source.pdb_id, report.variant)
                    for source in family.structures
                    for report in source.reports
                )
            for request in candidates:
                if request not in seen:
                    seen.add(request)
                    yield request
