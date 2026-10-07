"""Source format and transport checks."""

from __future__ import annotations

from pathlib import Path

from aminor_msa.utils.logging import get_custom_logger

logger = get_custom_logger(__name__)
import gzip
import json
import re
import zipfile

from aminor_msa.utils.files import CHUNK_SIZE

from .models import Artifact


def validate_artifact(path: Path, artifact: Artifact) -> dict:
    """Check transport integrity and basic source-format constraints.

    This does not validate biological annotations or residue correspondences.

    :param path: Downloaded or supplied file.
    :type path: Path
    :param artifact: Expected format and identity.
    :type artifact: Artifact
    :return: Format diagnostics for provenance.
    :rtype: dict
    :raises ValueError: If content has an unexpected format or identity.
    """
    if path.stat().st_size == 0:
        raise ValueError("Empty artifact")
    if artifact.kind == "pdb":
        # Stream all decompressed bytes to check the gzip CRC with bounded memory.
        with gzip.open(path, "rb") as handle:
            prefix = handle.read(CHUNK_SIZE).decode("utf-8")
            while handle.read(CHUNK_SIZE):
                pass
        match = re.search(r"(?m)^data_(\S+)", prefix)
        if not match or match[1].casefold() != artifact.accession.casefold():
            raise ValueError("Unexpected mmCIF data block identity")
        return {
            "gzip_crc": "passed",
            "mmcif_data_block": match[1],
            "validation_level": "transport_and_data_block",
        }
    if artifact.kind == "seed":
        # Reassemble interleaved Stockholm blocks before comparing column counts.
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            text = handle.read()
        if not text.startswith("# STOCKHOLM 1.0") or not text.rstrip().endswith("//"):
            raise ValueError("Incomplete or unexpected Stockholm alignment")
        if re.findall(r"(?m)^#=GF AC\s+(\S+)", text) != [artifact.accession]:
            raise ValueError("Stockholm accession does not match request")
        lengths: dict[str, int] = {}
        annotations: dict[str, int] = {}
        for line in text.splitlines():
            parts = line.split()
            if line.startswith("#=GC ") and len(parts) == 3:
                annotations[parts[1]] = annotations.get(parts[1], 0) + len(parts[2])
            elif line and not line.startswith("#") and line != "//":
                if len(parts) != 2:
                    raise ValueError("Unexpected Stockholm sequence row")
                lengths[parts[0]] = lengths.get(parts[0], 0) + len(parts[1])
        widths = set(lengths.values())
        if len(widths) != 1 or next(iter(widths)) == 0:
            raise ValueError("Empty or unequal Stockholm sequence lengths")
        width = next(iter(widths))
        if any(length != width for length in annotations.values()):
            raise ValueError("Stockholm column annotation length mismatch")
        return {
            "sequence_count": len(lengths),
            "alignment_columns": width,
            "has_ss_cons": "SS_cons" in annotations,
            "has_rf": "RF" in annotations,
        }
    if artifact.kind == "cm":
        text = path.read_text(encoding="utf-8")
        if not text.startswith("INFERNAL1/") or not text.rstrip().endswith("//"):
            raise ValueError("Incomplete or unexpected Infernal model")
        # REMARK: Infernal files also contain a filter HMM with its own ACC field.
        model_accessions = re.findall(r"(?m)^ACC\s+(\S+)", text)
        if not model_accessions or set(model_accessions) != {artifact.accession}:
            raise ValueError("Covariance-model accession does not match request")
        return {"model_header": text.splitlines()[0]}
    if artifact.kind == "metadata":
        metadata = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict) or not isinstance(metadata.get("rfam"), dict):
            raise ValueError("Unexpected metadata schema")
        if metadata["rfam"].get("acc") != artifact.accession:
            raise ValueError("Metadata accession does not match request")
        return {"rfam_release": metadata["rfam"].get("release")}
    if artifact.kind == "dssr_zip":
        with zipfile.ZipFile(path) as archive:
            members = [entry for entry in archive.infolist() if not entry.is_dir()]
        if not members:
            raise ValueError("Empty DSSR archive")
        # REMARK: Inventory inspection does not decompress the 12.9 GB archive.
        return {
            "files": len(members),
            "uncompressed_bytes": sum(i.file_size for i in members),
            "validation_level": "zip_inventory_and_file_hash",
        }
    if artifact.kind == "supplied_table":
        return {"validation_level": "file_hash"}
    raise ValueError(f"Unknown artifact kind: {artifact.kind}")
