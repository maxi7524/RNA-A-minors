"""Single-alignment Stockholm input with lossless standard annotations."""

from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from aminor_msa.utils.logging import get_custom_logger

from .text import open_text

logger = get_custom_logger(__name__)


@dataclass
class StockholmAlignment:
    """Aligned strings and GF/GS/GR/GC annotations in source order.

    Repeated GF and GS values remain separate; interleaved sequences, GC and GR
    values are concatenated. Gaps and letter case are preserved. Column indexes
    are zero-based; this representation does not imply PDB residue coordinates.

    :param sequences: Sequence identifier to aligned sequence.
    :param file_annotations: GF tag to repeated values.
    :param sequence_annotations: GS sequence identifier, tag and repeated values.
    :param residue_annotations: GR sequence identifier and aligned annotation.
    :param column_annotations: GC tag to aligned annotation.
    """

    sequences: dict[str, str]
    file_annotations: dict[str, tuple[str, ...]]
    sequence_annotations: dict[str, dict[str, tuple[str, ...]]]
    residue_annotations: dict[str, dict[str, str]]
    column_annotations: dict[str, str]

    @property
    def length(self) -> int:
        """Return the number of columns.

        :rtype: int
        """
        return len(next(iter(self.sequences.values())))


def parse_stockholm(handle: TextIO) -> StockholmAlignment:
    """Parse exactly one Stockholm 1.0 alignment from a stream.

    :param handle: Open UTF-8 text input; ownership remains with the caller.
    :type handle: typing.TextIO
    :return: Validated aligned sequences and annotations.
    :rtype: StockholmAlignment
    :raises ValueError: On malformed, truncated, multiple or inconsistent alignments.
    """
    sequences, gf, gs, gr, gc = {}, {}, {}, {}, {}
    started = ended = False
    # Accumulate fragments without quadratic string concatenation.
    for number, line in enumerate(handle, 1):
        line = line.strip()
        if not line:
            continue
        if ended:
            raise ValueError(f"Line {number}: content after Stockholm terminator")
        if not started:
            if line != "# STOCKHOLM 1.0":
                raise ValueError("Expected Stockholm 1.0 header")
            started = True
            continue
        if line == "//":
            ended = True
            continue
        if line.startswith(("#=GF", "#=GC")):
            _, tag, value = line.split(maxsplit=2)
            target = gf if line.startswith("#=GF") else gc
            target.setdefault(tag, []).append(value)
        elif line.startswith(("#=GS", "#=GR")):
            _, name, tag, value = line.split(maxsplit=3)
            target = gs if line.startswith("#=GS") else gr
            target.setdefault(name, {}).setdefault(tag, []).append(value)
        elif line.startswith("#"):
            continue
        else:
            name, sequence = line.split()
            sequences.setdefault(name, []).append(sequence)
    # Validate all aligned annotations against the same column domain.
    if not ended or not sequences:
        raise ValueError("Truncated or empty Stockholm alignment")
    sequences = {name: "".join(parts) for name, parts in sequences.items()}
    gc = {tag: "".join(parts) for tag, parts in gc.items()}
    gr = {
        name: {tag: "".join(parts) for tag, parts in tags.items()}
        for name, tags in gr.items()
    }
    lengths = {len(value) for value in sequences.values()}
    if len(lengths) != 1:
        raise ValueError("Stockholm sequence lengths differ")
    length = lengths.pop()
    if any(len(value) != length for value in gc.values()):
        raise ValueError("Stockholm GC annotation length differs")
    if (gs.keys() | gr.keys()) - sequences.keys():
        raise ValueError("Stockholm annotation references an unknown sequence")
    if any(len(value) != length for tags in gr.values() for value in tags.values()):
        raise ValueError("Stockholm GR annotation length differs")
    return StockholmAlignment(
        sequences,
        {tag: tuple(values) for tag, values in gf.items()},
        {
            name: {tag: tuple(values) for tag, values in tags.items()}
            for name, tags in gs.items()
        },
        gr,
        gc,
    )


def read_stockholm(path: str | Path) -> StockholmAlignment:
    """Read one plain or gzipped alignment into memory.

    :param path: Selected alignment filename.
    :type path: str | pathlib.Path
    :return: Parsed single-family alignment.
    :rtype: StockholmAlignment
    :raises ValueError: On inconsistent Stockholm input.
    """
    logger.info("Reading Stockholm alignment: %s", path)
    with open_text(path) as handle:
        return parse_stockholm(handle)
