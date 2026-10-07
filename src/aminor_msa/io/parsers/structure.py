"""mmCIF structure access preserving author and label residue identifiers."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import gemmi

from aminor_msa.utils.logging import get_custom_logger

from .dssr import NucleotideId

logger = get_custom_logger(__name__)


@dataclass(frozen=True)
class ResidueRecord:
    """Coordinates and both mmCIF residue identifier namespaces.

    :param model_number: Original mmCIF model number, not its list index.
    :param chain: Author chain identifier.
    :param number: Signed author residue number.
    :param insertion: Author insertion code, empty when absent.
    :param name: Original residue name.
    :param label_chain: mmCIF label_asym_id.
    :param label_number: mmCIF label_seq_id, or None when absent.
    :param residue: Native Gemmi residue with atoms and alternate conformers.
    """

    model_number: int
    chain: str
    number: int
    insertion: str
    name: str
    label_chain: str
    label_number: int | None
    residue: gemmi.Residue


@dataclass
class StructureData:
    """A selected coordinate file represented by a native Gemmi structure.

    :param path: Original coordinate filename.
    :param structure: Mutable Gemmi structure; no atom conformers are removed.
    """

    path: Path
    structure: gemmi.Structure
    _residue_indexes: dict[
        tuple[int, str], dict[tuple[int, str, str], list[ResidueRecord]]
    ] = field(default_factory=dict, init=False, repr=False)

    def __getstate__(self) -> dict:
        """Serialize coordinates without duplicate native residue references.

        Lookup views are rebuilt against the restored structure so mutations
        do not target independently deserialized residue copies.

        :return: Source and coordinate state, without lookup indexes.
        :rtype: dict
        """
        return dict(self.__dict__, _residue_indexes={})

    def iter_residues(
        self, *, model_number: int | None = None, chain: str | None = None
    ) -> Iterator[ResidueRecord]:
        """Iterate residue views without copying coordinate arrays.

        :param model_number: Optional original model number filter.
        :type model_number: int | None
        :param chain: Optional author chain identifier filter.
        :type chain: str | None
        :return: Residue records retaining native Gemmi residue references.
        :rtype: collections.abc.Iterator[ResidueRecord]
        """
        for model in self.structure:
            if model_number is not None and model.num != model_number:
                continue
            for source_chain in model:
                if chain is not None and source_chain.name != chain:
                    continue
                for residue in source_chain:
                    yield ResidueRecord(
                        model.num,
                        source_chain.name,
                        residue.seqid.num,
                        residue.seqid.icode.strip(),
                        residue.name,
                        residue.subchain,
                        residue.label_seq,
                        residue,
                    )

    def resolve_nucleotide(
        self, identifier: NucleotideId, *, model_number: int
    ) -> ResidueRecord:
        """Find a unique exact author-namespace match for a DSSR nucleotide.

        The caller explicitly selects the source mmCIF model. Intermediate DSSR
        input files can renumber models; identifier.model is not assumed equal
        to the source model number. Matching does not validate atom selection,
        the input snapshot, or biological equivalence of the two structures.

        :param identifier: DSSR nucleotide identifier.
        :type identifier: NucleotideId
        :param model_number: Explicit source mmCIF model number.
        :type model_number: int
        :return: Unambiguous matching residue.
        :rtype: ResidueRecord
        :raises KeyError: If no exact residue exists.
        :raises ValueError: For ambiguous matches or unsupported qualifiers.
        """
        if identifier.qualifier:
            raise ValueError(
                "DSSR qualified identifiers require explicit source-specific handling"
            )
        index_key = (model_number, identifier.chain)
        if index_key not in self._residue_indexes:
            # Index the selected source chain once; subsequent matches are O(1).
            index = {}
            for residue in self.iter_residues(
                model_number=model_number, chain=identifier.chain
            ):
                key = (residue.number, residue.insertion, residue.name)
                index.setdefault(key, []).append(residue)
            self._residue_indexes[index_key] = index
        matches = self._residue_indexes[index_key].get(
            (identifier.number, identifier.insertion, identifier.name), []
        )
        if not matches:
            raise KeyError(
                f"No exact residue for {identifier.raw} in source model {model_number}"
            )
        if len(matches) != 1:
            raise ValueError(
                f"Ambiguous residue for {identifier.raw} in source model {model_number}"
            )
        return matches[0]

    def clear_residue_index(self) -> None:
        """Discard lookup indexes after mutating models, chains or residue IDs.

        Coordinate-only changes do not invalidate identifiers. Identifier or
        topology changes require rebuilding the index before another lookup.

        :rtype: None
        """
        self._residue_indexes.clear()


def read_structure(path: str | Path) -> StructureData:
    """Read one mmCIF or gzipped mmCIF file using Gemmi's native parser.

    :param path: Selected coordinate file.
    :type path: str | pathlib.Path
    :return: Models, chains, residues and atoms without identifier normalization.
    :rtype: StructureData
    :raises ValueError: If the file contains no coordinate models.
    """
    logger.info("Reading mmCIF coordinates: %s", path)
    # REMARK: Preserve chain parts to avoid silently merging repeated chain IDs.
    structure = gemmi.read_structure(str(path), merge_chain_parts=False)
    if not len(structure):
        raise ValueError(f"No coordinate models in {path}")
    return StructureData(Path(path), structure)


def read_mmcif_document(path: str | Path) -> gemmi.cif.Document:
    """Read all CIF categories in one file without projecting to atomic models.

    This is an optional separate read for tables such as entity_poly_seq or
    pdbx_poly_seq_scheme; no second representation is retained automatically.

    :param path: Selected mmCIF or gzipped mmCIF filename.
    :type path: str | pathlib.Path
    :return: Complete native CIF document, including non-coordinate categories.
    :rtype: gemmi.cif.Document
    """
    logger.info("Reading complete mmCIF document: %s", path)
    return gemmi.cif.read(str(path))
