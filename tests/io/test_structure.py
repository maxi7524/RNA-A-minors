"""Exact mmCIF identifiers, model selection and author-namespace lookup."""

import pickle
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aminor_msa.io import NucleotideId, read_mmcif_document, read_structure

from .support import write_dataset


class StructureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        write_dataset(self.root)
        self.coordinates = read_structure(self.root / "pdb/raw/1abc.cif.gz")

    def test_complete_document_retains_non_coordinate_categories(self):
        document = read_mmcif_document(self.root / "pdb/raw/1abc.cif.gz")
        self.assertEqual(
            document.sole_block().find_value("_struct.title"),
            "'A synthetic structure with preserved non-coordinate metadata'",
        )

    def test_author_label_and_altloc_preserved(self):
        residues = list(self.coordinates.iter_residues(model_number=7, chain="AA"))
        self.assertEqual(len(residues), 2)
        first = residues[0]
        self.assertEqual(
            (
                first.model_number,
                first.chain,
                first.number,
                first.insertion,
                first.name,
            ),
            (7, "AA", -2, "A", "GTP"),
        )
        self.assertEqual((first.label_chain, first.label_number), ("X", 1))
        self.assertEqual([atom.altloc for atom in first.residue], ["A", "B"])
        self.assertEqual(first.residue[0].pos.x, 1.0)

    def test_explicit_model_and_exact_identifier(self):
        identifier = NucleotideId.parse("1..AA.GTP.-2.A")
        first = self.coordinates.resolve_nucleotide(identifier, model_number=7)
        second = self.coordinates.resolve_nucleotide(identifier, model_number=9)
        self.assertEqual((first.residue[0].pos.x, second.residue[0].pos.x), (1.0, 9.0))
        self.assertEqual(first.model_number, 7)
        for token in ("1..AA.GTP.-2.", "1..X.GTP.-2.A", "1..AA.G.-2.A"):
            with self.subTest(token=token), self.assertRaises(KeyError):
                self.coordinates.resolve_nucleotide(
                    NucleotideId.parse(token), model_number=7
                )

    def test_chain_index_reused_and_clearable(self):
        identifier = NucleotideId.parse("1..AA.GTP.-2.A")
        self.coordinates.resolve_nucleotide(identifier, model_number=7)
        with patch.object(
            self.coordinates,
            "iter_residues",
            side_effect=AssertionError("unexpected rescan"),
        ):
            self.coordinates.resolve_nucleotide(identifier, model_number=7)
        self.coordinates.clear_residue_index()
        self.assertEqual(self.coordinates._residue_indexes, {})

    def test_serialized_lookup_views_are_rebuilt_against_restored_coordinates(self):
        identifier = NucleotideId.parse("1..AA.GTP.-2.A")
        self.coordinates.resolve_nucleotide(identifier, model_number=7)
        restored = pickle.loads(pickle.dumps(self.coordinates))
        self.assertEqual(restored._residue_indexes, {})
        residue = restored.resolve_nucleotide(identifier, model_number=7)
        residue.residue[0].pos.x = 11.0
        self.assertEqual(restored.structure[0][0][0][0].pos.x, 11.0)
        self.assertEqual(self.coordinates.structure[0][0][0][0].pos.x, 1.0)

    def test_ambiguous_residue_rejected(self):
        model = self.coordinates.structure[0]
        chain = model[0]
        chain.add_residue(chain[0])
        with self.assertRaises(ValueError):
            self.coordinates.resolve_nucleotide(
                NucleotideId.parse("1..AA.GTP.-2.A"), model_number=7
            )

    def test_opaque_qualifier_not_silently_ignored(self):
        with self.assertRaises(ValueError):
            self.coordinates.resolve_nucleotide(
                NucleotideId.parse("1.qualifier.AA.GTP.-2.A"), model_number=7
            )
