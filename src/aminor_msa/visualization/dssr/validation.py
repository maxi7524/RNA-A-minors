"""Visible diagnostics for DSSR-to-coordinate author-key lookups."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aminor_msa.utils.logging import get_custom_logger

from .._tables import _frame

if TYPE_CHECKING:
    from aminor_msa.io.parsers.dssr import DssrReport
    from aminor_msa.io.parsers.structure import StructureData
logger = get_custom_logger(__name__)


def residue_links_table(data: StructureData, report: DssrReport, *, model_number: int):
    """Audit exact author-key lookups; failures remain visible as table rows.

    This checks identifiers only, not source snapshot or atom-level equivalence.
    Unsupported qualified IDs and ambiguous keys are not silently accepted.

    :param data: Source mmCIF coordinates.
    :type data: StructureData
    :param report: Selected DSSR report.
    :type report: DssrReport
    :param model_number: Explicit source model, independent of the report suffix.
    :type model_number: int
    :return: Raw DSSR keys, source keys, status and diagnostic.
    :rtype: pandas.DataFrame
    :raises KeyError: If the requested source model does not exist.
    """
    if model_number not in {model.num for model in data.structure}:
        raise KeyError(f"No source model {model_number}")
    rows = []
    for nucleotide in report.nucleotides:
        identifier = nucleotide.identifier
        row = {
            "identifier": identifier.raw,
            "dssr_model": identifier.model,
            "source_model": model_number,
            "chain": identifier.chain,
            "number": identifier.number,
            "insertion": identifier.insertion,
            "name": identifier.name,
            "label_chain": None,
            "label_number": None,
            "status": "matched",
            "diagnostic": "",
        }
        try:
            record = data.resolve_nucleotide(identifier, model_number=model_number)
            row.update(label_chain=record.label_chain, label_number=record.label_number)
        except (KeyError, ValueError) as error:
            row.update(
                status="missing" if isinstance(error, KeyError) else "unresolved",
                diagnostic=str(error),
            )
        rows.append(row)
    failures = sum(row["status"] != "matched" for row in rows)
    if failures:
        logger.warning(
            "Unresolved DSSR residue identifiers: %s of %s", failures, len(rows)
        )
    return _frame(
        rows,
        [
            "identifier",
            "dssr_model",
            "source_model",
            "chain",
            "number",
            "insertion",
            "name",
            "label_chain",
            "label_number",
            "status",
            "diagnostic",
        ],
    )
