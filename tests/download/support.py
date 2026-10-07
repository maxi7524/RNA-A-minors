"""Small deterministic source fixtures shared by acquisition workflow tests."""

from __future__ import annotations

import zipfile
from pathlib import Path


def write_supplied_sources(source: Path) -> None:
    """Create the four supplied input types without network access.

    :param source: Destination for deterministic source fixtures.
    :type source: Path
    :return: None.
    :rtype: None
    """
    source.mkdir(parents=True, exist_ok=True)
    (source / "rfam-family-student.tsv").write_text(
        "Accession\tStudent\tStudent\tEntry\tDescription\tName\tRNA type\tSEED\tFULL\tSpecies\t3D\n"
        "RF00001\tExample\tAda\tfamily\tTest family\tTest\tGene\t1\t1\t1\t1\n"
    )
    (source / "Rfam.pdb").write_text("RF00001\t1abc\tA\t1\t3\t10\t1e-5\t1\t3\textra\n")
    with zipfile.ZipFile(source / "dssr_out_261003.zip", "w") as archive:
        archive.writestr("1abc.out", "DSSR report\n")
    with zipfile.ZipFile(source / "AminorsMSA_Main.docx", "w") as document:
        document.writestr("word/document.xml", "<document>Task</document>")
