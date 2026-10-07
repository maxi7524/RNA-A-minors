"""Small deterministic source fixtures shared by parser and workflow tests."""

import gzip
import json
import zipfile
from pathlib import Path

# Minimal excerpts of actual 6WLU.out1 rows, with counts reduced to the excerpts.
# They preserve negative numbering, extended pair classes, starred G donors,
# and distinct minor-groove motif types; no full archive is needed in tests.
DSSR_SAMPLE = """DSSR v2.0.0
Command: x3dna-dssr-2 -i=6WLU.cif1 --idstr=long
List of 2 base pairs
     nt1 nt2 bp name Saenger LW DSSR
   1 1..A.G.-4. 1..A.A.226. G+A -- -- cWH cW+M
       H-bonds[2]: details retained in raw_text
   2 1..A.G.-3. 1..A.A.139. G-A -- -- cWW cW-W
****************************************************************************
List of 3 A-minor motifs (types I, II, or X)
   1* type=I G|C-G 1..A.G.17.|1..A.C.61.,1..A.G.82. WC
        -1..A.C.61. H-bonds[1]: details
   2  type=I A|C-G 1..A.A.18.|1..A.C.61.,1..A.G.82. WC
   3  type=X A|U-A 1..A.A.73.|1..A.U.144.,1..A.A.221. WC
****************************************************************************
Summary of structural features of 3 nucleotides
   1  G . 1..A.G.-4. 0.001 anti,~C3'-endo,non-canonical,non-pair-contact,helix,multiplet,ss-non-loop
   2  G . 1..A.G.-3. 0.001 anti,~C3'-endo,BI,non-canonical,non-pair-contact,helix,ss-non-loop
   3  U ( 1..A.U.-2. 0.003 k-turn,anti,~C3'-endo,BI,canonical,non-pair-contact,helix,stem-end,coaxial-stack
****************************************************************************
"""

STOCKHOLM_SAMPLE = """# STOCKHOLM 1.0
#=GF AC RF00001
#=GF RN [1]
#=GF RN [2]
#=GS seq1 DE source description
#=GS seq1 DE second description
seq1 A-c
seq2 AUC
#=GR seq1 PP 9.8
#=GC SS_cons (.<

seq1 U.G
seq2 U-G
#=GR seq1 PP 7.6
#=GC SS_cons >.)
//
"""

# Synthetic atom_site rows isolate author/label numbering, insertions, alternate
# conformers and nonconsecutive source model numbers in standards-compliant CIF.
MMCIF_SAMPLE = """data_1abc
_struct.title 'A synthetic structure with preserved non-coordinate metadata'
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.type_symbol
_atom_site.label_atom_id
_atom_site.label_alt_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.label_entity_id
_atom_site.label_seq_id
_atom_site.pdbx_PDB_ins_code
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
_atom_site.occupancy
_atom_site.B_iso_or_equiv
_atom_site.auth_seq_id
_atom_site.auth_comp_id
_atom_site.auth_asym_id
_atom_site.auth_atom_id
_atom_site.pdbx_PDB_model_num
HETATM 1 P P A GTP X 1 1 A 1.0 2.0 3.0 0.5 10 -2 GTP AA P 7
HETATM 2 P P B GTP X 1 1 A 2.0 2.0 3.0 0.5 10 -2 GTP AA P 7
ATOM   3 P P . A X 1 2 ? 3.0 2.0 3.0 1.0 10 -1 A AA P 7
ATOM   4 P P . C Y 2 1 ? 4.0 2.0 3.0 1.0 10 23 C B P 7
HETATM 5 P P . GTP X 1 1 A 9.0 2.0 3.0 1.0 10 -2 GTP AA P 9
#
"""


def write_dataset(root: Path) -> None:
    """Create a tiny linked dataset under a test's temporary data directory.

    :param root: Temporary dataset root.
    :type root: pathlib.Path
    :rtype: None
    """
    for relative in (
        "config",
        "rfam/raw/RF00001",
        "rfam/raw/RF00002",
        "pdb/raw",
        "dssr/raw",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)
    (root / "config/families.csv").write_text(
        "rfam_acc,participant_id,rna_type,entry_type\nRF00001,olejnik_antonina,Gene; rRNA,Family\nRF00002,janowiak_aleksander,Cis-reg; riboswitch,Family\n"
    )
    (root / "rfam/raw/Rfam.pdb").write_text(
        "RF00001\t1ABC\tAA\t-2\t10\t50.0\t1e-9\t1\t12\n"
        "RF00001\t1ABC\tB\t23\t25\t50.0\t1e-9\t1\t3\n"
        "RF00002\t1ABC\tAA\t-2\t10\t40.0\t1e-8\t1\t12\n"
    )
    for accession in ("RF00001", "RF00002"):
        directory = root / "rfam/raw" / accession
        with gzip.open(directory / "seed.sto.gz", "wt") as handle:
            handle.write(STOCKHOLM_SAMPLE.replace("RF00001", accession))
        (directory / "family.json").write_text(
            json.dumps(
                {
                    "rfam": {
                        "acc": accession,
                        "id": "example",
                        "description": "Example RNA",
                        "release": {"number": 15},
                    }
                }
            )
        )
        (directory / "model.cm").write_text(
            f"INFERNAL1/a [1.1.4]\nNAME example\nACC {accession}\nCLEN 4\nCOM first\nCOM second\nCM\nbody\n//\nHMMER3/f\nACC different\n//\n"
        )
    with gzip.open(root / "pdb/raw/1abc.cif.gz", "wt") as handle:
        handle.write(MMCIF_SAMPLE)
    with zipfile.ZipFile(
        root / "dssr/raw/dssr_out_261003.zip", "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        archive.writestr("reports/1ABC.out1", DSSR_SAMPLE)
        archive.writestr("reports/1ABC.out2", DSSR_SAMPLE)
        archive.writestr(
            "reports/2XYZ.out1", "An unrequested report deliberately not parsed"
        )
