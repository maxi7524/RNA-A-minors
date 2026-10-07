"""Rfam family descriptions and Infernal covariance-model headers."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aminor_msa.utils.logging import get_custom_logger

from .text import open_text

logger = get_custom_logger(__name__)


@dataclass
class FamilyMetadata:
    """Rfam metadata, retaining the complete source JSON payload.

    :param accession: RFxxxxx accession.
    :param name: Rfam family identifier.
    :param description: Human-readable family description.
    :param payload: Complete response, including release, clan and CM information.
    """

    accession: str
    name: str
    description: str
    payload: dict[str, Any]


@dataclass
class CovarianceModel:
    """Infernal header and a path to the unmodified model body.

    The numerical CM/HMM body is consumed by Infernal, not interpreted here.
    Repeated header fields such as COM are retained separately.

    :param path: Source model path for subsequent Infernal use.
    :param fields: Header field to repeated values, ending at the first CM marker.
    """

    path: Path
    fields: dict[str, tuple[str, ...]]

    @property
    def accession(self) -> str:
        """Return the first CM accession, excluding the embedded HMM header.

        :rtype: str
        """
        return self.fields["ACC"][0]

    @property
    def consensus_length(self) -> int:
        """Return the number of model consensus positions.

        :rtype: int
        """
        return int(self.fields["CLEN"][0])


def read_family_metadata(path: str | Path) -> FamilyMetadata:
    """Read and validate a Rfam JSON response without dropping fields.

    :param path: Selected family JSON filename.
    :type path: str | pathlib.Path
    :return: Description and complete source metadata.
    :rtype: FamilyMetadata
    :raises ValueError: If the required Rfam fields are absent.
    """
    logger.debug("Reading Rfam metadata: %s", path)
    with open_text(path) as handle:
        payload = json.load(handle)
    family = payload.get("rfam") if isinstance(payload, dict) else None
    if not isinstance(family, dict) or not all(
        isinstance(family.get(key), str) for key in ("acc", "id", "description")
    ):
        raise ValueError("Expected Rfam accession, identifier and description")
    return FamilyMetadata(family["acc"], family["id"], family["description"], payload)


def read_covariance_model(path: str | Path) -> CovarianceModel:
    """Stream the Infernal header, stopping before its numerical body.

    :param path: Plain or gzipped Infernal CM filename.
    :type path: str | pathlib.Path
    :return: Parsed first CM header with a reference to its source file.
    :rtype: CovarianceModel
    :raises ValueError: If the Infernal header or required fields are invalid.
    """
    logger.debug("Reading Infernal header: %s", path)
    fields = {}
    with open_text(path) as handle:
        if not handle.readline().startswith("INFERNAL1/"):
            raise ValueError("Expected Infernal 1 covariance model")
        for line in handle:
            if line.strip() == "CM":
                break
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                fields.setdefault(parts[0], []).append(parts[1].strip())
        else:
            raise ValueError("Missing Infernal CM body marker")
    if not all(key in fields for key in ("ACC", "NAME", "CLEN")):
        raise ValueError("Missing required Infernal header fields")
    if int(fields["CLEN"][0]) <= 0:
        raise ValueError("Infernal consensus length must be positive")
    return CovarianceModel(
        Path(path), {key: tuple(values) for key, values in fields.items()}
    )
