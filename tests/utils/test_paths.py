"""Project discovery without Git metadata or a root working directory."""

import tempfile
import unittest
from pathlib import Path

from aminor_msa.utils.paths import find_project_root


class ProjectPathTests(unittest.TestCase):
    def test_nearest_root_from_nested_directory_and_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").touch()
            (root / "src/aminor_msa").mkdir(parents=True)
            nested = root / "assets/analysis/date"
            nested.mkdir(parents=True)
            notebook = nested / "example.ipynb"
            notebook.touch()
            self.assertEqual(find_project_root(nested), root)
            self.assertEqual(find_project_root(notebook), root)
            (root / "pyproject.toml").unlink()
            with self.assertRaises(FileNotFoundError):
                find_project_root(nested)
