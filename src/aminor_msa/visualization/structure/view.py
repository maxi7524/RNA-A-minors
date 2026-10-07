"""Optional source-model and chain coordinate visualization."""

from __future__ import annotations

from typing import Any

import gemmi

from aminor_msa.io.parsers.structure import StructureData
from aminor_msa.utils.logging import get_custom_logger

logger = get_custom_logger(__name__)


def view_structure(
    data: StructureData,
    *,
    model_number: int | None = None,
    chain: str | None = None,
    width: int = 800,
    height: int = 500,
) -> Any:
    """Build an embeddable py3Dmol view of one source model and optional chain.

    Coordinates come from the loaded local file; the browser loads the 3Dmol.js
    viewer from its CDN. The returned object supports py3Dmol styling methods.
    No source structure is modified and no browser is launched by this function.

    :param data: Parsed native coordinates.
    :type data: aminor_msa.io.parsers.structure.StructureData
    :param model_number: Original mmCIF model number; required for multiple models.
    :type model_number: int | None
    :param chain: Optional author chain identifier to display.
    :type chain: str | None
    :param width: Positive display width in pixels.
    :type width: int
    :param height: Positive display height in pixels.
    :type height: int
    :return: Notebook viewer object; use as the final cell expression or call show().
    :rtype: py3Dmol.view
    :raises ImportError: If the notebook extra is not installed.
    :raises ValueError: On ambiguous model selection or invalid display dimensions.
    :raises KeyError: If a selected model or chain does not exist.
    """
    if width <= 0 or height <= 0:
        raise ValueError("Viewer dimensions must be positive")
    models = [
        model
        for model in data.structure
        if model_number is None or model.num == model_number
    ]
    if not models:
        raise KeyError(f"No source model {model_number}")
    if len(models) != 1:
        raise ValueError("Select an explicit model_number for visualization")
    selected = gemmi.Model(str(models[0].num))
    for source_chain in models[0]:
        if chain is None or source_chain.name == chain:
            selected.add_chain(source_chain)
    if not len(selected):
        raise KeyError(f"No author chain {chain}")
    display = gemmi.Structure()
    display.add_model(selected)
    try:
        import py3Dmol
    except ImportError as error:
        logger.error("Notebook visualization dependency is unavailable", exc_info=True)
        raise ImportError(
            "Install the notebook extra: uv sync --extra notebook"
        ) from error
    logger.debug(
        "Preparing coordinate viewer for model %s, chain %s", models[0].num, chain
    )
    viewer = py3Dmol.view(width=width, height=height)
    viewer.addModel(display.make_mmcif_document().as_string(), "cif")
    viewer.setStyle({"cartoon": {"color": "spectrum"}, "stick": {"radius": 0.12}})
    viewer.zoomTo()
    return viewer
