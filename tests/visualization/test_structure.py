"""Selected-model viewer input and source preservation without browser access."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from aminor_msa import DataStore
from aminor_msa.visualization import view_structure
from tests.io.support import write_dataset


class ViewerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        write_dataset(self.root)
        self.coordinates = DataStore(self.root).structure("1abc").coordinates

    def test_selected_coordinates_and_source_preserved(self):
        module = Mock()
        before = self.coordinates.structure.make_mmcif_document().as_string()
        with patch.dict("sys.modules", {"py3Dmol": module}):
            viewer = view_structure(self.coordinates, model_number=9, chain="AA")
        self.assertIs(viewer, module.view.return_value)
        text, kind = viewer.addModel.call_args.args
        self.assertEqual(kind, "cif")
        self.assertIn("9 2 3", text)
        self.assertNotIn("1 2 3", text)
        self.assertEqual(
            before, self.coordinates.structure.make_mmcif_document().as_string()
        )

    def test_ambiguous_and_missing_selection(self):
        with self.assertRaises(ValueError):
            view_structure(self.coordinates)
        with self.assertRaises(KeyError):
            view_structure(self.coordinates, model_number=99)
        with self.assertRaises(KeyError):
            view_structure(self.coordinates, model_number=7, chain="missing")
        with self.assertRaises(ValueError):
            view_structure(self.coordinates, model_number=7, width=0)
