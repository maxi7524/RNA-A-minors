"""Compact worker results for exploratory loading without large IPC objects."""

from .requests import read_request


def summarize_request(store, request):
    """Read one source inside the worker and return only scalar counts.

    This diagnostic transform is not a training feature extractor. It avoids
    transferring parsed coordinates, a full MSA or report text between processes.

    :param store: Worker-local source store.
    :type store: aminor_msa.DataStore
    :param request: Independently addressable source key.
    :type request: SourceRequest
    :return: Source identity, quantity, count and optional width/completeness.
    :rtype: dict
    """
    value = read_request(store, request)
    result = {
        "kind": request.kind,
        "accession": request.accession,
        "variant": request.variant,
    }
    if request.kind == "alignment":
        result.update(
            quantity="sequences", count=len(value.sequences), width=value.length
        )
    elif request.kind == "metadata":
        result.update(quantity="top_level_fields", count=len(value.payload))
    elif request.kind == "cm":
        result.update(quantity="consensus_positions", count=value.consensus_length)
    elif request.kind == "coordinates":
        result.update(
            quantity="residues_all_models", count=sum(1 for _ in value.iter_residues())
        )
    elif request.kind == "cif":
        result.update(quantity="data_blocks", count=len(value))
    else:
        result.update(
            quantity="nucleotides",
            count=len(value.nucleotides),
            complete=value.complete,
            base_pairs=len(value.base_pairs),
            aminor_motifs=len(value.aminor_motifs),
        )
    return result
