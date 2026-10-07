"""Typed readers for the supplied DSSR 2 text reports, including ZIP members."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from aminor_msa.utils.logging import get_custom_logger

from .text import open_text

logger = get_custom_logger(__name__)


@dataclass(frozen=True)
class NucleotideId:
    """A DSSR identifier retaining source numbering and the original token.

    Long tokens have six dot-separated fields. The second field is retained as
    an opaque qualifier; resolving nonempty qualifiers requires source-specific
    handling. Short tokens have no model identifier. No numbering is inferred
    from the report filename.

    :param raw: Original DSSR token.
    :param model: Model field, or None for short tokens.
    :param qualifier: Uninterpreted second long-token field.
    :param chain: Source chain identifier.
    :param name: Source residue name, including modified nucleotide names.
    :param number: Signed author residue number.
    :param insertion: Insertion code, or an empty string.
    """

    raw: str
    model: int | None
    qualifier: str
    chain: str
    name: str
    number: int
    insertion: str

    @classmethod
    def parse(cls, token: str) -> "NucleotideId":
        """Parse a long or short nucleotide token without normalizing names.

        :param token: DSSR residue identifier.
        :type token: str
        :return: Typed identifier.
        :rtype: NucleotideId
        :raises ValueError: On an unsupported or malformed token.
        """
        fields = token.split(".")
        if len(fields) == 6:
            model, qualifier, chain, name, number, insertion = fields
            return cls(
                token, int(model), qualifier, chain, name, int(number), insertion
            )
        match = re.fullmatch(
            r"([^.]*)\.([A-Za-z0-9_]*?[A-Za-z_])(-?\d+)(?:\^(.+))?", token
        )
        if match:
            chain, name, number, insertion = match.groups()
            return cls(token, None, "", chain, name, int(number), insertion or "")
        raise ValueError(f"Unsupported DSSR nucleotide identifier: {token}")


@dataclass(frozen=True)
class BasePair:
    """DSSR base-pair annotation and its unmodified table row.

    :param first: First residue.
    :param second: Second residue.
    :param bases: DSSR base shorthand.
    :param name: Pair name, such as WC or Wobble.
    :param saenger: Saenger class.
    :param leontis_westhof: LW class.
    :param dssr: DSSR pair class.
    :param raw: Original row.
    """

    first: NucleotideId
    second: NucleotideId
    bases: str
    name: str
    saenger: str
    leontis_westhof: str
    dssr: str
    raw: str


@dataclass(frozen=True)
class AMinorMotif:
    """A DSSR minor-groove triplet, including starred non-A donors.

    A starred row can have a G donor; callers must choose their label policy.
    Types I, II and X are preserved rather than collapsed to a binary label.

    :param donor: Residue contacting the pair's minor groove.
    :param first: First paired residue.
    :param second: Second paired residue.
    :param kind: DSSR type string.
    :param starred: Whether the source marks this motif with an asterisk.
    :param raw: Original motif table row.
    """

    donor: NucleotideId
    first: NucleotideId
    second: NucleotideId
    kind: str
    starred: bool
    raw: str


@dataclass(frozen=True)
class Nucleotide:
    """One DSSR nucleotide summary row.

    :param identifier: Source nucleotide identifier.
    :param base: One-letter source shorthand; case is preserved.
    :param dot_bracket: Per-nucleotide secondary-structure character.
    :param features: Comma-separated DSSR feature names.
    """

    identifier: NucleotideId
    base: str
    dot_bracket: str
    features: tuple[str, ...]


@dataclass(frozen=True)
class DotBracket:
    """A whole-structure or per-chain DSSR DBN record.

    :param header: Original record header without the leading greater-than sign.
    :param sequence: Sequence with source chain-break ampersands.
    :param notation: Extended dot-bracket notation with chain breaks.
    """

    header: str
    sequence: str
    notation: str


@dataclass
class DssrReport:
    """Parsed supported DSSR tables and retained original report text.

    ``complete`` means a consistent nucleotide summary was found. It does not
    assert biological coverage or that every source section has a typed parser.
    ``sections`` names the original sections; unsupported detail remains in text.

    :param source: Filename or ZIP member used for this report.
    :param raw_text: Complete selected report text.
    :param sections: Section headings in source order.
    :param command: Original DSSR command, when present.
    :param base_pairs: Parsed base-pair rows.
    :param aminor_motifs: Parsed minor-groove triplets.
    :param nucleotides: Parsed nucleotide summaries.
    :param dot_brackets: Whole and chain secondary-structure records.
    :param complete: Whether a complete summary was present and validated.
    """

    source: str
    raw_text: str
    sections: tuple[str, ...]
    command: str | None
    base_pairs: tuple[BasePair, ...]
    aminor_motifs: tuple[AMinorMotif, ...]
    nucleotides: tuple[Nucleotide, ...]
    dot_brackets: tuple[DotBracket, ...]
    complete: bool


def parse_dssr(handle: TextIO, *, source: str = "<stream>") -> DssrReport:
    """Parse the supported tables in a selected DSSR text stream.

    :param handle: Text input; ownership remains with the caller.
    :type handle: typing.TextIO
    :param source: Report provenance, including a ZIP member when applicable.
    :type source: str
    :return: Typed annotations, completeness flag and original text.
    :rtype: DssrReport
    :raises ValueError: On inconsistent counts or malformed supported table rows.
    """
    text = handle.read()
    lines = text.splitlines()
    pairs, motifs, nucleotides, dbn, sections = [], [], [], [], []
    command = None
    section = ""
    expected = {}
    dbn_header = None
    dbn_values = []
    # Recognize source sections before parsing their specific table schemas.
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Command:"):
            command = stripped.removeprefix("Command:").strip()
        if stripped.startswith(
            (
                "List of ",
                "Summary of structural features",
                "Secondary structures in dot-bracket",
            )
        ):
            section = stripped
            sections.append(section)
            if re.fullmatch(r"List of \d+ base pairs?", section):
                expected["pairs"] = int(section.split()[2])
            if re.fullmatch(r"List of \d+ A-minor motifs?.*", section):
                expected["motifs"] = int(section.split()[2])
            match = re.fullmatch(
                r"Summary of structural features of (\d+) nucleotides?", section
            )
            if match:
                expected["nucleotides"] = int(match[1])
            continue
        if stripped.startswith("****"):
            section = ""
            continue
        if section.startswith("Secondary structures in dot-bracket"):
            if stripped.startswith(">"):
                if dbn_header is not None and len(dbn_values) != 2:
                    raise ValueError(f"Incomplete DSSR DBN record in {source}")
                dbn_header, dbn_values = stripped[1:], []
            elif stripped and dbn_header is not None:
                dbn_values.append(stripped)
                if len(dbn_values) == 2:
                    sequence, notation = dbn_values
                    if len(sequence) != len(notation) or [
                        i for i, c in enumerate(sequence) if c == "&"
                    ] != [i for i, c in enumerate(notation) if c == "&"]:
                        raise ValueError(
                            f"Inconsistent DSSR DBN lengths or breaks in {source}"
                        )
                    dbn.append(DotBracket(dbn_header, sequence, notation))
            continue
        if section.startswith("List of ") and "A-minor motif" in section:
            match = re.match(
                r"^\s*\d+(\*)?\s+type=(\S+)\s+\S+\s+(\S+)\|(\S+),(\S+)\s", line
            )
            if match:
                star, kind, donor, first, second = match.groups()
                motifs.append(
                    AMinorMotif(
                        NucleotideId.parse(donor),
                        NucleotideId.parse(first),
                        NucleotideId.parse(second),
                        kind,
                        bool(star),
                        line,
                    )
                )
        elif re.fullmatch(r"List of \d+ base pairs?", section) and re.match(
            r"^\s*\d+\s", line
        ):
            fields = stripped.split()
            if len(fields) != 8:
                raise ValueError(f"Unexpected DSSR base-pair row in {source}: {line}")
            pairs.append(
                BasePair(
                    NucleotideId.parse(fields[1]),
                    NucleotideId.parse(fields[2]),
                    *fields[3:],
                    line,
                )
            )
        elif section.startswith("Summary of structural features") and re.match(
            r"^\s*\d+\s", line
        ):
            fields = stripped.split(maxsplit=5)
            if len(fields) < 5:
                raise ValueError(f"Unexpected DSSR nucleotide summary in {source}")
            nucleotides.append(
                Nucleotide(
                    NucleotideId.parse(fields[3]),
                    fields[1],
                    fields[2],
                    tuple(fields[5].split(",")) if len(fields) == 6 else (),
                )
            )
    # Counts distinguish a valid absence from truncated or unsupported output.
    for key, count in (
        ("pairs", len(pairs)),
        ("motifs", len(motifs)),
        ("nucleotides", len(nucleotides)),
    ):
        if key in expected and count != expected[key]:
            raise ValueError(
                f"DSSR {key} count mismatch in {source}: {count} != {expected[key]}"
            )
    if dbn_header is not None and len(dbn_values) != 2:
        raise ValueError(f"Incomplete DSSR DBN record in {source}")
    complete = "nucleotides" in expected
    if not complete:
        logger.warning("DSSR report has no validated nucleotide summary: %s", source)
    return DssrReport(
        source,
        text,
        tuple(sections),
        command,
        tuple(pairs),
        tuple(motifs),
        tuple(nucleotides),
        tuple(dbn),
        complete,
    )


def read_dssr(path: str | Path) -> DssrReport:
    """Read a selected plain or gzipped DSSR report.

    :param path: Report filename.
    :type path: str | pathlib.Path
    :return: Parsed report.
    :rtype: DssrReport
    :raises ValueError: On inconsistent supported sections.
    """
    logger.info("Reading DSSR report: %s", path)
    with open_text(path) as handle:
        return parse_dssr(handle, source=str(path))
