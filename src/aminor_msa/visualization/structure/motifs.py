"""Coordinate markers for exact source DSSR triplets."""

from __future__ import annotations

from .view import view_structure


def view_aminor_motif(data, motif, *, model_number: int, style=None):
    """Mark one DSSR triplet using exact source-residue coordinate lookups.

    Spheres are placed on C1' (first atom fallback); they are navigation markers,
    not an inferred interaction geometry. Alternate atoms are retained in the
    underlying view; the first matching C1' conformer anchors each marker.
    Resolution errors are propagated rather than guessed from renderer labels.

    :param data: Parsed native coordinates.
    :type data: StructureData
    :param motif: One source DSSR A-minor record.
    :type motif: aminor_msa.io.parsers.dssr.AMinorMotif
    :param model_number: Explicit source mmCIF model number.
    :type model_number: int
    :param style: Optional shared viewer dimensions and marker palette.
    :type style: aminor_msa.visualization.config.ViewStyle | None
    :return: Viewer with donor and paired-residue labels and navigation markers.
    :rtype: py3Dmol.view
    :raises KeyError: If a residue is missing or has no atoms.
    :raises ValueError: If a residue lookup is ambiguous or qualified.
    """
    from ..config import DEFAULT_STYLE

    style = DEFAULT_STYLE if style is None else style
    # Resolve all identifiers before creating a partial visualization.
    records = [
        data.resolve_nucleotide(identifier, model_number=model_number)
        for identifier in (motif.donor, motif.first, motif.second)
    ]
    markers = []
    for record in records:
        atoms = list(record.residue)
        if not atoms:
            raise KeyError(f"No atoms in residue {record.chain}:{record.number}")
        atom = next((atom for atom in atoms if atom.name == "C1'"), atoms[0])
        markers.append({"x": atom.pos.x, "y": atom.pos.y, "z": atom.pos.z})
    viewer = view_structure(
        data, model_number=model_number, width=style.width, height=style.height
    )
    for identifier, position, color in zip(
        (motif.donor, motif.first, motif.second),
        markers,
        (style.donor_color, style.pair_color, style.pair_color),
        strict=True,
    ):
        viewer.addSphere(
            {"center": position, "radius": 0.8, "color": color, "opacity": 0.85}
        )
        viewer.addLabel(
            identifier.raw,
            {
                "position": position,
                "fontColor": color,
                "backgroundColor": "white",
                "backgroundOpacity": 0.8,
            },
        )
    return viewer
